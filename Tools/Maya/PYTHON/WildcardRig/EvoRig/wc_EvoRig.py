    # coding=utf-8

"""
Use this as the shelf command:

import wc_EvoRig
reload(wc_EvoRig)
wc_EvoRig.removeWindows()
wc_EvoRig.AutoRigUI()


"""

import os
import sys
import copy

from math import *

import traceback
import json
import pickle
from collections import OrderedDict
from functools import partial
from inspect import getsourcefile


import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
    reload = __import__('importlib').reload

if 2 < sys.version_info.major:
    xrange = range

# Current Script path, using more robust method than __file__ which is sometimes missing
script_path = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))

# Find wildcardRig path
rig_path = os.path.dirname(script_path)

# Find wildcardAnim path
anim_path = '{}/wildcardAnim'.format(os.path.dirname(rig_path))

# Add relevant paths to sys path
for path in [script_path, rig_path, anim_path]:
    if path in sys.path:
        del sys.path[sys.path.index(path)]
    sys.path.insert(0, path)

import wc_shapes as sh
reload(sh)

import ctrls
reload(ctrls)

import mb_rig_utilities as util
reload(util)
is_iterable = util.is_iterable

import mb_MirrorAnimation as mirror
reload(mirror)
import cr_MakeEngineIK
reload(cr_MakeEngineIK)
import MakeFace
reload(MakeFace)
import MakeRoot
reload(MakeRoot)
import mb_MakeAdditiveSpline
reload(mb_MakeAdditiveSpline)

util.debugging = True

__author__ = 'Michael Buettner, Ethan McCaughey, Corey Ross, Mic Marvin, Jessica Tung'
__version__ = '1.15.0'  # <major>.<minor>.<revision>
rigControlSizeSlider = "rigControlSizeSlider"
splineCountSlider = "splineCountSlider"

windowName = "EvoRig"

fullFilePath = cmds.file(q=True, sn=True)
fileNameSplit = os.path.split(fullFilePath)
folderDir = fileNameSplit[0]
fileName = fileNameSplit[1]


# changeKeywordNames = ('changeKeywordTextone', 'changeKeywordTexttwo', 'changeKeywordTextthree','four','five','six')
# changeKeywordCommands = (changeKeywordTextone, changeKeywordTexttwo, changeKeywordTextthree, four, five, six)

def removeWindows():
    if (cmds.window(windowName + str(0), exists=True)):
        cmds.deleteUI(windowName + str(0))

def dockableAutoRig():
    dockControl = 'EvoRigUI'

    if cmds.workspaceControl(dockControl, exists=True):
        cmds.deleteUI(dockControl, control=True)

    dock = cmds.workspaceControl(
        dockControl,
        label='EvoRig',
        retain=False,
        floating=True,
        initialWidth=420,
        initialHeight=700
    )

    ui = AutoRigUI()
    ui.window = dock
    ui.mainLayout = None
    ui.dynamicLayout = None
    ui.initLayout()        
    ui.loadFromSceneSettings()

    return ui


class AutoRigUI(object):
    def __init__(self):
        self.rigName = "Rig"
        self.rigNameUI = None

        self.root = ''
        self.rootUI = None

        self.controlSize = 50
        self.controlSizeUI = None

        self.positionBasedColor = True
        self.positionBasedColorUI = None

        self.controlLayerNames = ['main', 'face']

        self.leftPrefix = 'l_'
        self.rightPrefix = 'r_'
        self.uiPath = ''
        self.uiShapePath = ''
        self.uiScriptPath =''
        self.applyShapeData = True
        self.applyShapeDataUI = None

        self.uiIndex = 0
        self.moduleTypes = ctrls.modules
        self.modules = [self.moduleTypes['Additive IK Spline'](keyword='spine', _expanded=False),
                        self.moduleTypes['IK/FK Leg'](keyword='thigh', _expanded=False),
                        self.moduleTypes['Additive IK Spline'](keyword='neck', _expanded=False),
                        self.moduleTypes['FK'](keyword='head', _expanded=False),
                        self.moduleTypes['FK'](keyword='tail', _expanded=False),
                        self.moduleTypes['FK'](keyword='toe', _expanded=False)]

        self.shapeData = []

        self.mainLayout = None
        self.dynamicLayout = None
        self.textFieldFilePath = None
        self.textFieldShapePath = None
        self.textFieldLeftPrefix = None
        self.textFieldRightPrefix = None
        self.boneModDataType = None
        self.boneModData = 'Human'
        self.boneModInfo = ''
        self.textFieldBoneModInfo = None
        self.collapsed = {}



    @property
    def defaultSettingsPath(self):
        fileName = cmds.file(q=True, sn=True)
        folderDir = os.path.dirname(fileName)
        fileName = os.path.basename(fileName).split('.')[0]
        return '{}/{}_EvoRig_settings.json'.format(folderDir, fileName)

    @property
    def sceneSettings(self):
        settings_name = 'EvoRigSceneSettings'
        sceneSettings = (pm.ls(settings_name) or [None])[0]
        if sceneSettings and cmds.nodeType(str(sceneSettings)) != 'renderLayer':
            try:
                pm.delete(sceneSettings)
            except:
                pm.warning('EvoRig Unable to delete invalid Scene Settings Node {}'.format(sceneSettings))
                sceneSettings = (pm.ls(settings_name + '*') or [None])[0]

        if not sceneSettings:
            pm.warning('EvoRig Settings Path not found in Scene. Using Default')
            sceneSettings = pm.createNode('renderLayer', name=settings_name, ss=True)
            pm.addAttr(sceneSettings, sn='uiPath', dt='string')
            sceneSettings.setAttr('uiPath', self.defaultSettingsPath)

        return sceneSettings

    def deleteSceneSettings(self):
        settings_name = 'EvoRigSceneSettings'
        sceneSettings = (pm.ls(settings_name) or [None])[0]
        if sceneSettings:
            pm.delete(sceneSettings)

    def loadFromSceneSettings(self):
        self.uiPath = self.sceneSettings.getAttr('uiPath')
        if not os.path.exists(self.uiPath):
            pm.warning('Evorig Saved Settings Path Not Found: "{}"'.format(self.uiPath))
            pm.warning(' - Trying Default Path Instead:       "{}"'.format(self.uiPath))
            self.uiPath = self.defaultSettingsPath

        if os.path.exists(self.uiPath):
            self.loadSettings()
        else:
            pm.warning('Evorig Settings Path Not Found: "{}"'.format(self.uiPath))

    def show(self):
        cmds.showWindow(self.window)

    def initDynamicLayout(self):
        layout = self.dynamicLayout
        if layout is not None:  # and (pm.rowColumnLayout(self.dynamicLayout, query=True, exists=True)):
            cmds.deleteUI(layout)

        self.dynamicLayout = pm.columnLayout(parent=self.scrollLayout)  # pm.rowColumnLayout(nc=2, cw=[(1,70), (2,270)],
        pm.text('keywordText', label='Modules: ' + str(len(self.modules)), parent=self.dynamicLayout)
        pm.separator(height=10, style="none", parent=self.dynamicLayout)
        # return

        mx = len(self.modules)
        for i, module in enumerate(self.modules):
            module.initDynamicLayout(self, index=i)

    def updateUI(self):
        # pm.intSliderGrp(self.moduleAmountSlider, edit=True, value = len(self.modules))
        self.initLayout()

    def initLayout(self):
        layout = self.mainLayout
        if layout is not None:  # and (pm.rowColumnLayout(self.dynamicLayout, query=True, exists=True)):
            cmds.deleteUI(layout)
            self.dynamicLayout = None  # Dynamic layout is a child, so it gets deleted with the main Layout
        
        
        
        mainScroll = pm.scrollLayout(parent=self.window)
        mainColumn = pm.columnLayout(adjustableColumn=True, w=365, parent=mainScroll)

        self.mainLayout = mainScroll

        pm.rowColumnLayout(nc=2, cw=[(1, 100), (2, 250)], parent=mainColumn)

        # Rig Name
        pm.separator(h=10, style="none")
        pm.text(label='Path ' + script_path[0:13] + '..   ' + 'Version ' + __version__, al='right')

        pm.text(label='Rig Name :', al='right')
        self.rigNameUI = pm.textField("rigNameTextField", changeCommand=partial(setattr, self, 'rigName'),
                                      textChangedCommand=partial(setattr, self, 'rigName'),
                                      annotation='Rig Name', text=self.rigName)
        # Root Button/Text
        rootButton = pm.button("rootButton",
                               label='Root >',
                               command=str)
        self.rootUI = pm.textField("rootNameTextField",
                                   changeCommand=partial(setattr, self, 'root'),
                                   textChangedCommand=partial(setattr, self, 'root'),
                                   annotation='Root', text=self.root)
        pm.button(rootButton, e=True,
                  command=partial(self.setSelectionToTextField, 'root', self.rootUI))

        # control slider
        pm.text(label='Control Size', al='right')
        self.controlSizeUI = pm.floatSliderGrp(rigControlSizeSlider,
                                               l="",
                                               min=1,
                                               max=100,
                                               fieldMaxValue=100000,
                                               value=self.controlSize,
                                               step=1,
                                               field=1,
                                               cat=[1, 'left', -170],
                                               adj=1,
                                               changeCommand=partial(setattr, self, 'controlSize'))

        pm.text(label='Color by Pos.', al='right')
        self.positionBasedColorUI = pm.checkBox("positionBasedColorUI",
                                                value=self.positionBasedColor,
                                                label='',
                                                changeCommand=partial(setattr, self, 'positionBasedColor'))

        pm.separator(h=10, style="none")
        pm.button(label="Generate Rig",
                  command=self.mb_makeRigCommand,
                  bgc=(0.2, 0.6, 0.2),
                  annotation='Create IK Leg. Select main joint first.')
        pm.separator(h=10, style="none")
        pm.button(label="Validate Rig", command=self.validateRig, bgc=(0.8, 0.7, 0.4), annotation='Validate the rig.')  # -MM
        pm.separator(h=10, style="none")
        pm.button(label="Delete Rig", command=lambda x: util.deleteRig(self.rigName), bgc=(0.75, 0.4, 0.4), annotation='Delete the rig.')  # -MM

        self.scrollLayout = pm.scrollLayout(height=700, parent=mainColumn)

        self.initDynamicLayout()
    
        # ------------------- Control Layers ---------------------------------------------
        layoutFrameControlLayers = pm.frameLayout("layoutFrameControlLayers",
                                                  label="Control Layers",
                                                  collapsable=True,
                                                  collapse=self.collapsed.get("Control Layers", True),
                                                  cc=partial(self.collapsed.__setitem__, "Control Layers", True),
                                                  ec=partial(self.collapsed.__setitem__, "Control Layers", False),
                                                  parent=mainColumn)

        layersLayout = pm.rowColumnLayout(nc=2,
                                          cw=[(1, 100), (2, 240)],
                                          parent=layoutFrameControlLayers)
        for i, s in enumerate(self.controlLayerNames):
            pm.text(label=str(i), al='right')
            # pm.separator(h=10, style="none")
            controlLayerTextField = pm.textField('controlLayerTextField' + str(i),
                                                 text=s,
                                                 changeCommand=partial(self.setListAttr, 'controlLayerNames', i),
                                                 annotation='List of control layer names',
                                                 parent=layersLayout)

        pm.button(label='Remove Layer', command=self.removeLayerCommand)
        pm.button(label='Add Layer', command=self.addLayerCommand)

        # --------------------- Add/Remove modules ----------------------------------------
        layoutFrameAddRemove = pm.frameLayout("layoutFrameAddRemove",
                                              label="Add/Remove Modules",
                                              collapsable=True,
                                              collapse=self.collapsed.get("Add/Remove Modules", False),
                                              cc=partial(self.collapsed.__setitem__, "Add/Remove Modules", True),
                                              ec=partial(self.collapsed.__setitem__, "Add/Remove Modules", False),
                                              parent=mainColumn)
        pm.rowColumnLayout(nc=2, cw=[(1, 170), (2, 170)], parent=layoutFrameAddRemove)
        pm.button(label='Remove Module', command=self.removeLastModuleCommand)
        pm.button(label='Add Module', command=self.addModuleCommand)
        pm.columnLayout("moduleAmountSliderColumn", parent=layoutFrameAddRemove)
        self.moduleAmountSlider = pm.intSliderGrp('moduleAmountSlider',
                                                  label='Module Amount',
                                                  value=len(self.modules),
                                                  annotation='',
                                                  parent="moduleAmountSliderColumn",
                                                  min=1,
                                                  field=True)
        pm.button(label='Apply Amount', command=self.applyModuleAmountCommand)

        # Save Shapes
        shapeDataUI = pm.frameLayout("ShapeData",
                                     label="Save/Load Shape Data",
                                     collapsable=True,
                                     collapse=self.collapsed.get("Save/Load Shape Data", True),
                                     cc=partial(self.collapsed.__setitem__, "Save/Load Shape Data", True),
                                     ec=partial(self.collapsed.__setitem__, "Save/Load Shape Data", False),
                                     parent=mainColumn)
        pm.rowColumnLayout(nc=2, cw=[(1, 170), (2, 170)], parent=shapeDataUI)
        if self.uiShapePath == '':
            self.uiShapePath = '%s/%s_EvoRig_shapes.pkl' % (folderDir, fileName[0:-3])
        browseShapeButton = pm.button(label='Browse Shapes', annotation='Browse Shapes')
        self.textFieldShapePath = pm.textField("shapesFilePath",
                                               annotation='Shapes File Path',
                                               text=self.uiShapePath,
                                               changeCommand=partial(setattr, self, 'uiShapePath'),
                                               textChangedCommand=partial(setattr, self, 'uiShapePath'))

        cmd = partial(self.mb_browsePath,
                      folder=folderDir,
                      ff='*.pkl',
                      message='Set Shapes File',
                      textField=self.textFieldShapePath,
                      attrib="uiShapePath")
        pm.button(browseShapeButton, edit=True, command=cmd)

        pm.button(label="Save Shapes", command=self.saveShapes, annotation='Save Shapes')
        pm.button(label="Load Shapes", command=self.loadShapes, annotation='Load Shapes')
        pm.button(label='Shape Editor', command=self.shapeEditor, annotation='Shape Editos')
        self.applyShapeDataUI = pm.checkBox('ApplyShapes',
                                            value=self.applyShapeData,
                                            label='Apply Shapes',
                                            changeCommand=partial(setattr, self, 'applyShapeData'))

        pm.separator(h=10, style="none")
        pm.separator(h=10, style="none")

        # ------------------- Mirror Settings ---------------------------------------------
        mirrorUI = pm.frameLayout("Mirror",
                                    label="Mirror",
                                    collapsable=True,
                                    collapse=self.collapsed.get("Mirror", False),
                                    cc=partial(self.collapsed.__setitem__, "Mirror", True),
                                    ec=partial(self.collapsed.__setitem__, "Mirror", False),
                                    parent=mainColumn)

        mirrorLayout = pm.rowColumnLayout(nc=2,
                                          cw=[(1, 100), (2, 240)],
                                          parent=mirrorUI)
        
        pm.text(label="Left Prefix", al='right')
        self.textFieldLeftPrefix = pm.textField(self.textFieldLeftPrefix,
                                            text=self.leftPrefix,
                                            changeCommand=partial(setattr, self, 'leftPrefix'),
                                            annotation='Left prefix',
                                            parent=mirrorLayout)

        pm.text(label="Right Prefix", al='right')
        self.textFieldRightPrefix = pm.textField(self.textFieldRightPrefix,
                                            text=self.rightPrefix,
                                            changeCommand=partial(setattr, self, 'rightPrefix'),
                                            annotation='Right prefix',
                                            parent=mirrorLayout)
        
         # ------------------- Bone Mod ---------------------------------------------
        boneModUI = pm.frameLayout("BoneMod",
                                        label="Bone Mod",
                                        collapsable=True,
                                        collapse=self.collapsed.get("Bone Mod", True),
                                        cc=partial(self.collapsed.__setitem__, "Bone Mod", True),
                                        ec=partial(self.collapsed.__setitem__, "Bone Mod", False),
                                        parent=mainColumn)
        
        self.boneModDataType = pm.optionMenuGrp(self.boneModDataType, 
                                                label='Bone Mod Data Type',
                                                changeCommand=partial(self.boneModTypeOPMenu_CB))
        pm.menuItem(label='Human')
        pm.menuItem(label='Dino')
        pm.optionMenuGrp(self.boneModDataType,e=True, value=self.boneModData) 
        
        boneModLayout = pm.rowColumnLayout(nc=2,
                                          cw=[(1, 100), (2, 240)],
                                          parent=boneModUI)
        
        pm.text(label="Bone Mod Info", al='right')
        #self.textFieldBoneModInfo = pm.textField(self.textFieldBoneModInfo,    
        self.textFieldBoneModInfo = pm.scrollField(self.textFieldBoneModInfo,    
                                                #ww=True,
                                                text=self.boneModInfo,
                                                annotation='Bone Mod Info',
                                                changeCommand=partial(setattr, self, 'boneModInfo'),
                                                parent=boneModLayout)
        def convert(_):
            self.convertBoneMod()
            self.updatePreview()
        
        pm.text(vis=False)
        pm.button(label="Update", command = convert, annotation='Bone Mod Convert')

         # ------------------- Assembly Script ---------------------------------------------
        assemblyScriptUI = pm.frameLayout("AssemblyScript",
                                        label="Assembly Script",
                                        collapsable=True,
                                        collapse=self.collapsed.get("Assembly Script", True),
                                        cc=partial(self.collapsed.__setitem__, "Assembly Script", True),
                                        ec=partial(self.collapsed.__setitem__, "Assembly Script", False),
                                        parent=mainColumn)
        pm.rowColumnLayout(nc=2, cw=[(1, 170), (2, 170)], parent = assemblyScriptUI)
        browseScriptButton = pm.button(label='Browse Scripts', annotation='Browse Scripts')
        self.textFieldScriptPath = pm.textField("settingsScriptPath",
                                              annotation='Settings Script Path',
                                              text=self.uiScriptPath,
                                              changeCommand=partial(setattr, self, 'uiScriptPath'),
                                              textChangedCommand=partial(setattr, self, 'uiScriptPath'))
        cmd = partial(self.mb_browsePath,
                      folder=folderDir,
                      ff='*.py',
                      message='Set Script File',
                      textField=self.textFieldScriptPath,
                      attrib="uiScriptPath")
        pm.button(browseScriptButton, edit=True, command=cmd)
        

        # Save Settings
        settingsUI = pm.frameLayout("Settings",
                                    label="Settings",
                                    collapsable=True,
                                    collapse=self.collapsed.get("Settings", False),
                                    cc=partial(self.collapsed.__setitem__, "Settings", True),
                                    ec=partial(self.collapsed.__setitem__, "Settings", False),
                                    parent=mainColumn)
        pm.rowColumnLayout(nc=2, cw=[(1, 170), (2, 170)], parent=settingsUI)
        if self.uiPath == '':
            self.uiPath = '{}/{}_EvoRig_settings.json'.format(folderDir, fileName[0:-3])
        browseButtonSettings = pm.button(label='Browse Settings', annotation='Browse Settings')
        self.textFieldFilePath = pm.textField("settingsFilePath",
                                              annotation='Settings File Path',
                                              text=self.uiPath,
                                              changeCommand=partial(setattr, self, 'uiPath'),
                                              textChangedCommand=partial(setattr, self, 'uiPath'))
        cmd = partial(self.mb_browsePath,
                      folder=folderDir,
                      ff='*.json',
                      message='Set Settings File',
                      textField=self.textFieldFilePath,
                      attrib="uiPath")
        pm.button(browseButtonSettings, edit=True, command=cmd)
        pm.button(label="Save Settings", command=self.mb_saveSettings, annotation='Save Settings')
        pm.button(label="Load Settings", command=self.mb_loadSettings, annotation='Load Settings')
        pm.button(label="Reset Settings", command=self.resetSettings, annotation='Reset Settings')

        
        
    def makeWindow(self):
        # Type in the name and the size of the window
        # windowName = "wc_AutoRigWindow"
        windowSize = (300, 600)

        if not (cmds.window(windowName + str(self.uiIndex), exists=True)):
            self.window = pm.window(windowName + str(self.uiIndex),
                                    title=windowName,
                                    resizeToFitChildren=True)  # widthHeight=(windowSize[0], windowSize[1])
        else:
            return

        self.initLayout()

        self.show()
        return self.window

    def setListAttr(self, attr, index, value):
        print(attr)
        getattr(self, attr)[index] = value
        # super(type(self).__bases__[0], self).__setattr__(str(attr) + '[' + str(index) + ']', value)

    def shapeEditor(self, _):
        sh.shapeTemplateUI()

    def setSelectionToTextField(self, attribute, textField, _):
        # single = not hasattr(getattr(self, attribute), '__iter__')
        single = not is_iterable(getattr(self, attribute))
        selection = [x.name() for x in pm.ls(sl=True)]
        if single:
            stringValue = selection[0]
            setattr(self, attribute, selection[0])
        else:
            stringValue = ','.join(selection)
            setattr(self, attribute, selection)

        pm.textField(textField, edit=True, text=stringValue)

    def reorderUpButton(self, i, _):
        print(i)
        if (i == 0):
            return
        switch = self.modules[i - 1], self.modules[i]
        self.modules[i], self.modules[i - 1] = switch
        self.updateUI()

    def reorderDownButton(self, i, _):
        print(i)
        if (i >= (len(self.modules) - 1)):
            return
        switch = self.modules[i + 1], self.modules[i]
        self.modules[i], self.modules[i + 1] = switch
        self.updateUI()

    def applyModuleAmountCommand(self, _):
        value = pm.intSliderGrp(self.moduleAmountSlider, query=True, value=True)
        sx = len(self.modules)

        # nochange
        if value == sx:
            return

        # delete all
        if value == 0:
            self.modules = []

        # add some
        elif value > sx:
            if self.modules:
                newType = self.moduleTypes[self.modules[-1]._label]
            else:
                newType = list(self.moduleTypes.values())[0]
            self.modules.extend([newType() for x in xrange((value - sx))])

        # delete extra
        else:
            del self.modules[value:]

        self.updateUI()

    def moduleMenuChanged(self, i, val):
        util.printdebug(val)
        newSettingIndex = i  # int(val[0])

        old = self.modules[int(i)]
        index = list(self.moduleTypes.keys()).index(val)
        new = list(self.moduleTypes.values())[index]()
        for k, v in new.__dict__.items():
            checkOld = old.__dict__.get(k)
            checkNew = new.__dict__.get(k)
            if '_' in str(k)[0] or checkOld == None:
                continue
            if type(checkOld) != type(checkNew):  # michaelb - Do not copy from old module if the type changed.
                continue
            setattr(new, k, copy.deepcopy(checkOld))
        self.modules[int(i)] = new
        util.printdebug("index:" + str(newSettingIndex))
        pm.evalDeferred(self.updateUI)

    def addModuleCommand(self, _):
        if self.modules:
            new = self.moduleTypes[self.modules[-1]._label]()
        else:
            new = list(self.moduleTypes.values())[0]()

        self.modules.append(new)
        util.printdebug(len(self.modules))
        self.updateUI()

    def removeModuleCommand(self, index, _):
        # always keep at least 1 module
        if len(self.modules) == 1:
            return

        if self.modules:
            confirm = cmds.confirmDialog(title='Confirm Remove Module',
                                         message='Remove Module ' + str(index + 1) + '',
                                         button=['Yes', 'No'],
                                         defaultButton='Yes',
                                         cancelButton='No',
                                         dismissString='No')
            if confirm == 'Yes':
                del self.modules[index]
                util.printdebug(len(self.modules))
                self.updateUI()

    def addLayerCommand(self, _):
        self.controlLayerNames.append('')
        self.updateUI()
        return

    def removeLayerCommand(self, _):
        if len(self.controlLayerNames) > 1:
            self.controlLayerNames.pop()
            self.updateUI()
        return

    def removeLastModuleCommand(self, _):
        # always keep at least 1 module
        if len(self.modules) == 1:
            return

        if self.modules:
            del self.modules[-1]
        util.printdebug(len(self.modules))

        self.updateUI()

    def mb_browsePath(self, *args, **kwargs):
        textField = (kwargs.get('textField'))  # or self.filePath)
        ff = (kwargs.get('ff') or '*.json')
        folder = (kwargs.get('folder') or cmds.internalVar(pwd=True))
        okc = (kwargs.get('message') or "Set Settings Path")
        attrib = (kwargs.get('attrib'))

        print('browse', ff, folder)
        browseFileName = str((pm.fileDialog2(cap="Browse",
                                             dir=folder,
                                             ds=2,
                                             okc=okc,
                                             fm=0,
                                             ff=ff,
                                             rf=1) or [''])[0])
        print(browseFileName)
        if not browseFileName:
            cmds.warning('No File Chosen')
            return

        pm.textField(textField, e=True, text=browseFileName)
        if attrib:
            # print("attrib before is: {} ; {}".format(attrib, getattr(self, attrib)))
            setattr(self, attrib, browseFileName)
            if attrib == 'uiPath':
                self.sceneSettings.setAttr('uiPath', browseFileName)
            # print("attrib is: {} ; {}".format(attrib, getattr(self, attrib)))

        # self.initDynamicLayout()

    def mb_saveSettings(self, args):
        self.saveSettings()

    def mb_loadSettings(self, args):
        self.loadSettings()

    def mb_makeRigCommand(self, args):
        # selection = cmds.ls(sl=True)
        # for each in selection:
        #    cmds.select(each)
        self.makeRig(args)

    def validateRig(self, *args, **kwargs):
        errors = []
        root = self.getRoot()

        if not root:
            errors.append((0,[f"Root not found!\n'{self.root}'"]))

        errors += [(i,x.validate(root)) for i,x in enumerate(self.modules)]
        errors = [x for x in errors if x[1]]

        if not errors:
            message = f"ALL {len(self.modules)} MODULES VALIDATED SUCCESSFULLY!"
        else:
            errorCount = sum(len(x[1]) for x in errors)
            message = f"FOUND {len(errors)} MODULES WITH A TOTAL OF {errorCount} WARNINGS"

            #for key, values in errors_dict.items():
            for key, values in errors:
                spaces = 58
                moduleName = self.modules[key]._label + " - " + self.modules[key].keyword
                buffer = "-" * ((spaces - len(moduleName)) // 2) + " " + moduleName + " " + "-" * ((spaces - len(moduleName)) // 2)
                message += f"\n\n{key+1} {buffer} {key+1}"

                for i in values:
                    message += f"{i}\n"

        cmds.confirmDialog(title="Rig Validation", button=["OK"], icon="warning", message=message)

    def duplicateJointHierarchy(self, parentJoint, constrainToSource=False, createOffsetJoints=False):
        jnt = parentJoint
        chain = jnt.listRelatives(ad=True, type='joint')
        chain.reverse()
        chain.insert(0, jnt)

        rigjnts = []
        offsetjnts = []
        for i, jnt in enumerate(chain):
            util.printdebug("Duplicating: " + jnt.name())
            # Duplicate one joint at a time
            dupRigJnt = jnt.duplicate(parentOnly=True)[0]
            dupRigJnt.rename(jnt.name() + '_RigJnt')
            rigjnts.append(dupRigJnt)
            
            dupOffsetJnt = None
            if createOffsetJoints:
                dupOffsetJnt = jnt.duplicate(parentOnly=True)[0]
                dupOffsetJnt.rename(jnt.name() + '_OffsetJnt')
                offsetjnts.append(dupOffsetJnt)
            
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index(jnt.getParent())
                dupRigJnt.setParent(rigjnts[jntIndex])
                if createOffsetJoints:
                    dupOffsetJnt.setParent(offsetjnts[jntIndex])
            # else:
            #    dup.setParent( masterGrp )
            if (constrainToSource):
                """Constrain joint to duplicate joint"""
                connectedT = pm.connectionInfo(jnt.name() + ".tx", sfd=True)
                connectedR = pm.connectionInfo(jnt.name() + ".rx", sfd=True)
                
                constraintTargets = [dupRigJnt]
                if dupOffsetJnt:
                    constraintTargets.append(dupOffsetJnt)
                    
                if len(connectedT) == 0:
                    pointConstraint = pm.pointConstraint(*constraintTargets, jnt, mo=True, weight=1)
                    if dupOffsetJnt:
                        pm.setAttr(pointConstraint + "." + dupOffsetJnt + "W1", 0)

                if len(connectedR) == 0:
                    orientConstraint = pm.orientConstraint(*constraintTargets, jnt, mo=True, weight=1)
                    orientConstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
                    if dupOffsetJnt:
                        pm.setAttr(orientConstraint + "." + dupOffsetJnt + "W1", 0)

        return rigjnts, offsetjnts
    
    def boneModTypeOPMenu_CB(self, *args):
        self.boneModData = pm.optionMenuGrp(self.boneModDataType, query=True, value=True)

        
    def decodeBoneModData(self, dataString, array, data):
                    if dataString in data:
                        keyLen = len(dataString)
                        newString = str(data)[keyLen+2:]
                        newString = newString.replace(")", "")
                        stringData = newString.split(",")
                        array.append(str(stringData[0])[2:])
                        array.append(str(stringData[1])[2:])
                        array.append(str(stringData[2])[2:])
    
    def convertBoneMod(self):
        boneModData = pm.optionMenuGrp(self.boneModDataType, query=True, value=True)
        boneModInfo = cmds.scrollField(self.textFieldBoneModInfo, query=True, text=True)
        #print("BoneModInfo is:")
        #print(boneModInfo)
        if boneModData == 'Human':
            bNameSplit = boneModInfo.split("(TheBoneName=")
        if boneModData == 'Dino':
            bNameSplit = boneModInfo.split("(BoneName=")
        bNameSplit.pop(0)

        self.recoded = []
        for boneName in bNameSplit:
            boneInfo = []
            
            if boneModData == 'Human':
                bModSplit = boneName.split(",TheBoneModifier=")
                boneInfo.append(str(bModSplit[0])[1:-1])
                dataSplit = bModSplit[1].split("),")
            if boneModData == 'Dino':
                bModSplit = boneName.split(",MaxScale=")    
                boneInfo.append(str(bModSplit[0])[1:-1])
                dataSplit = boneName.split("\",")
                dataSplit = dataSplit[1].split("),")
                
            scale = []
            trans = []
            rot = []
            recur = []
            for data in dataSplit:
                if boneModData == 'Human':
                    self.decodeBoneModData("(Scale", scale, data)
                    self.decodeBoneModData("Translation", trans, data)
                    self.decodeBoneModData("Rotation", rot, data)
                if boneModData == 'Dino':
                    self.decodeBoneModData("MaxScale", scale, data)
                    self.decodeBoneModData("MaxTranslation", trans, data)
                    self.decodeBoneModData("MaxRotation", rot, data)
                
                if "Recursive" in data:
                    recur.append("True")
            
            if scale == []:
                scale = ['0', '0', '0']
            if trans == []:
                trans = ['0', '0', '0']
            if rot == []:
                rot = ['0', '0', '0']
            if recur == []:
                recur = ["False"]

            boneInfo.append(scale)
            boneInfo.append(trans)
            boneInfo.append(rot)
            boneInfo.append(recur)
            self.recoded.append(boneInfo)
    
    # update offset skeleton and build controls
    def updatePreview(self):
        if not hasattr(self, "recoded"):
            self.recoded = []

        root = self.getRoot()
        root = f'{root}_OffsetJnt'
        skeleton = pm.listRelatives(root, allDescendents=True, type='joint')
        skeleton.reverse()
        skeleton.insert(0,root)
        
        if cmds.objExists('offsetControls'):
            children = cmds.listRelatives('offsetControls')
            cmds.delete(children)
            offsetControlGrp = cmds.ls('offsetControls', type='transform')
        
        else:
            offsetControlGrp = cmds.group(name='offsetControls', empty=True)
        
        for bone in skeleton:
            bone = pm.PyNode(bone)
            bone.setScale([1, 1, 1])
            
        for bone in self.recoded:
            name = bone[0]
            name = f"{name}_OffsetJnt"
            scale = bone[1]
            recur = bone[4]
            control = name + "_CON"

            if recur[0] == "True":
                children = cmds.listRelatives(name, ad = True)
                print (children)
                children.append(name)
                for jnt in children:
                    CurrentScaleX =  cmds.getAttr(name+'.scaleX')
                    CurrentScaleY =  cmds.getAttr(name+'.scaleY')
                    CurrentScaleZ =  cmds.getAttr(name+'.scaleZ')
                    cmds.xform(jnt, scale=(float(scale[0])*CurrentScaleX, float(scale[1])*CurrentScaleY, float(scale[2])*CurrentScaleZ))
            else:
                cmds.xform(name, scale=(float(scale[0]), float(scale[1]), float(scale[2])))
                
        for bone in skeleton:
            #making controls and groups. Parenting into hierarchy 
            util.makeNurbsShape(0, name=bone + "_CON", scale = 0.5)
            cmds.group(name= bone + "_GRP", empty=True)
            cmds.group(name= bone + "_offset_GRP", empty=True)
            transGRP = cmds.group(name = bone + '_transGRP', empty=True)
            cmds.parent(bone + "_CON", bone + "_offset_GRP")
            cmds.parent(bone + "_offset_GRP", bone + "_GRP")
            
            #get controls/group to the offset bone position/orientation
            parent = pm.listRelatives(bone, parent=True, type='joint')
            pm.pointConstraint(bone, bone + "_GRP"); pm.delete(bone + "_GRP" + "_pointConstraint1")
            if parent != None:
                pm.orientConstraint(bone, bone + "_GRP"); pm.delete(bone + "_GRP" + "_orientConstraint1")
            #pm.parent(bone + "_GRP", "offsetControls")
            
            pm.parentConstraint(bone.replace('OffsetJnt', 'RigJnt'), transGRP); pm.delete(transGRP + "_parentConstraint1")
            pm.parent(bone + "_GRP",transGRP)
            pm.parent(transGRP, "offsetControls")
            #put the groups into hierarchy and constraint offset bone to control
            if parent:
                pm.parent(transGRP, parent[0] + "_CON")
            pm.pointConstraint(bone + "_CON", bone, mo=True)
            pm.orientConstraint(bone + "_CON", bone, mo=True)
               
        for bone in self.recoded: 
            name = bone[0]
            name = f"{name}_OffsetJnt"
            trans = bone[2]
            rot = bone[3]
            control = name + "_offset_GRP"
            
            cmds.xform(control, 
                       translation=trans, 
                       rotation=rot, 
                       )

            # print("Name        -->  " + str(name))
            # print("Scale       -->  " + str(scale))
            # print("Translation -->  " + str(trans))
            # print("Rotation    -->  " + str(rot))
            # print("Recursive   -->  " + str(recur))
        for bone in skeleton:
            pm.orientConstraint(bone.replace('OffsetJnt', 'RigJnt'), bone + '_CON',  mo=True)
            
            #calculating relative translate and plugging it into each joint's transGRP
            offsetTranslate = pm.createNode("plusMinusAverage", n = bone +'_offsetPMA')
            pm.connectAttr(bone.replace('OffsetJnt', 'RigJnt') + ".translate", offsetTranslate + ".input3D[0]", force=True)
            pm.connectAttr(bone.replace('OffsetJnt', 'RigJnt') + ".translate", offsetTranslate + ".input3D[1]", force=True)
            pm.disconnectAttr(bone.replace('OffsetJnt', 'RigJnt') + ".translate", offsetTranslate + ".input3D[1]")
            pm.setAttr(offsetTranslate + ".operation", 2)
            targetTranslate = pm.createNode("plusMinusAverage", n = bone +'_PMA')
            pm.connectAttr(bone + "_transGRP.translate", targetTranslate + ".input3D[0]", force=True)
            pm.disconnectAttr(bone + "_transGRP.translate", targetTranslate + ".input3D[0]")
            pm.connectAttr(offsetTranslate + ".output3D", targetTranslate + ".input3D[1]", force=True)
            pm.connectAttr(targetTranslate + ".output3D", bone + "_transGRP.translate", force=True)

        return offsetControlGrp
    
    def toggleBoneModSkeleton(self, mainCtrl, offsetJntList):
        root = self.getRoot()
        constraint_list = list(filter(lambda x:x.endswith(("Constraint1")), pm.listRelatives(root, ad = True)))
        
        for constraint in constraint_list:
            lastString = constraint.rfind('_')
            jntName = constraint[:lastString]
            if not 'FACIAL_' in jntName:
                if 'point' in constraint.name() or 'orient' in constraint.name():
                    pm.connectAttr(mainCtrl.name() + '.boneModSkeleton', constraint.name() + f".{jntName}_OffsetJntW1")
                    reverse_node = pm.createNode('reverse',n=f"{jntName}_RVS")
                    pm.connectAttr(mainCtrl.name() + '.boneModSkeleton', reverse_node.name() + '.input.inputX')
                    pm.connectAttr(reverse_node.name() + '.output.outputX', constraint.name() + f".{jntName}_RigJntW0")
                else:
                    pass 
        
        offsetJntList = offsetJntList[1:]  
        bcNodes = []     
        # get correct scale data from boneMod by useing blendColor instead of scaleConstraint
        for offsetjnt in offsetJntList:
            lastString = offsetjnt.rfind('_')
            jntName = offsetjnt[:lastString]
            connectedScale = pm.connectionInfo(jntName + '.scaleX', sfd = True)
            if len(connectedScale) == 0:
                #print ('forBlendColor:' + jntName)
                offsetJntBC = pm.shadingNode('blendColors', asUtility = True, n = offsetjnt + '_scale_BC')
                bcNodes.append(offsetJntBC)
                pm.setAttr(offsetJntBC + '.color2R', 1)
                pm.setAttr(offsetJntBC + '.color2G', 1)
                pm.connectAttr(offsetjnt + '.scale', offsetJntBC.name() + '.color1')
                pm.connectAttr(mainCtrl.name() + '.boneModSkeleton', offsetJntBC.name() + '.blender')
                pm.connectAttr(offsetJntBC.name() + '.output', jntName + '.scale')
                
            if len(connectedScale) > 0 and "CON" in connectedScale:
                #print ('forBlendColor:' + jntName)
                offsetJntBC = pm.shadingNode('blendColors', asUtility = True, n = offsetjnt + '_scale_BC')
                bcNodes.append(offsetJntBC)
                pm.connectAttr(offsetjnt.replace('OffsetJnt','CON') + '.scale', offsetJntBC.name() + '.color2')
                pm.connectAttr(offsetjnt + '.scale', offsetJntBC.name() + '.color1')
                pm.connectAttr(mainCtrl.name() + '.boneModSkeleton', offsetJntBC.name() + '.blender')
                pm.disconnectAttr(offsetjnt.replace('OffsetJnt','CON') + '.scale', jntName + '.scale')
                pm.connectAttr(offsetJntBC.name() + '.output', jntName + '.scale')
           
        util.connectMessage(self.getRigNetwork(), 'blendColors', bcNodes)

    def saveSettings(self):

        self.boneModInfo = cmds.scrollField(self.textFieldBoneModInfo, query=True, text=True)
        self.boneModData = pm.optionMenuGrp(self.boneModDataType, query=True, value=True)

        """Save Settings"""

        settings = [{'rigName':self.rigName,
                     'root':self.root,
                     'controlSize':self.controlSize,
                     'positionBasedColor':self.positionBasedColor,
                     'applyShapeData':self.applyShapeData,
                     'uiShapePath':self.uiShapePath,
                     'controlLayerNames':self.controlLayerNames,
                     'collapsed':self.collapsed,
                     'leftPrefix':self.leftPrefix,
                     'rightPrefix':self.rightPrefix,
                     'boneModData':self.boneModData,
                     'boneModInfo':self.boneModInfo,
                     'uiScriptPath':self.uiScriptPath}]

        for i in range(len(self.modules)):

            modAttrs = {}
            modName = self.modules[i]._label

            modData = self.modules[i].__dict__
            for key, values in modData.items():
                if key[0] != '_' or str(key) in ('_expanded', '_spaceBlendDict','_rollTwistAmountDict'):
                    if pm.objExists(str(values)):
                        values = str(values)

                    modAttrs[str(key)] = (values)
            settings.append([modName, modAttrs])

        try:
            jsonFile = open(self.uiPath, "w")
            json.dump(settings, jsonFile, ensure_ascii=False)
            print('Settings Saved: "' + self.uiPath + '"')
            cmds.inViewMessage( cl='midCenter' )
            cmds.inViewMessage( amg='<hl>Settings Saved to:</hl> "' + self.uiPath + '"', pos='midCenter', fst=2000, fot=500, fade=True )

        except:
            print('=' * 80)
            cmds.warning('Error Saving Settings File "' + self.uiPath + '"')
            print('=' * 80)
            traceback.print_exc()
            print('=' * 80)
            cmds.inViewMessage( cl='midCenter' )
            cmds.inViewMessage( amg='<hl>Error Saving Settings File</hl>\n "' + self.uiPath + '" \n\n' +  traceback.format_exc(), pos='midCenter', fst=4000, fot=1000, fade=True )

            jsonFile.close()
            return
        finally:
            try:
                jsonFile.close()
            except:
                return

        self.sceneSettings.setAttr('uiPath', self.uiPath)

    def resetSettings(self, args):
        self.deleteSceneSettings()
        self.uiPath = self.defaultSettingsPath
        # self.uiPath = None
        self.uiShapePath = None
        self.uiScriptPath = None
        self.leftPrefix = 'l_'
        self.rightPrefix = 'r_'
        self.boneModInfo = ''
        self.boneModData = 'Human'
        # initialize layout
        self.modules = [self.moduleTypes['Additive IK Spline'](keyword='spine', _expanded=True)]

        #self.makeWindow()
        self.updateUI()

    def loadSettings(self):
        """Load Settings"""

        loadModules = []

        try:
            jsonFile = open(self.uiPath, "r")
            settingsLoad = json.load(jsonFile)
        except:
            print('=' * 80)
            cmds.warning('Error Loading Settings File "' + self.uiPath + '"')
            print('=' * 80)
            traceback.print_exc()
            print('=' * 80)
            jsonFile.close()
            return
        finally:
            try:
                jsonFile.close()
            except:
                return

        # get all saved modules, to initalize layout
        print(len(settingsLoad))
        if not settingsLoad:
            cmds.warning('Settings File Empty: "' + self.uiPath + '" -> "' + settingsLoad + '"')
            return

        # Load Auto Rig Settings
        self.__dict__.update(**settingsLoad[0])
        pm.textField(self.rigNameUI, e=True, text=self.rigName)
        pm.textField(self.rootUI, e=True, text=self.root)
        pm.floatSliderGrp(self.controlSizeUI, e=True, value=self.controlSize)
        pm.checkBox(self.applyShapeDataUI, e=True, value=self.applyShapeData)
        pm.checkBox(self.positionBasedColorUI, e=True, value=self.positionBasedColor)
        pm.textField(self.textFieldShapePath, edit=True, text=self.uiShapePath)
        pm.textField(self.textFieldLeftPrefix, edit=True, text=self.leftPrefix)
        pm.textField(self.textFieldRightPrefix, edit=True, text=self.rightPrefix)
        pm.optionMenuGrp(self.boneModDataType, e=True, value=self.boneModData)
        pm.scrollField(self.textFieldBoneModInfo, edit=True, text=self.boneModInfo)
       
        # Load All Modules
        for module in settingsLoad[1:]:
            modName = module[0]
            modKeywords = module[1]
            print('Loading: ', modName, '\n\t', '\n\t'.join(map(str, modKeywords.items())))
            loadModules.append(self.moduleTypes[modName](**modKeywords))

        # initialize layout
        self.modules = loadModules

        #self.makeWindow()
        self.updateUI()

        print('Settings Loaded: "' + self.uiPath + '"')

    def saveShapes(self, _):
        """Save Shapes Data"""

        ctrlSet = self.rigName + "_AllControls_set"
        print(ctrlSet, cmds.objExists(ctrlSet))
        if cmds.objExists(ctrlSet):
            ctrls = pm.sets(ctrlSet, q=True, no=True)
            print('save shaper', ctrls)
            if ctrls:
                self.shapeData = [sh.gizmoObject(x, create=False) for x in ctrls]

        try:
            f = None
            with open(self.uiShapePath, "wb") as f:
                pickle.dump(self.shapeData, f)
            print('Shapes Saved: "' + self.uiShapePath + '"')

            cmds.inViewMessage( cl='midCenter' )
            cmds.inViewMessage( amg='<hl>Shapes Saved to:</hl> "' + self.uiShapePath + '"', pos='midCenter', fst=2000, fot=500, fade=True )
        except:
            cmds.warning('Shapes File Error: "' + self.uiShapePath + '"')
            traceback.print_exc()

            cmds.inViewMessage( cl='midCenter' )
            cmds.inViewMessage( amg='<hl>Error Saving Shapes File</hl>\n "' + self.uiShapePath + '" \n\n' +  traceback.format_exc(), pos='midCenter', fst=4000, fot=1000, fade=True )


        finally:
            if f:
                f.close()

    def loadShapes(self, omitted=None):
        """Load Shapes Data"""

        f = None
        if not os.path.exists(self.uiShapePath):
            cmds.warning('Shapes File Not Found: "' + self.uiShapePath + '"')
        else:
            try:
                with open(self.uiShapePath, "rb") as f:
                    self.shapeData = pickle.load(f)
            except:
                cmds.warning('Shapes File Error: "' + self.uiShapePath + '"')
                traceback.print_exc()
                if f:
                    f.close()
                return
            finally:
                if f:
                    f.close()

            print('Shapes Loaded: "' + self.uiShapePath + '"')
            self.applyShapes(omitted=omitted)

    def applyShapes(self, omitted=None):
        """Apply shape data to current shapes"""
        # Omitted Ctrls Should Not Load Shapes - MM
        omitted = omitted or []

        for item in self.shapeData:
            node = (pm.ls(item.node) or [None])[0]
            if node and not (node in omitted):
                item.setData(node)


    # Added "useEngineIK" argument and Print statement along with moving everything under "if" statement - MM
    def cleanUpFootIKHierarchy(self, exportRoot, controlSize, rigGrp, mainCtrl, rootIKName="foot_root_ik", spaceSwitchList=None, useEngineIK=True):
        print('-' * 60)
        print("IK NAME: {}".format(rootIKName))
        print('-' * 60)

        footIKName = rootIKName
        footIKRoot = util.findInChain(exportRoot, footIKName)
        if footIKRoot:
            pm.delete(footIKRoot)

        # Put everything in a check for whether we are using EngineIK or not - MM
        if useEngineIK:
            footIKRoot = pm.joint(exportRoot, name=footIKName)
            groundPlaneControl = util.getGroundPlaneControl(footIKRoot, rigGrp, controlSize)
            groundOrientConstraint = pm.orientConstraint(groundPlaneControl, footIKRoot, mo=True)
            groundOrientConstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.disconnectAttr(groundOrientConstraint.name() + ".constraintRotateY", footIKRoot.name() + ".rotateY")

            ikControl, ikGrp = util.makeControl(footIKRoot, controlSize, constrainObj=None, worldOrient=True, shape=7, controlSuffix='_EngineIKCON')
            pm.pointConstraint(ikControl, footIKRoot, mo=True)

            pm.parent(ikGrp, rigGrp)
            if spaceSwitchList:
                spaceSwitches = spaceSwitchList[:]
                '''Not adding exportRoot anymore because it would cause a cyclic dependency'''
                spaceSwitches.insert(0, exportRoot)
                util.setupSpaceSwitch(ikControl, spaceSwitches, nameDetailLevel=4, nameDetailStart=0)

            if mainCtrl:
                pm.connectAttr(mainCtrl.name() + ".scale", ikGrp.name() + ".scale")

            # Add controls to set
            engineIKSetName = "EngineIK_ctrl_set"
            engineIKSet = pm.ls(engineIKSetName)
            if not engineIKSet:
                newSet = pm.sets([ikControl], name=engineIKSetName)
            else:
                newSet = pm.sets(engineIKSetName, include=[ikControl])

            if rigGrp:
                engineIKSet = pm.ls(engineIKSetName)
                if engineIKSet:
                    util.addToSet(engineIKSet, rigGrp.name() + '_set')

        return footIKRoot

    def findHipJoint(self, root):
        hipJnt = None
        maxLen = 0
        # Find child with the longest chain
        childJnts = pm.listRelatives(root, allDescendents=False)
        for a in childJnts:
            aRelatives = pm.listRelatives(a, ad=True)
            if len(aRelatives) > maxLen:
                hipJnt = a
                maxLen = len(aRelatives)

        return hipJnt

    def setupControlLayers(self, mainCtrl, allControls):

        for i, x in enumerate(self.controlLayerNames):
            mainCtrl.addAttr(x, at="bool", keyable=False)
            mainCtrl.setAttr(x, True, cb=True)

        for i, ctrl in enumerate(allControls):
            if ctrl == mainCtrl:
                continue

            visnode = None
            parentConnectionOccupied = False
            ctrlParent = ctrl.listRelatives(parent=True)
            if len(ctrlParent) > 0:
                ctrlParent = ctrlParent[0]
                connections = pm.listConnections(ctrlParent.name() + '.visibility', d=False, s=True)
                if len(connections) > 0:
                    parentConnectionOccupied = True
            else:
                continue

            grandParent = None
            if parentConnectionOccupied:
                grandParent = ctrlParent.listRelatives(parent=True)

            if grandParent and len(grandParent) > 0:
                visnode = grandParent[0]
            else:
                visnode = ctrlParent

            connections = pm.listConnections(visnode.name() + '.visibility', d=False, s=True)
            if len(connections) > 0:
                continue

            exists = pm.attributeQuery('controlLayer', node=ctrl, exists=True)
            if not exists:
                continue
            layer = ctrl.getAttr('controlLayer')
            pm.connectAttr(mainCtrl.name() + '.' + self.controlLayerNames[layer], visnode.name() + '.visibility')

            '''cond = pm.shadingNode('condition', asUtility=True) 
            pm.connectAttr(mainCtrl.name() + '.layerVisibility' , cond.name() + '.firstTerm')
            nodeOutliner -e -replace condition536 connectWindowModal|tl|cwForm|connectWindowPane|leftSideCW;
            connectAttr -f l_Eyelid_Upper_CON.controlLayer condition536.secondTerm;
            setAttr "condition536.operation" 3;
            connectAttr -f condition536.outColorR l_Eyelid_Upper_CON_offset_GRP.visibility;'''

    def getRoot(self):
        jnt = (pm.ls(self.root) or [None])[0]
        if not jnt:
            jnt = (pm.selected(type='joint') or [None])[0]

        return jnt

    def getRigNetwork(self):
        nodeName = f'{self.rigName}_Network'
        if pm.objExists(nodeName):
            return pm.PyNode(nodeName)
        else:
            networkNode = pm.createNode('network', n=nodeName)
            return networkNode

    def makeRig(self, args):
        util.printdebug("Making Rig")

        # Get root Joint
        jnt = self.getRoot()

        util.printdebug(jnt)
        if not jnt:
            raise ValueError('A root joint must either be specified or selected.')

        if not cmds.objExists(jnt.longName() + '.rigGroup'):
            pm.addAttr(jnt, ln='rigGroup', at='message', k=False)

        rigCheck = pm.connectionInfo(jnt.longName() + '.rigGroup', sfd=True)
        if not rigCheck:
            rigCheck = pm.ls(self.rigName)
        else:
            rigCheck = pm.ls(rigCheck.split('.')[0])

        print('rigCheck', rigCheck)
        # check for preexisting rig
        if rigCheck:
            confirm = cmds.confirmDialog(title='Confirm',
                                         message='Delete and Replace Existing Rig?',
                                         button=['Yes', 'No'],
                                         defaultButton='Yes',
                                         cancelButton='No',
                                         dismissString='No')
            if confirm == 'Yes':
                util.deleteRig(rigCheck)  # I modified deleteRig to only take the name of the rig to be deleted - MM
            else:
                util.printdebug("Making Rig: Cancelled")
                return
        # Make network node. We will connect all the modules to this 
        rigNetwork = self.getRigNetwork()
        
        # Get control size
        controlSize = cmds.floatSliderGrp(rigControlSizeSlider, q=True, value=True)

        # create duplicate rig and offset skeleton
        boneModText =pm.scrollField(self.textFieldBoneModInfo, query=True, text=True).strip()
        rigjnts = self.duplicateJointHierarchy(jnt, constrainToSource=True, createOffsetJoints = bool(boneModText))
        firstRigJnt = rigjnts[0][0]
        if bool(boneModText):
            firstOffsetJnt = rigjnts[1][0]
        
        """ Make Controls """
        rigGrp = pm.group(em=True, name=self.rigName)
        pm.addAttr(rigGrp, ln='rigRoot', at='message', k=False)
        pm.connectAttr(rigGrp.longName() + ".rigRoot", jnt.longName() + ".rigGroup")
        pm.addAttr(rigGrp, ln='evoRigVersion', dt='string', k=False)
        rigGrp.setAttr('evoRigVersion', __version__)
        util.connectMessage(rigNetwork, 'rigGroup', rigGrp, 'mainNetwork')
        
        # Create Playblast cameras and frame the character. - ethanm
        # Creating now that rig is deleted so framing works more reliably. - ethanm

        # Frame camera to skinned meshes or bones if none found - ethanm
        skinClusters = pm.listHistory([jnt] + (pm.listRelatives(jnt, ad=True, type='joint') or []), type='skinCluster')
        meshes = [x for xl in [pm.skinCluster(s, q=True, g=True) for s in skinClusters] for x in xl]
        if not meshes:
            meshes = [jnt] + (pm.listRelatives(jnt, ad=True, type='joint') or [])

        # set scene resolution to 1080p
        for res in pm.ls('defaultResolution', type='resolution'):
            res.setAttr('width', 1920)
            res.setAttr('height', 1080)
            res.setAttr('deviceAspectRatio', 1.7777777910232544)
            res.setAttr('lockDeviceAspectRatio', False)
            res.setAttr('pixelAspect', 1.0)
            res.setAttr('dotsPerInch', 72.0)

        # iterate thgrough list of camera positions and create one for each- ethanm
        playCameras = {'{}_playblast_3qv'.format(self.rigName):{'y':([1, .25, 1], [-10, -50, 0]),
                                                                'z':([1, -1, .25], [75, 0, -50])},
                       '{}_playblast_tpv'.format(self.rigName):{'y':([0, 1, 1.25], [-35, 180, 0]),
                                                                'z':([0, 1.25, 1.0], [35, 0, 180])},
                       '{}_playblast_lft'.format(self.rigName):{'y':([-1000, 0, 0], [0, -90, 0]),
                                                                'z':([-1000, 0, 0], [90, 0, 90]),
                                                                'ortho':True,
                                                                'cameraScale':1.333}, }
        for name, data in playCameras.items():
            # create the camera - ethanm
            playCam = pm.camera(centerOfInterest=5,
                                focalLength=18.000,
                                lensSqueezeRatio=1,
                                cameraScale=1,
                                horizontalFilmAperture=1.41732,
                                horizontalFilmOffset=0,
                                verticalFilmAperture=0.94488,
                                verticalFilmOffset=0,
                                filmFit='Horizontal',
                                overscan=1.0,
                                motionBlur=0,
                                shutterAngle=144,
                                nearClipPlane=0.1,
                                farClipPlane=10000,
                                orthographic=data.get('ortho', False),
                                orthographicWidth=30,
                                panZoomEnabled=0,
                                horizontalPan=0,
                                verticalPan=0,
                                zoom=1)[0]
            playCam.rename(name)
            playCam.setAttr('v', 0)
            pm.camera(playCam, e=True, displayFilmGate=False, displayResolution=True, overscan=1.0)
            playCam.setAttr('horizontalFilmAperture', 16.0 / 9.0)
            playCam.setAttr('displayGateMaskColor', (0, 0, 0))
            playCam.setAttr('displayGateMaskOpacity', 1)
            playCam.setAttr('focalLength', 22.578)

            # move it to the right position and orientation - ethanm
            pos, rot = data[pm.upAxis(q=True, axis=True).lower()]
            pm.xform(playCam, a=True, ws=True, t=pos)
            pm.xform(playCam, a=True, ws=True, rotation=rot)

            # make it child of rigGrp - ethanm
            pm.parent(playCam, rigGrp)

            # frame skinned meshes (or bones if not skinned) - ethanm
            panel = pm.playblast(ae=True).split('|')[-1]
            current = pm.modelPanel(panel, q=True, camera=True)
            pm.modelPanel(panel, edit=True, camera=playCam)
            OS = pm.selected()
            pm.select(meshes, r=True)
            pm.viewFit(playCam, all=False, f=1)
            mel.eval('fitPanel -selectedNoChildren;')
            playCam.setAttr('cameraScale', data.get('cameraScale', 1.0))
            if OS:
                pm.select(OS, r=True)
            else:
                pm.select(cl=True)
            pm.modelPanel(panel, edit=True, camera=current)

        scale = 8.0 * controlSize
        mainCtrl = util.makeNurbsShape(6, name="c_Main_CON")
        spans = pm.getAttr(mainCtrl + ".spans")
        pm.select(mainCtrl + ".cv[0:" + str(spans) + "]", r=True)
        pm.scale(scale, scale, scale, r=True)
        pm.parent(mainCtrl, rigGrp)
        pm.parent(firstRigJnt, rigGrp)
        if bool(boneModText):
            pm.parent(firstOffsetJnt, rigGrp)
        mainInnerCtrl = util.makeNurbsShape(6, name="c_MainInner_CON")
        scale = 6.0 * controlSize
        spans = pm.getAttr(mainInnerCtrl + ".spans")
        pm.select(mainInnerCtrl + ".cv[0:" + str(spans) + "]", r=True)
        pm.scale(scale, scale, scale, r=True)
        pm.parent(mainInnerCtrl, mainCtrl)
        
        """ Add size attribute for uniform rig scaling """  
        # ethanm - accidental negative scale caused a crash
        pm.addAttr(mainCtrl, ln="size", at='float', k=True, minValue=sys.float_info.epsilon)
        mainCtrl.setAttr("size", 1)
        pm.connectAttr(mainCtrl.name() + '.size', mainCtrl.name() + '.scaleX')
        pm.connectAttr(mainCtrl.name() + '.size', mainCtrl.name() + '.scaleY')
        pm.connectAttr(mainCtrl.name() + '.size', mainCtrl.name() + '.scaleZ')
        util.lockAndHideAttributes(mainInnerCtrl)
        util.lockAndHideAttributes(mainCtrl)
        """ Scale the export skeleton and the RigJnt skeleton with the rig """
        hierarchyroots = [jnt, firstRigJnt]
        for firstJoint in hierarchyroots:
            pm.connectAttr(mainCtrl.name() + '.scale', firstJoint.name() + '.scale')  # Connect scale to allow scaling the rig
            """ Set segmentScaleCompensate to off to allow scaling of rig """
            children = firstJoint.listRelatives(c=True, type='joint')
            for child in children:
                child.setAttr("segmentScaleCompensate", 0)

        worldSpaceNode = pm.createNode('transform', n='world_space', parent=rigGrp)  # self.rigName + '_

        spaceSwitchList = [mainCtrl, mainInnerCtrl, worldSpaceNode]  # ,hipjnt, , headjnt

        allControls = [mainCtrl, mainInnerCtrl]
        omittedControlShapes = []  # Omitted Ctrls Should Not Load Shapes - MM



        # Added "useEngineIK" variable/attribute and check along with print statement for clarification - MM
        makeArmEngineIK = any((x.engineIK for x in self.modules if hasattr(x, "_isArmCtrl") and hasattr(x, 'engineIK')))
        makeLegEngineIK = any((x.engineIK for x in self.modules if hasattr(x, "_isLegCtrl") and hasattr(x, 'engineIK')))
        
        footIKName = 'foot_root_ik'
        footIKRoot = util.findInChain(jnt, footIKName)
        if footIKRoot:
            pm.delete(footIKRoot)

        handIKName = 'hand_root_ik'
        handIKRoot = util.findInChain(jnt, handIKName)
        if handIKRoot:
            pm.delete(handIKRoot)

        # handIKName = None
        # footIKName = None

        # for m in self.modules:
        #     if hasattr(m, "engineIK") and m.engineIK:
        #         if getattr(m, "_isArmCtrl", False):
        #             handIKName = f'{m.keyword}_root_ik'                
        #         elif getattr(m, "_isLegCtrl", False):
        #             footIKName = f'{m.keyword}_root_ik'

        # makeArmEngineIK = handIKName is not None
        # makeLegEngineIK = footIKName is not None
        
        ikRoots = []
        for j in pm.listRelatives(jnt, ad=True, type=pm.nt.Joint):
            if j.hasAttr('engineIKRoot'):
                ikRoots.append(j)
        pm.delete(ikRoots)

        if makeLegEngineIK:
            legEngineIKObj = cr_MakeEngineIK.engineIKCtrl()
            legEngineIKObj.findAndCreate(jnt, 
                                        spaceSwitchList, 
                                        rigGrp, 
                                        controlSize, 
                                        mainCtrl, 
                                        rootIKName=footIKName, 
                                        rigNetwork=rigNetwork)
        if makeArmEngineIK:
            armEngineIKObj = cr_MakeEngineIK.engineIKCtrl()
            armEngineIKObj.findAndCreate(jnt, 
                                        spaceSwitchList, 
                                        rigGrp, 
                                        controlSize, 
                                        mainCtrl, 
                                        rootIKName=handIKName, 
                                        rigNetwork=rigNetwork)
        useEngineIK = makeArmEngineIK or makeLegEngineIK

        print('-' * 60)
        print("IS LEG VALID: {}".format(makeLegEngineIK))
        print('-' * 60)
        print('-' * 60)
        print("IS ARM VALID: {}".format(makeArmEngineIK))
        print('-' * 60)

        hipJnt = self.findHipJoint(firstRigJnt)
        rootControlObj = MakeRoot.rootCtrl()
        rootGrp, rootControl = rootControlObj.findAndCreate(firstRigJnt, 
                                                            spaceSwitchList, 
                                                            rigGrp, 
                                                            controlSize, 
                                                            exportRoot=jnt, 
                                                            hipJnt=hipJnt, 
                                                            rigNetwork=rigNetwork)
        # Iterate through rig modules
        
        for i, module in enumerate(self.modules):

            # ethanm - checks against keyword, jointlist, startjoint, and endjoint before bypassing creation.
            findObjects = (util.findAllInChain(firstRigJnt, module.keyword) or [])
            checkValidObjects = list(getattr(module, x) for x in ('keyword', 'jointList', 'startJoint', 'endJoint') if hasattr(module, x))
            if not any((findObjects + checkValidObjects)):
                pm.warning('Skipping Module {}: No valid joints found'.format(i + 1))
                continue

            # Get Space Switch List
            moduleSpaceSwitchList = []
            if not module.useSpaceBlending:
                moduleSpaceSwitchList = spaceSwitchList[:]
            moduleSpaceSwitchList += [x for x in [util.findInChain(firstRigJnt, s.name() + '_RigJnt') for s in module.spaces] if x]
            # Make Ctrls
            nodes = module.findAndCreate(firstRigJnt,
                                         group=rigGrp,
                                         moduleSpaceSwitchList=moduleSpaceSwitchList,
                                         controlSize=controlSize,
                                         mainCtrl=mainCtrl,
                                         leftPrefix=self.leftPrefix, 
                                         rightPrefix=self.rightPrefix,
                                         rigNetwork=rigNetwork)
            allControls.extend(nodes or [])

            # Omitted Ctrls Should Not Load Shapes - MM
            if not module.applyShapes:
                omittedControlShapes.extend(nodes or [])

        try:
            pm.xform(allControls, t=[0, 0, 0], absolute=True)
        except:
            pass
        
        # updated offset skeleton based on boneMod info
        if bool(boneModText):
            self.convertBoneMod()
            boneModControlGroup = self.updatePreview()
            pm.parent(boneModControlGroup, rigGrp)
            pm.addAttr(mainCtrl, ln="boneModSkeleton", at='float', k=True, minValue=0, maxValue=1)
            pm.setAttr(mainCtrl+'.boneModSkeleton', keyable=False, channelBox=True)
            # connect boneMod Skeleton toggle to constraint to toggle on and off
            self.toggleBoneModSkeleton(mainCtrl, rigjnts[1])
            pm.hide(boneModControlGroup)
            pm.hide(firstOffsetJnt)
        
        # Hide duplicate skeleton after all modules are created successfully
        pm.hide(firstRigJnt)
        #pm.hide(boneModControlGroup)

        # Adjust Main Ctrl Color Overrides
        util.colorControls(allControls, self.positionBasedColor)
        allControls.append(rootControl)  # Don't color root control. Add after coloring all
        shapes = pm.listRelatives(mainCtrl, shapes=True)
        if shapes:
            ashape = shapes[0]
            ashape.setAttr('overrideEnabled', 1)
            ashape.setAttr('overrideColor', 14)
            pm.setAttr(str(ashape) + ".overrideEnabled", 1)
            pm.setAttr(str(ashape) + ".overrideColor", 14)

        # Adjust Main Inner Ctrl Color Overrides
        shapes = pm.listRelatives(mainInnerCtrl, shapes=True)
        if shapes:
            ashape = shapes[0]
            ashape.setAttr('overrideEnabled', 1)
            ashape.setAttr('overrideColor', 18)

        # Control Vis Layers on Main Ctrl
        self.setupControlLayers(mainCtrl, allControls)
        # Setup Selection Sets
        pm.sets(allControls, name=self.rigName + "_AllControls_set")
        # ctrlSet = pm.sets ("HumanRig_AllControls_set", q=True)
        if pm.objExists('Controls'):
            pm.delete('Controls')
        pm.select(allControls)
        pm.createDisplayLayer(name='Controls', noRecurse=True)

        # Only want to add engine IK controls if we are adding engine IK - MM
        if pm.objExists('Controls_EngineIK'):
            pm.delete('Controls_EngineIK')

        if useEngineIK:
            ctrlSet = pm.sets("EngineIK_ctrl_set", q=True)
            pm.select(ctrlSet)
            pm.createDisplayLayer(name='Controls_EngineIK', noRecurse=True)

            omittedControlShapes.extend(ctrlSet)

            allControls.extend(ctrlSet)
        else:
            pm.select(None)

        for module in self.modules:
            if module._label == 'Face':
                module.finish_face_assembly(self.rigName)

        # Apply Saved Shape Data
        print('Apply Shapes:', self.applyShapeData)
        if self.applyShapeData:
            self.loadShapes(omitted=omittedControlShapes)  # Omitted Ctrls Should Not Load Shapes - MM
        print(allControls)
        mirror.initMirror(allControls, leftprefix=self.leftPrefix, rightprefix=self.rightPrefix)
             
        #Run Assembly Scipt if it points to a python file
        if os.path.isfile(self.uiScriptPath) and self.uiScriptPath.endswith('.py'):
            print('Run Script:', self.uiScriptPath)
            with open(self.uiScriptPath,'r') as file:
                exec(file.read())
        else:
            print('No Valid Script File Found')
            
        pm.select(mainCtrl)
        