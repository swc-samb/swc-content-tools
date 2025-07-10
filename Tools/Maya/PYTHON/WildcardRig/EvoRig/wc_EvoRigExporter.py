import sys
import stat
import os
import re
import math
import time
from inspect import getsourcefile
from collections import OrderedDict as od

import contextlib
from multiprocessing import cpu_count
from multiprocessing import Pool
import subprocess

import maya.cmds as mc
import maya.mel as ml
import pymel.core as pm


if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
    reload = __import__('importlib').reload

from fbx_sdk import *



#------------------------------------------------------------------------------#
# Scene Utility Functions
#------------------------------------------------------------------------------#


def is_visible(item):
    if not issubclass(type(item), pm.general.PyNode):
        item = (pm.ls(item) or [None])[0]
    current = item
    while current:
        display_layers = pm.listConnections(item,type='displayLayer')
        if display_layers and not all([x.getAttr('v') for x in display_layers]):
            return False
        if not current.getAttr('v'):
            return False        
        current = current.getParent()
    return True



def get_skin_cluster(item):
    '''Return any connected skin clusters'''
    return list(set((pm.listHistory(item,type='skinCluster') or []) + (pm.listConnections(item,type='skinCluster') or [])))


def get_exports(selected=None,
                root='root', 
                single_root=True, 
                hierarchy=False,
                mesh=False):
    '''Build object list for Export'''

    result = []
    if selected:
        if not mc.ls(selected, type = 'joint'):
            selected = mc.ls(sl = True, type='joint')
        else:
            selected = mc.ls(selected, type='joint')

    if not selected:
        selected = mc.ls(l = True, type='joint')

    roots = [x for x in selected if root.lower() == x.lower().split('|')[-1].split(':')[-1][:len(root)]]
    if selected and not roots:
        roots = selected
            
    if not roots:
        print('arkAnimExporterMaya.get_exports: Error: No Roots Given or Found')
        return result

    roots.sort(key = len)

    flatten = lambda x: [n for nl in x for n in nl] if hasattr(x, '__iter__') else x

    skinSort = lambda x: 0 if bool(mc.listRelatives(x, ad = True, f = True) and mc.ls(*[mc.ls(n) for n in get_skin_cluster(mc.listRelatives(x, ad = True, f = True), all = True)])) else 1
    roots.sort(key = skinSort)

    if single_root:
        result = [roots[0]]
    else:
        result = roots

    if hierarchy:
        for item in mc.listRelatives(result, ad = True, f = True, type = 'transform'):
            if 'constraint' not in mc.nodeType(item).lower():
                result.append(item)

    result.sort(key = len)

    if mesh:
        #skinClusters = get_skin_cluster(result, all = True, flatten = True)
        skinClusters = get_skin_cluster(result)

        if skinClusters:
            #meshes = get_skin_clusterMeshes(skinClusters, flatten = True)
            meshes = [x for x in pm.skinCluster(skinClusters, q=True, g=True) if is_visible(x)]

            if meshes:
                result.extend(list(set(mc.ls([x if mc.nodeType(x) == 'transform' else mc.listRelatives(x, p=True, f=True)[0] for x in meshes], l = True))))
                
    return result



#------------------------------------------------------------------------------#
# FBX Utility Functions
#------------------------------------------------------------------------------#


def skeletal_mesh_fbx_settings():
    """
    skeletalMeshFBX sets all the FBX setting for consitent FBX format exports for
    rig and mesh needs
    """ 

     # Scene Settings
    ml.eval('FBXProperty Export|AdvOptGrp|Fbx|AsciiFbx -v Binary')
    ml.eval('FBXProperty Export|AdvOptGrp|Fbx|ExportFileVersion -v FBX202000')
    ml.eval('FBXProperty Export|AdvOptGrp|AxisConvGrp|UpAxis -v Y')
    ml.eval('FBXProperty Export|IncludeGrp|CameraGrp|Camera -v false')
    ml.eval('FBXProperty Export|IncludeGrp|LightGrp|Light -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Audio -v false')
    ml.eval('FBXProperty Export|IncludeGrp|EmbedTextureGrp|EmbedTexture -v false')
    ml.eval('FBXProperty Export|IncludeGrp|BindPose -v true')
    ml.eval('FBXProperty Export|IncludeGrp|PivotToNulls -v false')
    ml.eval('FBXProperty Export|IncludeGrp|BypassRrsInheritance -v false')
    ml.eval('FBXProperty Export|IncludeGrp|InputConnectionsGrp|IncludeChildren -v true')
    ml.eval('FBXProperty Export|IncludeGrp|InputConnectionsGrp|InputConnections -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|UnitsGrp|DynamicScaleConversion -v true')
    #ml.eval('FBXProperty Export|AdvOptGrp|UnitsGrp|UnitsSelector -v Centimeters')
    ml.eval('FBXProperty Export|AdvOptGrp|UI|ShowWarningsManager -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|UI|GenerateLogData -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Obj|Triangulate -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Obj|Deformation -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionFrameCount -v 0')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionFromGlobalPosition -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionFrameRate -v 30.000000')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionGapsAsValidData -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionC3DRealFormat -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Motion_Base|MotionASFSceneOwned -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Biovision_BVH|MotionTranslation -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_ASF|MotionTranslation -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_ASF|MotionFrameRateUsed -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_ASF|MotionFrameRange -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_ASF|MotionWriteDefaultAsBaseTR -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_AMC|MotionTranslation -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_AMC|MotionFrameRateUsed -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_AMC|MotionFrameRange -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|FileFormat|Acclaim_AMC|MotionWriteDefaultAsBaseTR -v false')
    ml.eval('FBXProperty Export|AdvOptGrp|Dxf|Deformation -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|Dxf|Triangulate -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|Collada|Triangulate -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|Collada|SingleMatrix -v true')
    ml.eval('FBXProperty Export|AdvOptGrp|Collada|FrameRate -v 30.000000')

    # Geometry Settings
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|SelectionSet -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|AnimationOnly -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|SmoothingGroups -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|expHardEdges -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|TangentsandBinormals -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|SmoothMesh -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|BlindData -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|Instances -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|ContainerObjects -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|Triangulate -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|GeometryNurbsSurfaceAs -v NURBS')

    # Animation Settings
    ml.eval('FBXProperty Export|IncludeGrp|Animation -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|UseSceneName -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|RemoveSingleKey -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|Quaternion -v "Resample As Euler Interpolation"')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameStart -v {}'.format(0))
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameEnd -v {}'.format(1))
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameStep -v 1')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|ResampleAnimationCurves -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|HideComplexAnimationBakedWarning -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|Skins -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|Shape -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|ShapeAttributes -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|ShapeAttributes|ShapeAttributesValues -v Relative')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed|CurveFilterCstKeyRedTPrec -v 0.000100')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed|CurveFilterCstKeyRedRPrec -v 0.009000')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed|CurveFilterCstKeyRedSPrec -v 0.004000')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed|CurveFilterCstKeyRedOPrec -v 0.009000')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter|CurveFilterApplyCstKeyRed|AutoTangentsOnly -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|PointCache -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|ConstraintsGrp|Constraint -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Animation|ConstraintsGrp|Character -v false')


    

    # # Geometry
    # ml.eval("FBXExportSmoothingGroups -v true")
    # ml.eval("FBXExportHardEdges -v false")
    # ml.eval("FBXExportTangents -v false")
    # ml.eval("FBXExportSmoothMesh -v true")
    # ml.eval("FBXExportInstances -v false")
    # ml.eval("FBXExportReferencedAssetsContent -v false")
    # # Animation
    # ml.eval("FBXExportBakeComplexAnimation -v true")
    # ml.eval("FBXExportBakeComplexStart -v 0")
    # ml.eval("FBXExportBakeComplexEnd -v 1")
    # ml.eval("FBXExportBakeComplexStep -v 1")
    # # ml.eval("FBXExportBakeResampleAll -v true")
    # ml.eval("FBXExportUseSceneName -v false")
    # ml.eval("FBXExportQuaternion -v euler")
    # ml.eval("FBXExportShapes -v true")
    # ml.eval("FBXExportSkins -v true")
    # # Constraints
    # ml.eval("FBXExportConstraints -v false")
    # # Cameras
    # ml.eval("FBXExportCameras -v false")
    # # Lights
    # ml.eval("FBXExportLights -v false")
    # # Embed Media
    # ml.eval("FBXExportEmbeddedTextures -v false")
    # # Connections
    # ml.eval("FBXExportInputConnections -v false")
    # # Axis Conversion
    # ml.eval("FBXExportUpAxis z")
    # # File Type
    # ml.eval("FBXExportInAscii -v false")
    # # File Version
    # ml.eval('FBXExportFileVersion -v FBX201400')



def get_full_path(fbxNode):
    '''Get full path name for FBX sdk fbxNode'''

    if not fbxNode:
        return ''
    return get_full_path(fbxNode.GetParent()) + '|' + fbxNode.GetName()


def fbx_cleanup(filePath, 
                root='root',
                metaData=None,
                keep_list=None):
    '''Checks leaf Level Objects, 
       Deletes if they don't match root regex,
       Removes all namespaces to make retargeting from fbx easier,
       Embeds Useful Meta Data and thumbnail'''
    
    if not os.path.exists(filePath):
        print('deleteExtraObjects Error: File "{}" not found'.format(filePath))
        return

    
    # given list of items to keep
    keep_list = keep_list or od()
    if keep_list and not issubclass(type(keep_list),dict):
        temp_list = keep_list
        keep_list = od()
        for x in temp_list:
            if hasattr(x, 'longName'):
                x = x.longName()
            else:
                x = str(x)
            keep_list['|RootNode' + x] = True
            splits = x.split('|')
            if splits:
                for n in range(1,len(splits)):
                    keep_list['|RootNode' + '|'.join(splits[:n])] = True
                

    print('fbxCleanup: Begin: "{}"'.format(filePath))
    temp = '{}/{}_{}.fbx'.format(os.path.dirname(filePath),
                                 os.path.basename(filePath).split('.')[0],
                                 str(time.time()).replace('.',''))
    

    #load scene manually to ensure proper file type
    manager, scene = InitializeSdkObjects()
    importer = FbxImporter.Create(manager, "")    
    result = importer.Initialize(filePath, -1, manager.GetIOSettings())
    if not result:
        return False
    
    if importer.IsFBX():
        manager.GetIOSettings().SetBoolProp(EXP_FBX_MATERIAL, False)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_TEXTURE, False)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_EMBEDDED, True)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_SHAPE, False)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_GOBO, False)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_ANIMATION, True)
        manager.GetIOSettings().SetBoolProp(EXP_FBX_GLOBAL_SETTINGS, True)
    
    result = importer.Import(scene)
    importer.Destroy()

    #LoadScene(manager, scene, filePath)

    # set metadata

    sceneInfo = scene.GetSceneInfo()
    metaData = metaData or {}
    revision = metaData.get('revision')
    if not revision:
        revision = str(int((re.findall('[0-9]+', str(sceneInfo.mRevision)) or [0][-1]+1)))

    basename = os.path.basename(filePath).split('.')[0]
    sceneInfo.mTitle = FbxString(metaData.get('title') or basename)
    sceneInfo.mSubject = FbxString(metaData.get('subject') or mc.file(q=True,sn=True))
    sceneInfo.mAuthor = FbxString(metaData.get('author') or os.getenv('USERNAME'))
    sceneInfo.mRevision = FbxString(revision)
    sceneInfo.mKeywords = FbxString(metaData.get('keywords') or ' '.join(basename.split('_')))
    sceneInfo.mComment = FbxString(metaData.get('Comment') or '')
    changed = True

    # thumbnail = FbxThumbnail())
    # thumbnail.SetDataFormat(FbxThumbnail.eRGB_24)
    # thumbnail.SetSize(FbxThumbnail.e64x64)
    # thumbnail.SetThumbnailImage(cSceneThumbnail)
    # sceneInfo.SetSceneThumbnail(thumbnail)


    #adding all objects and their parent hierarchies to objCheck list
    nodeList =  [scene.GetRootNode()]
    node = scene.GetRootNode()
    extras = 0
    renamed = 0
    deleted = 0
    reparent = 0
    #iterate through and make anything not a joint for removal later
    keep = od()
    remove = od()

    hi_check = lambda x: '|'.join((n for n in str(x).split('|') if n))
    root = hi_check(root)


    # Getting a list of nodes from keep_list to prevent them from being removed
    keep_override = od()
    nodeList =  [scene.GetRootNode()]
    for item in nodeList:
        for i in range(item.GetChildCount()-1, -1, -1):
            child = item.GetChild(i)
            nodeList.append(child)
            #print('Checking:', keep_list.get(get_full_path(child)), get_full_path(child))
            if keep_list.get(get_full_path(child)):
                #print('-Keeping:', keep_list.get(get_full_path(child)), get_full_path(child))
                keep_override[child.GetUniqueID()] = child


    #remove extra root objects if it doesnt match given root name
    for i in range(node.GetChildCount()-1, -1, -1):
        child = node.GetChild(i)
        if hi_check(child.GetName()) == root:            
            keep[get_full_path(child)] = child
        else:
            changed = True
            extras += 1
            remove[get_full_path(child)] = child


    nodeList =  [scene.GetRootNode()]
    for item in nodeList:
        for i in range(item.GetChildCount()-1, -1, -1):
            child = item.GetChild(i)
            basename = child.GetName().split('|')[-1]
            nodeList.append(child)

            #reparent root to scene root

            #print(hi_check(child.GetName()).split('|')[-1]  == root)
            #print(hi_check(child.GetName()).split('|')[-1], root)
            if hi_check(child.GetName()).split('|')[-1] == root: 
                parent = child.GetParent()
                #print(' ', get_full_path(parent))
                #print(' ', get_full_path(node))
                if parent and get_full_path(parent) != get_full_path(node):
                    reparent += 1
                    changed = True
                    node.AddChild(child)
                    parent.RemoveChild(child)

            #remove all namespaces

            if ':' in basename:
                #print('renaming : "{}" . '.format(basename))
                child.SetName(basename.split(':')[-1])
                changed = True
                renamed += 1
                #print('"{}"'.format(child.GetName().split('|')[-1]))

            #print(bool(child.GetSkeleton()), child.GetName())
            if child.GetSkeleton():
                keep[get_full_path(child)] = child
            else:
                remove[get_full_path(child)] = child
            

    #check all keepers and remove their parents from remove list
    for item in keep.values():
        parent = item.GetParent()        
        while parent and parent.GetParent():
            checkName = get_full_path(parent)
            if remove.get(checkName):
                del remove[checkName]
                #print('Saving Transform', parent.GetName(), 'Parent of', item.GetName())
            parent = parent.GetParent()

    #remove any remaining objects still marked for removal
    if remove:
        changed = True
        for item in remove.values():
            if item.GetParent() and not keep_override.get(item.GetUniqueID()):
                print('Deleting "{}"'.format(item.GetName()))
                item.GetParent().RemoveChild(item)
                deleted += 1

    #Export
    pFileFormat = manager.GetIOPluginRegistry().GetNativeWriterFormat()
    print('File Format "{}"'.format(pFileFormat, manager.GetIOPluginRegistry().GetWriterFormatDescription(pFileFormat)))

    exporter = FbxExporter.Create(manager, "")
    exporter.Initialize(temp, pFileFormat)
    exporter.Export(scene)
    exporter.Destroy()

    #FbxCommon.SaveScene(manager, scene, temp)
    os.remove(filePath)
    os.rename(temp, filePath)
    print('Reparent Root {}'.format(bool(reparent)))
    print('Deleted {} Extra Roots'.format(extras))
    print('Deleted {} Non Joints'.format(deleted))
    print('Removed Namespace from {} FBX Objects'.format(renamed))
        
    manager.Destroy()
    print('FBXCleanup Finished "{}"'.format(filePath))



def export_rig(export_path=None, 
               selected=True, 
               prompt=True, 
               root='root',
               all_joints=True): 

    #load fbx Settings 
    
    skeletal_mesh_fbx_settings()   
     
    # some overrides for Unreal Upaxis
    print('UpAxis Maya {}'.format(pm.upAxis(q = True, axis = True)))
    ml.eval("FBXExportUpAxis {}".format(pm.upAxis(q = True, axis = True))) 
    print('UpAxis FBX {}'.format(ml.eval("FBXExportUpAxis -q")))

    
    if not export_path and prompt:
        folder = os.path.dirname(mc.file(q=True,sn=True)) or mc.internalVar(pwd=True)
        export_path = mc.fileDialog2(fm = 0, ff="FBX Files (*.fbx)", dir=folder, cap='Save Rig File')
        if export_path:
            export_path = export_path[0]
            folder = os.path.dirname(export_path)
        else:
            print('Export Rig Cancelled by User')
            return

    if not export_path:        
        file_name = mc.file(q=True,sn=True) or '{}/SK_Rig'.format(mc.internalVar(pwd=True))
        folder = os.path.dirname(file_name)
        export_path = '{}/{}.fbx'.format(folder, os.path.basename(file_name).split('.')[0])
    else:
        folder = os.path.dirname(export_path)
        

    if not selected:
        # Get export meshes from root
        export_items = get_exports(hierarchy=True, mesh=True, root=root)

    else:
        # Get export meshes and joints from selection
        selected = (pm.ls(sl=True, type='mesh') or []) + (pm.listRelatives(pm.ls(sl=True), ad=True, type='mesh', f=True) or [])
        selected = [x.getParent() for x in selected if is_visible(x)]

        export_items = od([(a,True) for a in selected[:]])
        influences = od()
        for item in selected:
            skinCluster = get_skin_cluster(item)
            if skinCluster:
                for a in pm.ls(pm.skinCluster(skinCluster, q=True, inf=True), l=True):
                    influences[a] = True

        export_items.update(influences)

        if all_joints:
            for k in influences.keys():
                parent = k.getParent()
                while parent:
                    export_items[parent] = True
                    parent = parent.getParent()
                    
            for child in (pm.listRelatives(*export_items, ad=True, f=True, type=['transform', 'joint']) or []):
                if not export_items.get(child) and mc.nodeType(child.longName()) in ['transform', 'joint']:
                    export_items[child] = True

        export_items = sorted(export_items.keys())


    # Export
    OS = pm.ls(sl = True, l = True)

    pm.select(export_items, r = True)
    ml.eval('FBXExport -s -f "{}"'.format(export_path))

    if OS:
        pm.select(OS, r = True)
    else:
        pm.select(cl =True)

    # Run Fbx SDk Cleanup actions
    fbx_cleanup(export_path, keep_list=export_items)

    print('Exported: "{}"'.format(export_path))

    #ml.eval('FBXPopSettings;')
    return export_path
    