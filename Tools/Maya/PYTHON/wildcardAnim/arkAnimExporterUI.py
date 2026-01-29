# coding=utf-8

import sys
import stat
import os
import re
import math
import time
import datetime
import random
import traceback
import pickle
from inspect import getsourcefile

if sys.version_info.major < 3:
    from itertools import izip
else:
    izip = zip

from collections import OrderedDict as od
from functools import partial

import contextlib
from multiprocessing import cpu_count
from multiprocessing import Pool
import subprocess

import maya.cmds as mc
import maya.mel as ml
import pymel.core as pm

# python 3 doesnt seem to populate path with currently directory for some reason
SCRIP_PATH = os.path.abspath(getsourcefile(lambda:0))
LOCAL_PATH = os.path.dirname(SCRIP_PATH)
if LOCAL_PATH not in sys.path:
    sys.path.insert(0,LOCAL_PATH)

SCRIPT_DATETIME = datetime.datetime.fromtimestamp(os.path.getmtime(SCRIP_PATH))
SCRIPT_TIME_STRING = str((SCRIPT_DATETIME.hour-1)%12+1) + SCRIPT_DATETIME.strftime(':%M%p %Z on %b %d, %Y')


try:
    makedirs = os.makedirs
except:
    mkdirs = os.mkdirs


import fbxExport
from fbx_sdk import *


__author__ = 'Ethan McCaughey'
__version__ = '0.3.0'

PLAYBLAST_WIDTH = 1920
PLAYBLAST_HEIGHT = 1080

#------------------------------------------------------------------------------#
# Force Load Plugins
#------------------------------------------------------------------------------#

def loadPlugin(plugin = 'gameFbxExporter', pluginPath = None):   
    '''Force plugin loading'''
    plugin = str(plugin).split('.')[0] 
    if pluginPath == None:
        for path in os.getenv('MAYA_PLUG_IN_PATH').split(';'):
            path = path.replace('\\','/')
            if not os.path.exists(path):
                continue
            for item in os.listdir(path):
                if plugin.lower() == item.split('.')[0].lower():
                    pluginPath = '{}/{}'.format(path, item)

    if not os.path.exists(str(pluginPath)):
        print('loadPlugin: Error: Plugin "{}" Not Found at "{}"'.format(plugin, pluginPath))
        return 

    if not mc.pluginInfo(os.path.basename(pluginPath), q = True, loaded = True):
        print('loadPlugin: Loading Plugin "{}" at "{}"'.format(plugin, pluginPath))
        try:
            mc.loadPlugin(pluginPath)
            mc.evalDeferred('import maya.cmds as mc; mc.pluginInfo("{}", e = True, autoload = True);'.format(pluginPath))
        except Exception as e:
            print('loadPlugin: Error:'.format(pluginPath))
            print(e)
            pass

loadPlugin(plugin = 'fbxmaya.mll')


#------------------------------------------------------------------------------#
# UI Helper Functions
#------------------------------------------------------------------------------#

def textDialog(title, message, text = ''):
    '''Generic text dialog function'''
    result = mc.promptDialog(title=title,
                             message=message,
                             text=text,
                             button=['OK', 'Cancel'],
                             defaultButton='OK',
                             cancelButton='Cancel',
                             dismissString='Cancel')
    if result == 'OK':
        return mc.promptDialog(query = True, text = True)
        

def confirmDialog(title, message):
    '''Generic confirmation dialog function'''
    confirm = mc.confirmDialog(title=title, 
                               message=message,
                               button=['Yes','No'],
                               defaultButton='Yes',
                               cancelButton='No',
                               dismissString='No')
    return confirm == 'Yes'


def removeWindows(windowName):  
    '''Clear window when script is called'''
    if (mc.window(windowName, exists=True)): 
        mc.deleteUI(windowName)



def setSelectionToTextField(parent, *args, **kwargs):
    '''Set text field with selected'''

    attribute = kwargs.get('attribute')
    textField = kwargs.get('textField')
    #animLayer = kwargs.get('animLayer')
    camera = kwargs.get('camera')        
    panel = pm.playblast(ae=True).split('|')[-1]

    if camera:
        selection = pm.ls(pm.modelPanel(panel,q=True,camera=True)) or pm.ls('persp')
    else:
        selection = [x.name() for x in pm.ls(sl = True)]

    if not selection:
        pm.warning('Nothing Selected for', attribute)
        return
    setattr(parent, attribute, selection[0])
    
    print('Set {} {}'.format(attribute, selection[0]))
    pm.textField(textField, edit = True, text = selection[0])
    

def batchExportPrompt(playblast=False):    
    '''Prompt for fold and batch export animations from maya files in it'''
    folder = os.path.dirname(mc.file(q=True,sn=True))
    filePath = str((pm.fileDialog2(cap = "Batch Export Folder",
                                   dir = folder,
                                   ds = 2, 
                                   okc = "Batch Export Folder",
                                   fm = 3, 
                                   rf = 1) or [''])[0])
    # search recursivly in folder                               
    print('Batch Export: "{}"'.format(filePath))
    files = []
    workFolders = [filePath]
    for folder in workFolders:
        for item in os.listdir(folder):
            filename = '{}/{}'.format(folder,item)
            if os.path.isdir(filename):
                workFolders.append(filename)
                #print('adding folder',filename)
                continue
            #print('filecheck ', re.findall('ma$|mb$',str(item).split('.')[-1], re.IGNORECASE), filename)
            if re.findall('ma$|mb$',str(item).split('.')[-1], re.IGNORECASE):
                files.append(filename)
                #print('adding file',filename)


    #files = ['{}/{}'.format(filePath,x) for x in os.listdir(filePath) if re.findall('ma$|mb$',str(x).split('.')[-1], re.IGNORECASE)]
    print(' - {} Files'.format(len(files)))
    batchExportFiles(files,playblast=playblast)
                                   

def batchExportFiles(files,playblast=False):
    '''Function to iterate through maya files from a folder and batch export their export settings'''
    isMaya = 'maya' == os.path.basename(sys.executable).split('.')[0].lower()
    # disabling this for now, because it doesnt cancel properly, 
    # and the progress window itself only pops up periodically,
    # will switch to progress bar instead of window at some point.
    isMaya = False

    fx = len(files)
    if not fx:
        return
    
    if isMaya:   
        #pm.progressWindow(endProgress=True)     
        pm.progressWindow(title=f'Batch Export Animations',
                          progress=0,
                          status=f'Exporting: 0% - 0/{fx} files',
                          isInterruptable=True)
                          
    for f,item in enumerate(files):
        if not os.path.exists(item):
            pm.warning('File not found "{}"!'.format(item))
            continue
        if not os.path.isfile(item):
            pm.warning('This is not a file "{}"!'.format(item))
            continue


        if isMaya:  
            print('Cancelled?: {}'.format(pm.progressWindow(endProgress=True)))      
            if pm.progressWindow(query=True, isCancelled=True) or pm.progressWindow(query=True, isCancelled=True) == None:
                pm.progressWindow(endProgress=True)
                return

            percent = int((float(f+1)/fx)*100)                
            pm.progressWindow(edit=True,
                              title=f'Batch Export Animations',
                              progress=percent,
                              status=f'Exporting: {f+1}/{fx} files - {percent}%')

        print('-'*80)
        print(f'Exporting {f+1}/{fx} "{item}"')
        print(f' -playblast: {playblast}')
        print('-'*80)
        try:
            mc.file(item,open=True,f=True,ignoreVersion=True)
            info = AnimExporterUI(batch=True)
            info.exportAll(playblast=playblast)
        except Exception as e:            
            if isMaya: 
                pm.progressWindow(endProgress=True)
            raise e

    if isMaya:
        pm.progressWindow(endProgress=True)

#------------------------------------------------------------------------------#
# Scene Utility Functions
#------------------------------------------------------------------------------#

def getFPS():
    '''Get FPS in proper float format'''
    lookup = {'game':15.0,
              'film':24.0,
              'pal':25.0,
              'ntsc':30.0,
              'show':48.0,
              'palf':50.0,
              'ntscf':60.0}
    rawTime = pm.currentUnit(q=True,t=True)
    return float((re.findall('[0-9\.]+', rawTime) or [lookup.get(rawTime,30.0)])[0])

def timestamp():
    '''timestamp string'''
    return str(time.time()).replace('.','')

def isArk2(path=None):
    '''Ark2 handles default exportpath differently, bool to detect that based on path name'''
    return bool(re.findall('^b:', str(path or mc.file(q=True,sn=True)), re.IGNORECASE)) 

def getFolderFile():
    '''Return current folder and filename'''
    filePath = mc.file(q = True, sn = True)
    folder = os.path.dirname(filePath)
    if not folder or not os.path.exists(folder):
        folder = mc.internalVar(pwd = True)
    if 'raw' == os.path.basename(folder).lower() and not isArk2(filePath):
        folder = os.path.dirname(folder)
    if not filePath:
        filePath = 'untitled'
    return folder, os.path.basename(filePath).split('.')[0]


frameRegex = re.compile('([0-9]+)f$', re.IGNORECASE)
def isExportLayer(name):
    '''Treat anim layers ending if #f as an animation'''
    return str(name) != 'BaseAnimation' and re.findall(frameRegex, str(name))


def getLayerNameFrame(name):
    '''Get filename and frame length from anim layer name'''

    name = str(name)
    frames  = re.findall(frameRegex, name)
    if frames:
        name = name[:-(len(frames[0])+1)]
    else:
        frames = [mc.playbackOptions(q = True, maxTime = True)]
    if len(name)>1 and name[-1] == '_':
        name = name[:-1]

    folder, filePath = getFolderFile()
    folder, name, ext = animFolderFilePrefix(os.path.join(folder, name))
    return name, int(frames[0])


def getCurrentAnimLayers():
    '''Find selected anim layer if any'''

    animCheck = lambda x: str(x) != 'BaseAnimation' and not pm.animLayer(x, q = True, mute = True)
    return [x for x in pm.ls(type = 'animLayer') if animCheck(x)]


def getRigName(root=None):
    '''Finds basename of refernced rig file or namespace and strips it of _RIG suffix'''
    if not root:
        root = defaultRoot()
    if not root:
        return ''
    
    rigName = ''
    if ':' in root:
        refFile = pm.referenceQuery(root,f=True)
        if refFile:
            rigName = re.sub('_RIG$','',os.path.basename(refFile).split('.')[0])
        elif ':' in root.name():
            rigName = root.name().split(':')[-2]

    return rigName


def defaultRoot(root='root',allRoots=False):  
    '''return first root joint corresponding to root name, 
       from selection if any, else scene'''

    selectedJoints = []

    if not allRoots:
        selectedJoints = pm.ls(sl=True, type='joint')
        if not selectedJoints:
            selected = pm.ls(sl=True)
            if selected:
                nameSpaces = [':'.join(x.name().split(':')[:-1]) for x in selected if ':' in x.name()]
                if nameSpaces:
                    selectedJoints = list(set([n for nl in (pm.ls('{}:*'.format(n),type='joint') for n in nameSpaces) for n in nl]))

    if not selectedJoints:
        selectedJoints = pm.ls(type='joint')

    roots = [x for x in selectedJoints if root.lower() == x.name().lower().split('|')[-1].split(':')[-1][:len(root)]]

    if not roots:
        roots = pm.ls(sl=True, type='joint')

    if not roots:
        print('arkAnimExporterUI.defaultRoot: Error: No Root joints Given or Selected')
        return None

    print('defaultRoot allRoots', allRoots, roots)
    lenSort = lambda x: len(x.longName())
    if not allRoots:
        roots.sort(key = lenSort)
        return roots[0].name()
    else:
        namespaces = {}
        for item in roots:
            namespace = ''
            if ':' in item.name():
                namespace = ':'.join(item.name().split(':')[:-1])
            if not namespaces.get(namespace):
                namespaces[namespace] = []
            namespaces[namespace].append(item)
        namespaceRoots = [list(sorted(x,key=lenSort))[0] for x in namespaces.values() if x]
        return [x.name() for x in namespaceRoots]


def animFolderFilePrefix(filePath = None):
    '''Certain anims should have prefixes, name fbx correctly based on export folder
       Create folder for export if it doesnt exist
       Return folder, filename, ext'''

    if filePath == None:
        folder, filePath = getFolderFile()
        filePath = os.path.join(folder, filePath + '.fbx').replace('\\','/')

    ext = filePath.split('.')[-1]
    folder, filePath = os.path.dirname(filePath), os.path.basename(filePath).split('.')[0]
    filecheck = '{}/'.format(str(folder).lower().replace('\\','/'))         
    prefix = ''

    if not isArk2(filecheck):
        if 'raw' == os.path.basename(folder).lower():
            folder = os.path.dirname(folder)
        if '/humans/' in filecheck or '/human/' in filecheck :
            folder = '{}/FBX'.format(folder)
           
        if '/cinematics/' not in filecheck:
            if '/humans/' not in filecheck and '/human/' not in filecheck :
                if '/weapons/' in filecheck:  
                    if '/tpv/' in filecheck:
                        prefix = 'TPV_'
                    elif '/fpv/' in filecheck:
                        prefix = 'FPV_'                 
                    prefix = '{}{}_'.format(prefix, os.path.basename(os.path.dirname(folder)))
                    
                    if not '/fpv/' in filecheck:
                        if '/female/' in filecheck:
                            prefix = '{}HF_'.format(prefix)
                        else:
                            prefix = '{}HM_'.format(prefix)   
                else:                
                    prefix = '{}_'.format(os.path.basename(folder))

            else:
                if '/tpv/' in filecheck:
                    prefix = 'TPV'
                elif '/fpv/' in filecheck:
                    prefix = 'FPV'                 
                prefix = '{}_{}'.format(prefix, os.path.basename(os.path.dirname(folder)))
                
                if not '/fpv/' in filecheck:
                    if '/female/' in filecheck:
                        prefix = '{}_HF_'.format(prefix)
                    else:
                        prefix = '{}_HM_'.format(prefix)  

                if '/npc/' in filecheck:
                    prefix = '{}_NPC_'.format(prefix)


    if not os.path.exists(folder):
        makedirs(folder)

    if re.findall('^' + prefix, filePath):
        filePath = filePath[len(prefix):]

    return folder, prefix + filePath, ext


def playblast(*args, **kwargs):
    filePath = mc.file(q=True, sn=True)
    if not filePath:
        pm.warning('File Not Saved!')
        return
    folder = os.path.dirname(filePath)    
    name = kwargs.get('name', os.path.basename(filePath).split('.')[0])
    root = kwargs.get('root')
    cameras = kwargs.get('cameras') or ''

    if 'qt' in pm.playblast(q=True,fmt=True):
        fmt = 'qt'
        ext = '.mov'
        compression = 'H264'
    else:
        fmt = 'avi'
        ext = '.avi'
        compression = 'none'
        pm.warning('Quicktime H264 Codec Not Installed!')

    namespace = ''
    if ':' in str(root):
        namespace = '{}:'.format(':'.join(str(root).split(':')[:-1]))

    
    #ml.eval('setNamedPanelLayout "Single Perspective View";')              
    #ml.eval('toggleMainWindowFullScreenModeDefer 0 MainPane;') 
    panel = pm.playblast(ae=True).split('|')[-1]
    current = pm.ls(pm.modelPanel(panel,q=True,camera=True)) or [pm.ls('persp')[0]]
    playCameras = pm.ls(str(cameras).split(',')) or pm.ls('{}*_playblast_*'.format(namespace),type='transform') or current

    for playCamera in playCameras:
        # switch active panel to play Camera
        print('playblast camera "{}"'.format(playCamera))
        pm.modelPanel(panel,edit=True,camera=playCamera)

        # save show states for control items then hide them
        showLocators = pm.modelEditor(panel, q=True, locators=True)
        showCurves = pm.modelEditor(panel, q=True, nurbsCurves=True)
        showCameras = pm.modelEditor(panel, q=True, cameras=True)
        showHandles = pm.modelEditor(panel, q=True, handles=True)
        showJoints = pm.modelEditor(panel, q=True, joints=True)
        showPolygons = pm.modelEditor(panel, q=True, polymeshes=True)
        pm.modelEditor(panel, 
                        e=True, 
                        nurbsCurves=False, 
                        locators=False, 
                        cameras=False,
                        joints=False,
                        handles=False,
                        polymeshes=True,)

        # playblastPath = '{}/playblasts/{}_{}{}'.format(folder, 
        #                                                name, 
        #                                                playCamera.name().split('|')[-1].replace(':','_'),
        #                                                ext)
        playblastPath = '{}/review/{}_{}{}'.format(folder, 
                                                       name, 
                                                       playCamera.name().split('|')[-1].replace(':','_'),
                                                       ext)

        print('Movie          : "{}"'.format(playblastPath))   
        print('- Compression  : "{}"'.format(compression)) 
        print('- Width Height :  {} x {}'.format(PLAYBLAST_WIDTH, PLAYBLAST_HEIGHT)) 
        #Create the playplast
        pm.playblast(fmt=fmt,
                     filename=playblastPath, 
                     clearCache=False,
                     viewer=False,
                     showOrnaments=False,
                     offScreen=True,
                     forceOverwrite=True,
                     fp=4,
                     percent=100, 
                     compression=compression,
                     quality=100,
                     widthHeight=(PLAYBLAST_WIDTH, PLAYBLAST_HEIGHT))
        
        # restore show states for control items
        pm.modelEditor(panel, 
                       e=True, 
                       nurbsCurves=showCurves, 
                       locators=showLocators, 
                       cameras=showCameras,
                       joints=showJoints,
                       handles=showHandles,
                       polymeshes=showPolygons)
        print(playblastPath)

    #ml.eval('toggleMainWindowFullScreenModeDefer 1 MainPane;') 
    # 
    print('current camera "{}"'.format(current[0])) 
    pm.modelPanel(panel,edit=True,camera=current[0])
    

def attachBlendShapeCurvesOnRoot(root):
    meshes = list(set(pm.listHistory(pm.listRelatives(root,ad=True,type='joint') + [root], f=True, type='mesh')))
    blendShapes =  list(set(pm.listHistory(meshes,type='blendShape')))
    if not blendShapes:
        pm.warning('Animation Export Warning: No blend shapes found for "{}"'.format(root))
        return

    #shapes = {k:v for xl in (zip(pm.listAttr(b.w,m=True),pm.blendShape(b,q=True,target=True)) for b in blendShapes) for k,v in xl}
    attributes = od([x for xl in (((x,getattr(b,x)) for x in pm.listAttr(b.w,m=True)) for b in blendShapes) for x in xl])
    reverse = od((v,k) for k,v in attributes.items())
    #create blendshape attributes on root if they dont already exist
    #connect them to blendshape attributes if they arent already
    for attribute,blendShapeAttribute in attributes.items():
        if len(re.findall('[a-zA-Z0-9\_]+', attribute)) != 1:
            #print('attachBlendShapeCurvesOnRoot: Skipping invalid attribute "{}"'.format(a))
            continue

        if not pm.objExists('{}.{}'.format(root,attribute)):
            pm.addAttr(root,longName=attribute,defaultValue=0.0,keyable=True)
            
        rootAttribute = getattr(root,attribute)
        #blendShapeAttribute = [getattr(b,a) for b in blendShapes if hasattr(b,a)][0]
        inputConnection = (pm.ls(pm.connectionInfo(rootAttribute, sfd=True)) or [None])[0]
        #print(reverse.get(inputConnection) != attribute, attribute, reverse.get(inputConnection))
        if reverse.get(inputConnection) != attribute:
            print('"{}" != "{}" "{}"->"{}"'.format(attribute, reverse.get(inputConnection), str(blendShapeAttribute), str(rootAttribute)))
            
            try:
                if inputConnection:
                    pm.disconnectAttr(inputConnection, rootAttribute)
                pm.connectAttr(blendShapeAttribute, rootAttribute)
            except Exception as e:
                pm.warning('attachBlendShapeCurvesOnRoot: Connection Error "{}" -> "{}"\n{}'.format(blendShapeAttribute, rootAttribute,e))

        
        




#------------------------------------------------------------------------------#
# FBX Utility Functions
#------------------------------------------------------------------------------#


def getFullPath(fbxNode):
    '''Get full path name for FBX sdk fbxNode'''

    if not fbxNode:
        return ''
    return getFullPath(fbxNode.GetParent()) + '|' + fbxNode.GetName()
    

def fbxCleanup(filePath, 
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
        revision = str(int((re.findall('[0-9]+', str(sceneInfo.mRevision)) or [0])[-1])+1)

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
            #print('Checking:', keep_list.get(getFullPath(child)), getFullPath(child))
            if keep_list.get(getFullPath(child)):
                #print('-Keeping:', keep_list.get(getFullPath(child)), getFullPath(child))
                keep_override[child.GetUniqueID()] = child


    #remove extra root objects if it doesnt match given root name
    for i in range(node.GetChildCount()-1, -1, -1):
        child = node.GetChild(i)
        if hi_check(child.GetName()) == root:            
            keep[getFullPath(child)] = child
        else:
            changed = True
            extras += 1
            remove[getFullPath(child)] = child


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
                #print(' ', getFullPath(parent))
                #print(' ', getFullPath(node))
                if parent and getFullPath(parent) != getFullPath(node):
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
                keep[getFullPath(child)] = child
            else:
                remove[getFullPath(child)] = child
            

    #check all keepers and remove their parents from remove list
    for item in keep.values():
        parent = item.GetParent()        
        while parent and parent.GetParent():
            checkName = getFullPath(parent)
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
    #os.remove(filePath)
    os.replace(temp, filePath)
    
    print('Reparent Root {}'.format(bool(reparent)))
    print('Deleted {} Extra Roots'.format(extras))
    print('Deleted {} Non Joints'.format(deleted))
    print('Removed Namespace from {} FBX Objects'.format(renamed))
        
    manager.Destroy()
    print('FBXCleanup Finished "{}"'.format(filePath))
    


#------------------------------------------------------------------------------#
# UI classes
#------------------------------------------------------------------------------#


class browseTextField(object):
    def __init__(self, 
                 label = 'filePath',
                 title = 'Browse', 
                 message = 'Browse for File',
                 mode = 0,
                 fileType = 'fbx',
                 attribute = 'exportPath',
                 parent = None):
        '''Class to handle linked textfield and file browsing'''

        self.label = label
        self.title = title
        self.message = message
        self.mode = mode
        self.fileType = fileType
        self.attribute = attribute
        self._parent = parent

        self.name = self.label + timestamp()
        self.column = None
        self.button = None
        self.textField = None

        self.create()

    
    def create(self):        
        self.column = pm.rowColumnLayout("folderColumn", 
                                         nc = 2, cw = [(1,self._parent.width * 0.2), 
                                                       (2,self._parent.width * 0.8)],
                                         adjustableColumn = True,
                                         w = self._parent.width)

                                                    
        self.button = pm.button(self.name + 'Button',
                                label = 'Browse ' + self.label + ' >', 
                                annotation = 'Browse For Export Folder',
                                command = partial(self.update, browse = True),
                                parent = self.column)

        self.textField = pm.textField(self.name + 'TextField', 
                                      annotation = self.label + ' Path',
                                      text = getattr(self._parent, self.attribute),
                                      changeCommand = partial(self.update, browse = False),
                                      parent = self.column)
        self.update(getattr(self._parent, self.attribute))


    def update(self, *args, **kwargs): 
        '''Browse and update various data and UI'''
        
        if kwargs.get('browse'):
            folder = self._parent.__dict__.get('folder')
            if not folder:
                folder, name = getFolderFile()
            filePath = str((pm.fileDialog2(cap = "Choose " + self.label,
                                           dir = folder,
                                           ds = 2, 
                                           okc = self.message, 
                                           fm = self.mode, 
                                           ff = '*.' + self.fileType, 
                                           rf = 1) or [''])[0])
            if not filePath:
                return
        else:
            filePath = ''
            if args:
                filePath = args[0]
            folder = os.path.dirname(filePath)
    
        if not filePath:
            mc.warning('arkAnimExportUI: No File Path Chosen')
            setattr(self._parent, self.attribute, '')
            return

        filePath = filePath.replace('\\','/')

        print('update {} {}'.format(self.attribute, filePath))
        #folders
        if self.mode in [2,3]:
            if filePath[-1] == ':':
                filePath += '/'
            self._parent.folder = ''
            self._parent.name = filePath

            print('folder: "{}"'.format(filePath))
            #update attributes and textfield
            setattr(self._parent, self.attribute, filePath)
            pm.textField(self.textField, e = True, text = filePath)

        #Files
        else:             
            filePath = filePath.replace(self._parent._parent.folder + '/', '')

            if filePath[0] in ['\\', '/'] and len(filePath) > 1:
                filePath = filePath[1:]
            if filePath[-1] in ['\\', '/']:
                filePath = filePath[:-1]
                
            self._parent.name = os.path.basename(filePath).split('.')[0]   

            #is folder is part of filePath       
            if '/' in filePath or '//' in filePath or ':' in filePath:
                self._parent.folder = os.path.dirname(filePath)
            else:
                self._parent.folder = ''

            #set filePath, or folder name if folder mode
            filePath = os.path.join(str(self._parent.folder), str(self._parent.name)).replace('\\','/')
            if not self.mode in [2,3]:
                filePath += '.' + self.fileType

            #update textfield with relative path
            pm.textField(self.textField, e = True, text = filePath)

            if ':' not in filePath and '//' not in filePath[:min(len(filePath), 2)]:
                filePath = os.path.join(self._parent._parent.folder, filePath).replace('\\','/')
            
            print('filePath: "{}"'.format(filePath))
            #update attributes
            setattr(self._parent, self.attribute, filePath)


class nodeData(object):
    def __init__(self, *args, **kwargs):
        '''Base Node Data Class, stores python data in maya node attributes'''
        object.__init__(self)
        if not hasattr(self, '_nodeType'):
            self._nodeType = 'renderLayer'

        if not hasattr(self, '_nodeName'):
            self._nodeName = 'dataNode'
        
        if not hasattr(self, '_node'):
            self._node = None
        
        if not self.__dict__.get('_nodeType'):
            self._nodeType = 'renderLayer'

        if not self.__dict__.get('_node') or not str(self.__dict__.get('_node')):
            self.check(do = True)

        if not hasattr(self, 'currentFile'):
            self.currentFile = mc.file(q = True, sn = True)

        if not hasattr(self, 'exclude'):
            self.exclude = ''

        for attr in pm.listAttr(self._node, ud = True):
            object.__setattr__(self, attr, pickle.loads(self._node.getAttr(attr).encode()))

        for k,v in kwargs.items():
            setattr(self, k, v)


    def save(self):
        for k,v in self.__dict__.items():
            setattr(self, k, v)

    def delete(self):
        if mc.objExists(str(self._node)):
            pm.delete(self._node)


    def check(self, do = False):
        if not do:
            return
        if not self.__dict__.get('_node'):
            node = (pm.ls(pm.ls(self._nodeName, type = self._nodeType)) or [None])[0]
            if not node:
                node = pm.createNode(self._nodeType, ss = True, name = self._nodeName)
            self._node = node
            self._nodeName = node.name()



    def __getstate__(self):
        result = {}
        for k,v in self.__dict__.items():
            if hasattr(v, '__call__'):
                continue
            if issubclass(type(v), pm.general.PyNode):
                result['pyNode_' + k] = str(v)
            else:
                result[k] = v
        return result
    

    def __setstate__(self, result):
        for k,v in result.items():
            if hasattr(v, '__call__'):
                continue
            if 'pyNode_' in k:
                object.__setattr__(self, k.split('pyNode_')[-1], (pm.ls(v) or [None])[0])
            else:
                object.__setattr__(self, k, v)

        #self.save()


    def __getattribute__(self, attr):
        value = object.__getattribute__(self, attr)
        if hasattr(value, '__call__') or '__' in attr or attr in ['_node', '_nodeName', '_nodeType']:
            return value
        
        self.check()
        if not mc.objExists('{}.{}'.format(self._node, attr)):
            return None
        return pickle.loads(self._node.getAttr(attr).encode())


    def __getattr__(self, attr):
        return self.__getattribute__(attr)


    def __setattr__(self, attr, value):
        object.__setattr__(self, attr, value)
        if hasattr(value, '__call__') or '__' in attr or attr in ['_node', '_nodeName', '_nodeType']:
            return   

        self.check()
        if not mc.objExists('{}.{}'.format(self._node, attr)):
            pm.addAttr(self._node, ln = attr, dt = 'string')
        self._node.setAttr(attr, pickle.dumps(value, 0).decode())


    def __delattr__(self, attr):
        if mc.objExists('{}.{}'.format(self._node, attr)):
            pm.deleteAttr('{}.{}'.format(self._node, attr))
        if hasattr(self, attr):
            object.__delattr__(self, attr)
    
    

#------------------------------------------------------------------------------#
# Export Window
#------------------------------------------------------------------------------#


class AnimExporterUI(nodeData):
    _nodeName = 'AnimExporterUI'
    _nodeType = 'renderLayer'
    def __init__(self, *args, **kwargs):    
        if not hasattr(self, '_nodeName'):    
            self._nodeName = 'AnimExporterUI'
        
        type(self).__bases__[0].__init__(self, *args, **kwargs)
        if not hasattr(self, 'width'):
            self.width = 600
        if not hasattr(self, 'height'):
            self.height = 300
        if not hasattr(self, 'separatorHeight'):
            self.separatorHeight = 15
        if not hasattr(self, 'numExports'):
            self.numExports = 0
        if not hasattr(self, 'scrollAmount'):
            self.scrollAmount = 0
        if not hasattr(self, 'playblastOnExport'):
            self.playblastOnExport = 1
        if not hasattr(self, 'playblastCameras'):
            self.playblastCameras = ''
        if not hasattr(self, 'exclude'):
            self.exclude = ''

        self.__batch__ = kwargs.get('batch')

        if not hasattr(self, 'folder'):
            self.folder, name = getFolderFile()
        self.folderText = None
        self.scrollLayout = None

        if mc.window(self._nodeName + str(0) , exists = True):
            mc.deleteUI(self._nodeName + str(0))

        if 'maya' == os.path.basename(sys.executable).lower().split('.')[0] and not kwargs.get('batch'):
            self.makeWindow()

    
    def getExports(self):
        exports = {}
        count = 0
        for k,v in self.__dict__.items():
            name = (re.findall('export[0-9]+', k) or [None])[0]
            if name:
                if not exports.get(name):
                    index = int(name[6:])
                    exports[name] = export(_parent = self, 
                                           _index = index)
                    count += 1
                attr = k.replace(name, '')
                if attr and '_' not in attr:
                    setattr(exports[name], attr, v) 

        indexSort = lambda x: x._index
        result = sorted(exports.values(), key=indexSort)
        self.numExports = len(result)
        return result
    
    
    def makeWindow(self):
        if not (pm.window(self._nodeName + str(0), exists=True)):
            window = pm.window(self._nodeName + str(0), 
                               title = 'Ark Animation Exporter - Version: {} : {}'.format(__version__, SCRIPT_TIME_STRING), 
                               resizeToFitChildren = True)
            windows = (window, window, window)
            cmd = 'print(\"delete {}\"); import maya.cmds as mc; [mc.deleteUI(\"{}\") if (mc.window(\"{}\", exists=True)) else None];'.format(*windows)
            pm.scriptJob(runOnce = True, event = ['deleteAll', cmd], kws = True)
            pm.scriptJob(runOnce = True, event = ['NewSceneOpened', cmd], kws = False)
            pm.scriptJob(runOnce = True, event = ['SceneOpened', cmd], kws = False)

        else:
            return

        
        mainColumn = pm.columnLayout("mainColumn", 
                                     adjustableColumn = True,
                                     w = self.width)


        #Choose Folder
        if not isArk2():
            browseTextField(label = 'Folder',
                            title = 'Browse for Folder', 
                            message = 'Choose Folder',
                            mode = 3,
                            fileType = '',
                            attribute = 'folder',
                            parent = self)
        else:
            self.folder = (os.path.dirname(mc.file(q=True,sn=True)) or self.folder)            
            self.folderText = pm.text('FolderText', 
                                      label = 'Folder: {}'.format(self.folder), 
                                      parent = mainColumn)


        #add remove all        
        third = int(self.width / 3.0)
        AddRemoveLayout = pm.rowColumnLayout(nc=3, cw=[(1,third), (2,third), (3,third)],
                                             adjustableColumn = True,
                                             parent = mainColumn)

        pm.button(label = "Add Export", 
                  command = partial(self.exportAdd, prompt = True), 
                  annotation = 'Add Export',
                  parent = AddRemoveLayout)
                     
        pm.button(label = "Remove All", 
                  command = self.exportRemoveAll, 
                  annotation = 'Remove All',
                  parent = AddRemoveLayout)

        pm.button(label = "Auto Populate", 
                  command = self.exportAutoPopulate, 
                  annotation = 'Auto Populate',
                  parent = AddRemoveLayout)

        for n in range(3):            
            pm.separator(height = 5, 
                        style = "none", 
                        parent = AddRemoveLayout)

        pm.button(label = "Export All", 
                  command = self.exportAll, 
                  annotation = 'Export All',
                  parent = AddRemoveLayout)

        

        playCameraButton = pm.button("playblastCamerasButton", 
                                     label = 'Override Playblast Cameras >', 
                                     command = str)
        playCameraText = pm.textField("playblastCamerasText",   
                                      changeCommand = partial(setattr, self, 'playblastCameras'),
                                      textChangedCommand = partial(setattr, self, 'playblastCameras'),
                                      annotation = 'Playblast Cameras', text = self.playblastCameras)
        pm.button(playCameraButton, e = True, 
                  command = partial(setSelectionToTextField, 
                                    self,
                                    attribute='playblastCameras', 
                                    camera=True,
                                    textField=playCameraText))

        pm.separator(height = self.separatorHeight, 
                    style = "none", 
                    parent = AddRemoveLayout)

        pm.checkBox(label = "Playblast on Export", 
                    value = self.playblastOnExport,
                    cc = partial(setattr, self, 'playblastOnExport'),
                    annotation = 'Playblast on Export',
                    parent = AddRemoveLayout)

        for n in range(2):            
            pm.separator(height = self.separatorHeight, 
                        style = "none", 
                        parent = AddRemoveLayout)


        nr = pm.rowColumnLayout(AddRemoveLayout, q=True, nr=True)
        nc = pm.rowColumnLayout(AddRemoveLayout, q=True, nc=True)
        pm.rowColumnLayout(AddRemoveLayout, 
                           e=True, 
                           rs=[(n,5) if n>1<nr else (n,0) for n in range(1,nr+1)], 
                           cs=[(n,5) if n>1<nc else (n,0) for n in range(1,nc+1)],)
        #list exports
        #self.initDynamicLayout(mainColumn)
        self.initDynamicLayout(window)


        mc.showWindow(window)
        return window
        

    def initDynamicLayout(self, 
                          mainColumn='mainColumn',
                          scrollAmount=None):     

        # Save Scroll Amount if window is open unless its given as an arg
        if self.scrollLayout and pm.scrollLayout(self.scrollLayout, q=True, exists=True):
            self.scrollAmount = scrollAmount or list(map(int,pm.scrollLayout(self.scrollLayout, q=True, scrollAreaValue=True)))[0]
        else:            
            self.scrollAmount = scrollAmount or self.scrollAmount or 0

        if pm.columnLayout('dynamicLayout', q=True, exists=True):
            mc.deleteUI('dynamicLayout')
                 
        exports = self.getExports()
        dynamicLayout = pm.columnLayout('dynamicLayout',
                                        width = self.width * 0.8,
                                        adjustableColumn = True,
                                        parent = mainColumn)

        height = pm.columnLayout(dynamicLayout, q = True, height = True)
        scrollLayout = pm.scrollLayout('scrollLayout',
                                       parent = dynamicLayout,
                                       height = min(600, max(height, self.numExports * 300)),
                                       childResizable = True)

        self.scrollLayout = scrollLayout
        scrollColumn = scrollLayout

        pm.text('ExportsText', 
                label = 'Exports: ' + str(self.numExports), 
                parent = scrollColumn)
        
        for i, item in enumerate(exports):
            print('Loading Export {} of {}'.format(i+1, self.numExports))
            item.initDynamicLayout(self, i, scrollColumn)
            item._write = True
            item.save()
        
        # retrieve scrollAmount
        #print(self.scrollAmount)
        cmd = 'import maya.cmds as mc;mc.scrollLayout("{}",edit=True,scrollByPixel=("down",{}));'.format(self.scrollLayout,
                                                                                                         self.scrollAmount)
        #print(cmd)
        mc.evalDeferred(cmd)

     
    def reorderUp(self, i, *args, **kwargs):
        self.reorder(i, -1)
        
    def reorderDown(self, i, *args, **kwargs):
        self.reorder(i, 1)

    def reorder(self, i, direction):
        print('reorder {}.{} of {}'.format(i+1, i+1+direction, self.numExports))
    
        if not (self.numExports > (i + direction) > -1):
            return     

        exports = self.getExports()   
        a, b = exports[i], exports[i+direction]   

        print('reorder start {} {}'.format(a._index+1, a.exportPath))

        aData, bData = a.__getstate__(), b.__getstate__()
        a.__setstate__(bData)
        b.__setstate__(aData)
        a._index = i
        b._index = i+direction
        a._write, b._write = True, True
        a.save()
        b.save()

        print('reorder end {} {}'.format(b._index+1, b.exportPath))

        self.initDynamicLayout()


    def exportAdd(self, *args, **kwargs):
        print('exportAdd {}'.format(self.numExports))
        prompt = kwargs.get('prompt')
        scrollColumn = (kwargs.get('scrollColumn') or 'scrollColumn')
        
        folder, name = getFolderFile()
        folder = self.folder
        start = pm.playbackOptions(q = True, minTime = True)
        end = pm.playbackOptions(q = True, maxTime = True)
        
        layers = getCurrentAnimLayers()
        if layers:
            exportLayers = [x for x in layers if isExportLayer(x)]
            if exportLayers:
                selected = [x for x in exportLayers if pm.animLayer(x, q = True, selected = True)]
                current = (selected or exportLayers)[0]
                name, end = getLayerNameFrame(current)
                start = 0

        if prompt:
            name = textDialog(title = 'New Animation',
                               message = 'Enter Animation Name',
                               text = name)
            if not name:
                pm.warning('New Animation Cancelled')
                return
            if '/' in name or '\\' in name:
                folder = os.path.dirname(name)
                name = os.path.basename(name).split('.')[0]

        name = kwargs.get('name') or name
        exportPath = os.path.join(folder, name + '.fbx').replace('\\','/')
        new = export(exportPath = exportPath, 
                     root=kwargs.get('root') or defaultRoot(),
                     start = start, end = end,
                     layers = list(map(str,layers)),
                     layersLeaveAlone = False,
                     _parent = self,
                     _index = self.numExports)
        new._write = True
        new.save()
        self.numExports += 1
        print('\tNew Export {} of {}'.format(new._index, self.numExports))
        
        self.initDynamicLayout(scrollAmount=self.numExports*500)
        #new.initDynamicLayout(self, self.numExports)
        return new


    def exportAutoPopulate(self, *args, **kwargs):
        print('exportAutoPopulate')

        if self.numExports:
            if confirmDialog(title = 'Confirm Replace All Exports', 
                            message = 'Replace All Exports From Animation Layers?'):   
                for item in self.getExports():
                    item.delete()                    

        allRoots = defaultRoot(allRoots=True)

        layers = [x for x in pm.ls(type = 'animLayer') if isExportLayer(x)]
        if not layers:
            folder, basename = getFolderFile()
            for root in allRoots:
                print('No Export Animation Layers Found')
                rigExportName = basename
                if len(allRoots) > 1:
                    rigExportName = '_'.join([x for x in [basename,getRigName(root)] if x])
                new = self.exportAdd(prompt=False, 
                                     name=rigExportName,
                                     root=root)
            self.initDynamicLayout()
            return

        self.folder, name, ext = animFolderFilePrefix()

        self.numExports = 0
        for root in allRoots:
            for i, layer in enumerate(map(str,layers)):
                name, end = getLayerNameFrame(layer)
                if len(allRoots) > 1:
                    name = '_'.join([x for x in [name, getRigName(root)] if x])
                exportPath = os.path.join(self.folder, name + '.' + ext).replace('\\','/')
                print('exportpath "{}"'.format(exportPath))
                new = export(exportPath = exportPath, 
                            start = 0, end = end,
                            root=root,
                            layers = [layer],
                            _parent = self,
                            _index = self.numExports)

                new._write = True
                new.save()
                self.numExports += 1
            
        print('numExports {}'.format(self.numExports))
        self.initDynamicLayout()


    def exportRemove(self, index, *args, **kwargs):
        print('exportRemove {} {}'.format(index+1, self.numExports))


        if self.numExports:
            exports = self.getExports()
            item = exports[index]
            message = 'Remove Export ' + str(index+1) + ' ' + item.name + '?'
            if confirmDialog(title = 'Confirm Remove Export',  message = message): 
                data = {i:exports[i].__getstate__() for i in range(index+1, self.numExports)}   
                exports[-1].delete()          
                for i in range(index+1, self.numExports):
                    data[i]['_index'] -= 1
                    exports[i].__setstate__(data[i])
                    exports[i]._write = True
                    exports[i].save()
                self.numExports -= 1
                self.initDynamicLayout()


    def exportRemoveAll(self, *args, **kwargs):
        print('exportRemoveAll {}'.format(self.numExports))

        if not self.numExports:
            return

        if confirmDialog(title = 'Confirm Remove All Exports', 
                         message = 'Remove All Exports?'):
            for item in self.getExports():
                item.delete()
            self.numExports = 0
            self.initDynamicLayout()


    def exportAll(self, *args, **kwargs):

        # get the exports
        exports = self.getExports()
        if not exports:
            pm.warning('arkAnimExporterUI exportAll : No Exports Found!')
            return

        # check for override
        force_playblast = kwargs.get('playblast')

        # See if each clip should be playblasted individually, 
        # if not then just playblast once at the end
        if force_playblast == False:
            do_playblast = False
        else:
            do_playblast = (force_playblast or (self.playblastOnExport and not self.__batch__))
            
        playblast_each = do_playblast and not self.playblastCameras

        # print('do_playblast', do_playblast)
        # print('playblast_each', playblast_each)

        # do the exports
        for item in exports:
            item.export(None, playblast=playblast_each)

        # if playblast on export but has override cameras only playblast each overridde camera once
        if do_playblast and not playblast_each and self.playblastCameras:
            exports[0].playblast(playblast=True)



    def updateFolder(self, *args, **kwargs):
        if not self.folderText:
            return
        self.folder = (os.path.dirname(mc.file(q=True,sn=True)) or self.folder)            
        pm.text(self.folderText, 
                e=True,
                label = 'Folder: {}'.format(self.folder))



#------------------------------------------------------------------------------#
# Export Item
#------------------------------------------------------------------------------#

class export(object):     
    def __init__(self, *args, **kwargs):
        '''Individual export settings''' 
        object.__init__(self)
        #type(self).__bases__[0].__init__(self, *args, **kwargs)  

        self._write = False
        self._parent = kwargs.get('_parent')
        self._index = 0
        if kwargs.get('_index') != None:
            self._index = kwargs.get('_index')      

        self._UI = {} 
        self.layers = []
        self.layersLeaveAlone = False
        self.RGBColor = [random.randrange(0,255) * (1.0/256) for x in range(3)]
        self.width = 600
        self.root = ''
        self.start = pm.playbackOptions(q = True, minTime = True)
        self.end = pm.playbackOptions(q = True, maxTime = True)
        self.folder = ''
        folder, self.name = getFolderFile()
        self.relativePath = os.path.join(self.folder, self.name + '.fbx').replace('\\','/')
        self.exportPath = os.path.join(self._parent.folder, self.relativePath).replace('\\','/')
        self.folder = os.path.dirname(self.exportPath)
        self.name = os.path.basename(self.exportPath).split('.')[0]
        self.exportMesh = False
        self.exportBlendshapes = False
        self.exclude = 'FACIAL_'

        for k,v in kwargs.items():
            setattr(self, k, v)            
    

    def save(self):
        if self._write:
            for k,v in self.__dict__.items():
                setattr(self, k, v)

    
    def __setattr__(self, attr, value):

        object.__setattr__(self, attr, value)
        if attr in ['_index', '_write'] or not self._write or '_' in attr or hasattr(value, '__call__'):
            return
        if self._parent:
            self._parent.updateFolder()

        if hasattr(self, '_index'):
            setattr(self._parent, 'export' + str(self._index) + attr, value)


    def __getattribute__(self, attr):
        value = object.__getattribute__(self, attr)
        if attr in ['_index', '_write'] or not self._write or '_' in attr or hasattr(value, '__call__'):
            return value
        return getattr(self._parent, 'export' + str(self._index) + attr)


    def delete(self):
        for k,v in self.__dict__.items():
            if '_' in k or hasattr(v, '__call__'):
                continue
            delattr(self._parent, 'export' + str(self._index) + k)
        self._parent.numExports -= 1

            

    def __getstate__(self):
        result = {}
        for k,v in self.__dict__.items():
            if hasattr(v, '__call__'):
                continue
            if issubclass(type(v), pm.general.PyNode):
                result['pyNode_' + k] = str(v.longName())
            else:
                result[k] = v
        return result


    def __setstate__(self, result):
        for k,v in result.items():
            if hasattr(v, '__call__'):
                continue
            if 'pyNode_' in k:
                object.__setattr__(self, k.split('pyNode_')[-1], (pm.ls(v) or [None])[0])
            else:
                object.__setattr__(self, k, v)
                

    def initDynamicLayout(self, 
                          parent, 
                          index, 
                          scrollColumn='scrollColumn'):        

        self.width = self._parent.width

        self._main = pm.columnLayout(width = self.width,
                                     adjustableColumn = True,
                                     parent = scrollColumn)


        #Export Path
        textColumn = pm.rowColumnLayout(nc=2, cw=[(1,5), (2,self.width - 5)],        
                                        adjustableColumn = True,
                                        parent = self._main)

        #print('check')
        #for item in self.__dict__.keys():
        #    print('\t', item)

        pm.text('ExportsText' + str(index), 
                label = str(index+1),
                bgc = self.RGBColor,
                parent = textColumn,
                recomputeSize = True)
        pm.separator(height = self._parent.separatorHeight * 2, 
                     style = "none",
                     bgc = self.RGBColor,
                     parent = textColumn)

        browseColumn = pm.columnLayout(width = self.width,
                                       adjustableColumn = True,
                                       parent = self._main)

        browseTextField(label = 'File Path',
                        title = 'Choose FBX File Name', 
                        message = 'Browse for FBX File Name',
                        mode = 0,
                        fileType = 'fbx',
                        attribute = 'exportPath',
                        parent = self)

        #root bone
        rootColumn = pm.rowColumnLayout(nc=3, cw=[(1,self.width * 0.1), 
                                                  (2,self.width * 0.4), 
                                                  (3,self.width * 0.4)],   
                                        adjustableColumn = True,
                                        parent = self._main)

        rootButton = pm.button("rootButton" + str(index), 
                               label = 'Root >', 
                               annotation = 'Set to currently selected root joint',
                               command = str)
        rootText = pm.textField ("rootText" + str(index),   
                                changeCommand = partial(setattr, self, 'root'),
                                textChangedCommand = partial(setattr, self, 'root'),
                                annotation = 'Root', text = self.root)
        pm.button(rootButton, e = True, 
                  command = partial(setSelectionToTextField, 
                                    self,
                                    attribute ='root', 
                                    textField = rootText))

        ExcludeLayout = pm.rowLayout(numberOfColumns=2, adjustableColumn = True, parent = rootColumn)
        pm.text(label="Exclusion Keyword: ", parent=ExcludeLayout)
        self.exclusion_textField = pm.textField('exclusion_textField', 
                                                text=self.exclude, 
                                                parent=ExcludeLayout,
                                                changeCommand = partial(setattr, self, 'exclude'),
                                                textChangedCommand = partial(setattr, self, 'exclude'))

        #Update Animation Layers
        layersColumn = pm.rowColumnLayout(nc=3, cw=[(1,int(self.width * 0.2)), 
                                                    (2,int(self.width * 0.6)),                                                    
                                                    (3,int(self.width * 0.2)),],
                                          adjustableColumn = True,
                                          parent = self._main)

        layersButton = pm.button("layersButton" + str(index), 
                                 label = 'Current Anim Layers >',
                                 annotation = 'Set to currently enable Animation Layers')
        
        layersText = pm.textField ("layersText" + str(index),  
                                   annotation = 'layers', 
                                   text = ','.join(self.layers))

        layersLeaveAloneBool = pm.checkBox("layersLeaveAloneBool" + str(index),  
                                           label = 'Leave Layers Alone',
                                           annotation = 'Leave Layers Settings as is on Export',
                                           v = self.layersLeaveAlone,
                                           cc = partial(setattr, self, 'layersLeaveAlone'))

        layersCmd = partial(self.setLayers, layersText = layersText)
        pm.button(layersButton, edit = True, command = layersCmd)
        pm.textField(layersText, edit = True, changeCommand = layersCmd)
        pm.textField(layersText, edit = True, textChangedCommand = layersCmd)

        #frame range
        fifth = int(self._parent.width / 5.0)
        frames = pm.rowColumnLayout(nc=5, cw=[(1,fifth), (2,fifth), (3,fifth), (4,fifth), (5,fifth)], 
                                    adjustableColumn = True,
                                    parent = self._main)

        
        frameCurrent = pm.button(label = 'Current Frame Range >', 
                                 annotation = 'Set To Current Frame Range')
                                             
        pm.text('StartFrame' + str(index), 
                label = 'Start Frame',
                parent = frames)

        startText = pm.textField ("startText" + str(index),
                                  annotation = 'Start Frame', 
                                  text = str(self.start))

        pm.text('EndFrame' + str(index), 
                label = 'End Frame',
                parent = frames)

        endText = pm.textField ("endText" + str(index), 
                                annotation = 'End Frame', 
                                text = str(self.end))
        

        setStartCmd = partial(self.setFrameAttribute, attribute = 'start')
        pm.textField(startText, edit = True, changeCommand = setStartCmd)
        pm.textField(startText, edit = True, textChangedCommand = setStartCmd)
        
        setEndCmd = partial(self.setFrameAttribute, attribute = 'end')     
        pm.textField(endText, edit = True, changeCommand = setEndCmd)
        pm.textField(endText, edit = True, textChangedCommand = setEndCmd)



        pm.button(frameCurrent, 
                  edit = True, 
                  command = partial(self.setCurrentRange, 
                                    startText = startText, 
                                    endText = endText))

        #Export
        exportColumn = pm.rowColumnLayout(nc=6, cw=[(1,fifth), (2,fifth), (3,fifth), (4,fifth), (5,fifth)], 
                                          adjustableColumn = True,
                                          parent = self._main)

        exploreButton = pm.button("exploreButton" + str(index),
                                  label = 'Show In Explorer',
                                  annotation='Show FBX file in Windows Explorer if it exists',
                                  command = partial(self.explore))

        #Blend Shape Settings
        blenshapeColumn = pm.rowColumnLayout(nc=2, cw=[(1,fifth*0.01), (2,fifth*0.9)], 
                                             adjustableColumn = True)
        pm.separator(height = self._parent.separatorHeight, 
                     style = "none",
                     parent = blenshapeColumn)

        pm.checkBox(label='Blend Shapes', 
                    value=self.exportBlendshapes,
                    cc=partial(setattr, self, 'exportBlendshapes'),
                    annotation='Include Blend Shapes in Export',
                    parent = blenshapeColumn)
        pm.setParent('..')

        previewButton = pm.button("previewButton" + str(index),
                                  label = 'Preview Settings',
                                  annotation = 'Set Frame range and active Animation layers to match this export.',
                                  command = partial(self.preview))

        playblastButton = pm.button("playblastButton" + str(index),
                                    label = 'Playblast',
                                    annotation='Render Playblast',
                                    command = partial(self.playblast))

        exportButton = pm.button("exportButton" + str(index),
                                 label = 'Export',
                                 annotation='Export FBX',
                                 command = partial(self.export))
        


        # Add reorder buttons
        colLayout = pm.rowColumnLayout(nc = 4, 
                                       cw = [(1,235), (2,35), (3,35), (4,35)],
                                       adjustableColumn = True,
                                       parent = self._main,
                                       bgc = self.RGBColor)
        pm.separator(height = self._parent.separatorHeight, 
                     style = "none", 
                     parent = colLayout,
                     bgc = self.RGBColor)

        if (index == 0):
            pm.separator(height = self._parent.separatorHeight, 
                         style = "none", 
                         parent = colLayout)
        else:
            pm.button('reorderUp'+ str(index), 
                      label = u'▲', 
                      command = partial(self._parent.reorderUp, index))
        
        if (index >= (self._parent.numExports-1)):
            pm.separator(height = self._parent.separatorHeight, 
                         style="none",
                         parent = colLayout)
        else:
            pm.button('reorderDown'+ str(index), 
                      label = u'▼', 
                      command = partial(self._parent.reorderDown, index))
        
        pm.button('Delete' + str(index),
                  label = u'X',
                  command = partial(self._parent.exportRemove, index))                    


    def explore(self, *args, **kwargs):
        filePath = self.exportPath
        if not os.path.exists(filePath):
            filePath = os.path.dirname(filePath)

        os.system('explorer.exe/select,"{}"'.format(filePath.replace('/','\\')))


    def setLayers(self, text = None, layersText = None):
        if text:
            layers = [x for x in re.findall('[a-zA-Z0-9_\:]+', text) if x]           
        else:
            layers = list(map(str,getCurrentAnimLayers()))

        
        print('Set layers {}'.format(','.join(self.layers)))
        self.layers = layers
        pm.textField(layersText, edit = True, text = ','.join(self.layers))
    

    def setFrameAttribute(self, *args, **kwargs):
        attribute = kwargs.get('attribute')
        frame = args[0]

        print('Set {} {}'.format(attribute, frame))
        try:
            frame = float(frame)
        except:
            return
        setattr(self, attribute, frame)

    
    def setCurrentRange(self, *args, **kwargs):
        startText = kwargs.get('startText')
        endText = kwargs.get('endText')
        
        self.start = pm.playbackOptions(q = True, minTime = True)
        self.end = pm.playbackOptions(q = True, maxTime = True)

        print('Set Current Range: {} : {}'.format(self.start, self.end))
        pm.textField(startText, edit = True, text = str(self.start))
        pm.textField(endText, edit = True, text = str(self.end))


    def preview(self, *args, **kwargs):
        pm.select(self.root, r = True)
        pm.playbackOptions(minTime = self.start)
        pm.playbackOptions(maxTime = self.end)
        if self.layers and not self.layersLeaveAlone:
            for layer in pm.ls(type = 'animLayer'):
                off = not (str(layer) in self.layers)
                if str(layer) != 'BaseAnimation': 
                    layer.setAttr('mute', off)
                layer.setAttr('lock', off)    
        ml.eval('updateEditorFeedbackAnimLayers("AnimLayerTab");')


    def playblast(self, *args, **kwargs):
        self.preview()

        filePath = mc.file(q=True, sn=True)
        if not filePath:
            pm.warning('File Not Saved!')
            return
        folder = os.path.dirname(filePath)
        kwargs['name'] = kwargs.get('name', self.name)
        kwargs['root'] = self.root
        kwargs['cameras'] = self._parent.playblastCameras or None
        playblast(*args,**kwargs)
    

    def export(self, *args, **kwargs):
        '''Export Animation and remove namespaces'''

        hisort = lambda x: len(str(x.longName()).split('|'))
        root = (sorted(pm.ls(self.root), key=hisort) or [None])[0]
        print('Roots', sorted(pm.ls(self.root), key=hisort))

        if not root:
            pm.warning('Anim Exporter Could not find Root "{}"'.format(self.root))
            return
     
        # get mainControl and check if there is boneModSkeleton attribute,
        # if true, set it back to 0 for export
        mainControl = pm.listConnections(root+'.scale', source=True, destination=False)
        if mainControl and pm.attributeQuery('boneModSkeleton', node=mainControl[0].name(), exists=True):
            boneModSkeletonAttr = pm.getAttr(mainControl[0].name()+'.boneModSkeleton')
            pm.setAttr(mainControl[0].name()+'.boneModSkeleton',0)
            
        # if playblast kwarg is False dont playblast, 
        # if true, playblast, 
        # if None defer to parent playblastOnExport setting
        if kwargs.get('playblast') != False and (self._parent.playblastOnExport or kwargs.get('playblast')):
            self.playblast()

        # get export path
        self.folder = self.folder.replace(self._parent.folder, '')
        folder = self.folder
        if ':' not in folder:
            folder = os.path.join(self._parent.folder, folder).replace('\\','/')
        
        if not os.path.exists(folder):
            print('Folder Missing "{}"'.format(folder))
            split = os.path.split(folder)
            for i in range(len(split)):
                check = os.path.join(*split[:i+1]).replace('\\','/')
                if not os.path.exists(check):
                    print(' - making folder {}'.format(check))
                    os.mkdir(check)

        self.exportPath = os.path.join(folder, self.name + '.fbx').replace('\\','/')

        # set blendshape export bool for included meshes in export
        blendshapesBool = str(bool(self.exportBlendshapes)).lower() if self.exportMesh else 'false'

        #store current settings
        OS = pm.ls(sl = True)
        start = pm.playbackOptions(q = True, minTime = True)
        end = pm.playbackOptions(q = True, maxTime = True)
        layerSettings = {x:(pm.animLayer(x, q = True, mute = True), pm.animLayer(x, q = True, lock = True)) for x in pm.ls(type = 'animLayer')}

        # Scene Settings
        fps = getFPS()
        ml.eval(f'FBXResamplingRate -v {fps}')

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
        ml.eval(f'FBXProperty Export|AdvOptGrp|Collada|FrameRate -v {fps}')

        # Geometry Settings
        ml.eval('FBXProperty Export|IncludeGrp|Geometry|SelectionSet -v false')
        ml.eval('FBXProperty Export|IncludeGrp|Geometry|AnimationOnly -v false')
        ml.eval('FBXProperty Export|IncludeGrp|Geometry|SmoothingGroups -v false')
        ml.eval('FBXProperty Export|IncludeGrp|Geometry|expHardEdges -v false')
        ml.eval('FBXProperty Export|IncludeGrp|Geometry|TangentsandBinormals -v {}'.format(blendshapesBool))
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
        ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameStart -v {}'.format(self.start))
        ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameEnd -v {}'.format(self.end))
        ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|BakeFrameStep -v 1')
        ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|ResampleAnimationCurves -v true')
        ml.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation|HideComplexAnimationBakedWarning -v true')
        ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation -v {}'.format(blendshapesBool))
        ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|Skins -v {}'.format(blendshapesBool))
        ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|Shape -v {}'.format(blendshapesBool))
        ml.eval('FBXProperty Export|IncludeGrp|Animation|Deformation|ShapeAttributes -v {}'.format(blendshapesBool))
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
        pm.mel.FBXExportIncludeChildren('-v', False)



        #some overrides for Unreal Upaxis
        ml.eval('FBXExportUpAxis {}'.format(mc.upAxis(q = True, axis = True)))  
        #print('UpAxis FBX'.format(ml.eval("FBXExportUpAxis -q")))
        

        # find blendshapes if self.exportBlendshapes
        extras = []
        if self.exportBlendshapes:
            # to save space isnted of exporting meshes make sure blend shape weight attributes are attached to matching attributes on root bone.
            if not self.exportMesh:
                attachBlendShapeCurvesOnRoot(root)
                
            # otherwise export meshes for any blendshapes
            else:
                meshes = list(set(pm.listHistory(pm.listRelatives(root,ad=True,type='joint') + [root], f=True, type='mesh')))
                blendShapes =  list(set(pm.listHistory(meshes,type='blendShape')))
                if not blendShapes:
                    pm.warning('Animation Export Warning: No blend shapes found for "{}"'.format(self.name))
                else:
                    extras.extend(set(blendShapes + list(set(pm.listHistory(blendShapes,type='mesh')))))
            

        # Set layer settings
        pm.select(extras + [root], r=True)
        if self.layers:
            layer_str = {True:'On', False:'Off'}
            # use default animation configuration. 
            if self.layersLeaveAlone:
                for layer, settings in layerSettings.items():
                    if bool(layer.getAttr('mute')) != bool(settings[0]) or bool(layer.getAttr('lock')) != bool(settings[1]):
                        print('Setting Anim Layer {} -> {}'.format(layer, layer_str[not bool(settings[0])]))
                        if str(layer) != 'BaseAnimation': 
                            layer.setAttr('mute', settings[0])
                        layer.setAttr('lock', settings[1])

            # enable only this animations layers
            else:
                for layer in pm.ls(type = 'animLayer'):
                    off = not (str(layer) in self.layers)   
                    print('Setting Anim Layer {} -> {}'.format(layer, layer_str[off]))
                    if str(layer) != 'BaseAnimation': 
                        layer.setAttr('mute', off)
                    layer.setAttr('lock', off)      

        pm.playbackOptions(minTime = self.start)
        pm.playbackOptions(maxTime = self.end)
                
        if os.path.exists(self.exportPath) and not os.access(self.exportPath, os.W_OK):
            message = 'P4 Check Out Needed: Overwrite Non-Writeable File "{}"?'.format(os.path.basename(self.exportPath))
            if confirmDialog(title = 'Confirm', message = message):
                os.chmod(self.exportPath, stat.S_IWRITE)
            else:
                return

        root_hi = pm.listRelatives(self.root, ad=True, type=pm.nt.Joint) + [pm.PyNode(self.root)]        
        # Remove joints indicated for exclusion by user 
        if self.exclude:
            pm.select([x for x in root_hi if not self.exclude in x.name()], r=True)
        else: 
            pm.select(root_hi, r=True)

        ml.eval('FBXExport -s 1 -f "{}"'.format(self.exportPath))
        print('Exported: "{}"'.format(self.exportPath))
        print(' - Extras:' + str(extras))
        fbxCleanup(self.exportPath, root=str(root), keep_list=extras)

        #restore saved settings
        if OS:
            pm.select(OS, r = True)

        pm.playbackOptions(minTime = start)
        pm.playbackOptions(maxTime = end)
        for layer, settings in layerSettings.items():
            layer.setAttr('mute', settings[0])
            layer.setAttr('lock', settings[1]) 
        
        if mainControl and 'boneModSkeletonAttr' in locals():
            pm.setAttr(mainControl[0].name()+'.boneModSkeleton',boneModSkeletonAttr)

