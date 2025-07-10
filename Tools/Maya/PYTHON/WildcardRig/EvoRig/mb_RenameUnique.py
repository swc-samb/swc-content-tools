#Give selected joints unique names 

from pymel.core import *
import maya.cmds as mc
import maya.mel as mm
import logging

RenamePrefix = "Rig_"
RenameSuffix = "_jnt"

#logging.debug(sel)
#help(nt.Joint)

def makeWindow():
    #Type in the name and the size of the window
    windowName = "mb_RenameUnique"
    windowSize = (200, 150)
    #check to see if this window already exists
    if (mc.window(windowName , exists=True)):
        mc.deleteUI(windowName)
    window = mc.window( windowName, title= windowName, widthHeight=(windowSize[0], windowSize[1]) )
    #Type your UI code here
    mc.columnLayout( "mainColumn", adjustableColumn=True )
    
    #World Orientation TextField
    cmds.text( label='Prefix:', al='left' )
    cmds.textField( "namePrefixTextField", text = RenamePrefix, annotation='Prefix', parent = "mainColumn")
    cmds.text( label='Suffix:', al='left' )
    cmds.textField( "nameSuffixTextField", text = RenameSuffix, annotation='Suffix', parent = "mainColumn")

    
    cmds.checkBox("nameJointsBox", label = "Only Joints", annotation='Only rename joints and constraints. Constraints will not be suffixed when this is enabled.', value = True, parent = "mainColumn")
    #cmds.checkBox("nameJointsBox", label = "Constraints", annotation='Only rename joints and constraints', value = True, parent = "mainColumn")


    # Button
    cmds.columnLayout( "columnName02", columnAttach=('both', 5), rowSpacing=10, columnWidth=200)
    cmds.button(label = "Rename", command = executeButton, annotation='Rename selected objects', parent = "columnName02")
    
    cmds.helpLine()
    
    mc.showWindow( windowName )
    mc.window( windowName, edit=True, widthHeight=(windowSize[0], windowSize[1]) )

    
def executeButton(args):
    sel = ''
    RenamePrefix = str(cmds.textField( "namePrefixTextField", query=True, text=True))
    RenameSuffix = str(cmds.textField( "nameSuffixTextField", query=True, text=True))
    bOnlyJoints = mc.checkBox("nameJointsBox", query=True, value=True)
    if (bOnlyJoints):
        sel = ls(sl=True, type="joint", sn=True, l=False)
        selconstraints = ls(sl=True, type="constraint", sn=True, l=False)
        sel += selconstraints
    else:
        sel = ls(sl=True, sn=True, l=False)
    
    for a in sel:
        logging.debug('Selection: ' + str(a))
        aName = str(a)
        aName = aName.decode("utf-8").replace(u"\u007C", "_")
        
        #logging.debug(u"\u007C")
        if (aName.find(RenamePrefix) != 0): #does not have prefix
            aName = RenamePrefix + aName
        if (aName.find(RenameSuffix) == -1): #does not have suffix
            if (bOnlyJoints == False or aName.find('Constraint') == -1):
                aName = aName + RenameSuffix
        
        logging.debug('Renaming to: ' + aName)
        rename(a, aName)
        
#makeWindow()

