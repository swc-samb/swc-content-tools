import pymel.core as pm
import maya.cmds as mc
import maya.mel as ml
import os
import re


def export_nanite_fbx():
    '''
    Export selected fbxes to their own file
    If no selection look for special group "Static_Grp"
    '''

    # get top folder path
    folder = os.path.dirname(mc.file(q=True,sn=True))

    # back up out of _rig or _ven folders
    split_check = re.findall('_raw|_ven', folder, re.IGNORECASE)
    if split_check:
        folder = folder.split(split_check[0])[0][:-1]
    
    folder += '/Meshes'

    # get objects for export
    selected = pm.ls(sl=True)
    if not selected:
        selected = pm.ls('Static_Grp')

    # exit if it cant find anything
    if not selected:
        pm.warning('export_static_mesh_fbx: No objects given!')
        return

    print("Objects to export: {}".format(selected))
    # set export settings
    static_mesh_fbx_settings()

    # iterate through list of meshes:
    for mesh in pm.ls(selected,type='mesh') + pm.listRelatives(selected,ad=True,type='mesh'):
        # get transform node
        node = pm.listRelatives(mesh,p=True)[0]
        
        # skip if its skinned or an intermediateObject
        if mesh.getAttr('intermediateObject') or pm.listHistory(mesh,type='skinCluster'):     # mesh.getAttr('intermediateObject') or
            pm.warning('export_static_mesh_fbx: Skipping skinned mesh "{}"'.format(node))
            continue
        
        # get a subfolder path from group node name (if any)
        parent = (pm.listRelatives(node,p=True) or [None])[0]
        subfolder = ''
        if parent:
            subfolder = str(parent).split('|')[-1].split(':')[-1]
            for sub in ['^SM_' 'Geo_', '_nanite']:
                subfolder = re.sub(re.compile(sub, re.IGNORECASE), '', subfolder)
            subfolder = '/{}'.format(subfolder)
        export_folder = folder + subfolder

        # full export path
        if not os.path.exists(export_folder):
            os.makedirs(export_folder)
        export_path = '{}/{}.fbx'.format(export_folder,
                                         str(node).split('|')[-1].split(':')[-1])
        
        # duplicate mesh, and convert it to local space of the bone.
        dupe = pm.duplicate(node,rr=True)[0]
        joint = None
        if parent:
            joint_name = node.name()
            # Match '_p' plus any digit characters
            for sub in ['^SM_' 'Geo_', '_nanite', r'_p\d+']:
                joint_name = re.sub(re.compile(sub, re.IGNORECASE), '', joint_name)
            print('Looking for joint name: {}'.format(joint_name))
            joint = (pm.ls(joint_name, r=1) or [None])[0]
        if not joint:
            pm.warning('export_nanite_fbx Warning: Could not find Parent Joint "{}" for Mesh "{}"'.format(joint_name, node))
        else:
            lockNode(dupe,lock=False)
            pm.parent(dupe,joint,a=True)
            pm.makeIdentity(dupe,a=True,t=True,r=True,s=True)
            pm.parent(dupe,w=True,r=True)

        # do the export
        pm.select(dupe,r=True)      
        print('Exporting {}'.format(node))
        ml.eval('FBXExport -s -f "{}"'.format(export_path))
        print(export_path)

        # remove the duplicate afterwards.
        pm.delete(dupe)


def static_mesh_fbx_settings():    
    '''
    static_mesh_fbx_settings sets all the FBX setting for consitent FBX format exports for
    static meshes
    ''' 
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
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|TangentsandBinormals -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|SmoothMesh -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|BlindData -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|Instances -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|ContainerObjects -v true')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|Triangulate -v false')
    ml.eval('FBXProperty Export|IncludeGrp|Geometry|GeometryNurbsSurfaceAs -v NURBS')

    # Animation Settings  - no animation
    ml.eval('FBXProperty Export|IncludeGrp|Animation -v false')


def lockNode(item,lock=False):
    pm.lockNode(item,lock=lock)
    for a in item.listAttr():
        try:
            if pm.getAttr(a,l=not lock):
                pm.setAttr(a,l=lock)
        except:
            #print('lock error {}.{}'.format(item,a))
            continue
