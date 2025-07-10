'''


'''
import re
import functools
import os
from collections import OrderedDict 

import maya.cmds as cmds
import maya.OpenMayaUI as OpenMayaUI
import maya.mel as mel

maya_version = cmds.about(v=True)
if int(maya_version) > 2024:
    import shiboken6 as shiboken
    from PySide6.QtCore import *
    from PySide6.QtGui import *
    from PySide6.QtWidgets import *
    import PySide6.QtWidgets as QtWidgets
else:
    import shiboken2 as shiboken
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    import PySide2.QtWidgets as QtWidgets
    
import pymel.core as pm

__author__ = 'Corey Ross, Ethan MccAughey'
__version__ = '1.0.2'


MENU_LABEL = 'Space Switching'

WINDOW_NAME='Space Switching_UI'


def maya_main_window():
    mayaMainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
    maya_window = shiboken.wrapInstance(int(mayaMainWindowPtr), QtWidgets.QWidget)

    return maya_window

#Tool UI
class SpaceSwitchUI(QtWidgets.QDialog):

    def __init__(self, parent=maya_main_window()):

        super(SpaceSwitchUI, self).__init__(parent)
        
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME, wnd=True)
            
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle('EvoRig Space Switcher V1')
        
        #layouts
        main_layout = QtWidgets.QVBoxLayout(self)
        refresh_layout = QtWidgets.QHBoxLayout(self)
        availableSpaces_layout = QtWidgets.QVBoxLayout(self)
        selObj_layout = QtWidgets.QHBoxLayout(self)
        switchSpaces_layout = QtWidgets.QVBoxLayout(self)
        switchButton_layout = QtWidgets.QHBoxLayout(self)
        objLabel_layout = QtWidgets.QHBoxLayout(self)

        #buttons
        self.refresh_button = QtWidgets.QPushButton('Refresh')
        self.switchCurrentFrame_button = QtWidgets.QPushButton('Curent Frame')
        self.switchselectedFrames_button = QtWidgets.QPushButton('Selected Frames')
        self.switchAllFrames_button = QtWidgets.QPushButton('All Frames')

        #text fields
        self.selObj_text = QtWidgets.QLineEdit()
        self.currentSpace_text = QtWidgets.QLineEdit()

        #scroll Lists
        self.spaceSelection_scroll = QtWidgets.QComboBox()

        #group boxes
        self.object_groupBox = QtWidgets.QGroupBox('Current Space')
        self.switch_groupBox = QtWidgets.QGroupBox('Switch Spaces')

        #labels
        self.ctrl_label = QtWidgets.QLabel('Control')
        self.space_label = QtWidgets.QLabel('Current Space')

        #parent UI elements to layouts
        refresh_layout.addWidget(self.refresh_button)
        selObj_layout.addWidget(self.selObj_text)
        selObj_layout.addWidget(self.currentSpace_text)
        objLabel_layout.addWidget(self.ctrl_label)
        objLabel_layout.addWidget(self.space_label)
        availableSpaces_layout.addLayout(refresh_layout)
        availableSpaces_layout.addLayout(objLabel_layout)
        availableSpaces_layout.addLayout(selObj_layout)
        switchButton_layout.addWidget(self.switchCurrentFrame_button)
        #switchButton_layout.addWidget(self.switchselectedFrames_button)
        #switchButton_layout.addWidget(self.switchAllFrames_button)
        switchSpaces_layout.addWidget(self.spaceSelection_scroll)
        switchSpaces_layout.addLayout(switchButton_layout)


        #add layouts to group boxes
        self.object_groupBox.setLayout(availableSpaces_layout)
        self.switch_groupBox.setLayout(switchSpaces_layout)

        #add group boxes to main layout
        main_layout.addWidget(self.object_groupBox)
        main_layout.addWidget(self.switch_groupBox)
        
        self.refreshUI()

        self.refresh_button.clicked.connect(functools.partial(self.refreshUI, refresh = True))
        self.switchCurrentFrame_button.clicked.connect(functools.partial(self.switchCurrentFrame))
        #self.switchselectedFrames_button.clicked.connect(functools.partial(self.switchSelectedFrames))
        #self.switchAllFrames_button.clicked.connect(functools.partial(self.switchAllFrames))
       

    def switchSpace(self, startFrame, endFrame):

        # store current selection and current frame
        OS = pm.ls(sl=True)
        currentFrame = pm.currentTime(q=True)


        enumList = self.getTargetList()
        currentSpaceEnum = self.getCurrentSpace()
        newSpaceString = self.spaceSelection_scroll.currentText()
        newSpaceAttr = enumList.index(str(newSpaceString))

        ctrl = self.getCtrl()
        if not ctrl:
            pm.warning('Control Not Found "{}"'.format(ctrl))
            return

        # Create Ref Groups
        refGroup = pm.createNode('transform',ss=True,name='{}_spaceBlendTemp'.format(ctrl))
        startGroup = pm.createNode('transform',ss=True,name='{}_spaceBlendTempStart'.format(ctrl))
        endGroup = pm.createNode('transform',ss=True,name='{}_spaceBlendTempEnd'.format(ctrl))

        for frame,group in zip((startFrame,endFrame), (startGroup, endGroup)):
            pm.currentTime(frame,update=True)
            pm.xform(group,
                     a=True,
                     ws=True,
                     matrix=pm.xform(ctrl,q=True,ws=True,matrix=True))
        refConstraint = pm.parentConstraint(startGroup,refGroup,mo=False)        
        refConstraint = pm.parentConstraint(endGroup,refGroup,mo=False)
        refConstraint.setAttr('interpType',2)
        pm.setKeyframe(ctrl,t=startFrame,at=refConstraint.getWeightAliasList()[0],value=1.0)
        pm.setKeyframe(ctrl,t=startFrame,at=refConstraint.getWeightAliasList()[1],value=0.0)
        pm.setKeyframe(ctrl,t=endFrame,at=refConstraint.getWeightAliasList()[0],value=0.0)
        pm.setKeyframe(ctrl,t=endFrame,at=refConstraint.getWeightAliasList()[1],value=1.0)


        pm.setKeyframe(ctrl, t=startFrame, at='space',value=currentSpaceEnum)
        pm.setKeyframe(ctrl, t=endFrame, at='space',value=newSpaceAttr)

        for frame in range(int(startFrame),int(endFrame+1)):
            pm.currentTime(frame,update=True)
            pm.xform(ctrl,
                     a=True,
                     ws=True,
                     matrix=pm.xform(refGroup,q=True,ws=True,matrix=True))
            pm.setKeyframe(ctrl,mr=True,at='t')
            pm.setKeyframe(ctrl,mr=True,at='r')
            pm.setKeyframe(ctrl,mr=True,at='s')

        pm.delete([refGroup, startGroup, endGroup])


        # reset selection
        if OS:
            pm.select(OS,r=True)
        else:
            pm.select(cl=True)

        pm.currentTime(currentFrame, update=True)
        

    def switchCurrentFrame(self):

        ctrl = self.getCtrl()

        pm.undoInfo(ock=True)
        currentFrame = pm.currentTime(q=True)
        self.switchSpace(currentFrame-1, currentFrame)



    def switchSelectedFrames(self):

        selectedFrames = mel.eval('$tmpVar=$gPlayBackSlider')
        timeRange = pm.timeControl(selectedFrames, q=True, rangeArray=True)
        self.switchSpace(timeRange[0], timeRange[-1])

    
    def switchAllFrames(self):

        startFrame = pm.playbackOptions(q=True, minTime=True)
        endFrame = pm.playbackOptions(q=True, maxTime=True)
        print(startFrame)
        print(endFrame)
        self.switchSpace(startFrame, endFrame)


    def refreshUI(self, refresh=False):

        #clear UI 
        self.selObj_text.clear()
        self.currentSpace_text.clear()
        self.spaceSelection_scroll.clear()

        self.selObj_text.setText(self.getSelection(refresh=refresh))
        enumIndex = self.getCurrentSpace()
        
        if self.selObj_text.text() != None and enumIndex != None:
            enumList = self.getTargetList()
            self.currentSpace_text.setText(enumList[int(enumIndex)])
            self.spaceSelection_scroll.addItems(enumList)

    def getTargetList(self):
        enums = pm.attributeQuery('space', n=self.selObj_text.text(), listEnum=True)
        print('enums "{}"'.format(enums))
        enumList = enums[0].split(':')
        return enumList


    def getSelection(self, refresh=False):
        selObjs = pm.ls(sl=True)
        if len(selObjs)==1:
            if selObjs[0][-3:]=='CON':
                return str(selObjs[0])
            else:
                if refresh == True:
                    pm.confirmDialog(title='Please Select valid Control Object', message= 'Please Select Single Valid Control Object')
                return None
        else:
            if refresh == True:
                pm.confirmDialog(title='Please Select valid Control Object', message= 'Please Select Single Valid Control Object')
            return None            

    def getCurrentSpace(self):
        ctrl = self.getCtrl()

        if ctrl != None:
            try:
                space = ctrl.getAttr('space')
                return int(space)
            except:
                return None

    # I think this one can be deleted
    def getMatrix(self, node):
        try:
            matrix = pm.xfor(node, q=True, matrix=True)
        except:
            matrix = None
            print('no target matrix')
        return matrix
    
    def getConstraintInputs(self):
        ctrl = self.getCtrl()
        spaceGrp = '{}_Grp'.format(ctrl)
        constraint = pm.parentConstraint(spaceGrp, q=True, n=True)
        targets = pm.parentConstraint(constraint, q=True, targetList=True)
        return targets

    # I think this one can be deleted
    def getParent(self, node, levels=1):
        obj = node
        i = 0
        while i < levels:
            try:
                parent = pm.listrelatives(obj, p=True)
                obj = parent
                i += 1
            except:
                print('no parent object')
                i += levels
        return obj
    
    def getCtrl(self):
        ctrl = (pm.ls(self.selObj_text.text()) or [None])[0]
        
        if not ctrl:
            pm.warning('Control Not Found "{}"'.format(ctrl))
            
        return ctrl
        


def main():
    """
    Runtime method called whenever the file is executed.
    :rtype: None
    """

    # Close previous session
    #Window.closeExistingWindow()

    # Create new instance
    window = SpaceSwitchUI()
    window.show()


if __name__ == '__main__':

    main()

