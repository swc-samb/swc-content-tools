# Rename center joints
# By Michael Buettner
# Copyright 2017 Wildcard Studios
# 07.07.2017

from pymel.core import *
import maya.cmds as mc
import maya.mel as mm
import logging

CenterPrefix = "c_"
SidePrefixes = "l_ r_"


def makeWindow():
    #Type in the name and the size of the window
    windowName = "mb_RenameCenterJoints"
    windowSize = (200, 150)
    #check to see if this window already exists
    if (mc.window(windowName , exists=True)):
        mc.deleteUI(windowName)
    window = mc.window( windowName, title= windowName, widthHeight=(windowSize[0], windowSize[1]) )
    #Type your UI code here
    mc.columnLayout( "mainColumn", adjustableColumn=True )
    
    #World Orientation TextField
    cmds.text( label='Center Prefix:', al='left' )
    cmds.textField( "nameCenterPrefixTextField", text = CenterPrefix, annotation='Center Prefix', parent = "mainColumn")
    cmds.text( label='Side Prefixes:', al='left' )
    cmds.textField( "nameSidePrefixesTextField", text = SidePrefixes, annotation='Side Prefixes', parent = "mainColumn")

    
    #cmds.checkBox("nameJointsBox", label = "Only Joints", annotation='Only rename joints and constraints. Constraints will not be suffixed when this is enabled.', value = True, parent = "mainColumn")
    #cmds.checkBox("nameJointsBox", label = "Constraints", annotation='Only rename joints and constraints', value = True, parent = "mainColumn")


    # Button
    cmds.columnLayout( "columnName02", columnAttach=('both', 5), rowSpacing=10, columnWidth=200)
    cmds.button(label = "Rename", command = executeButton, annotation='Rename selected objects', parent = "columnName02")
    
    cmds.helpLine()
    
    mc.showWindow( windowName )
    mc.window( windowName, edit=True, widthHeight=(windowSize[0], windowSize[1]) )

    
def executeButton(args):
    sel = ls(sl=True, type="joint")
    if not sel:
        raise TypeError( 'A joint must either be specified, or selected.' )
    jnt = sel[0]
    chain = jnt.listRelatives( ad=True, type='joint' )
    chain.reverse()
    chain.insert( 0, jnt )
    CenterPrefix = str(cmds.textField( "nameCenterPrefixTextField", query=True, text=True))
    SidePrefixes = str(cmds.textField( "nameSidePrefixesTextField", query=True, text=True))
    #bOnlyJoints = mc.checkBox("nameJointsBox", query=True, value=True)
    SideList = SidePrefixes.split()
    print(SideList)
    
    for a in chain:
        #logging.debug('Selection: ' + str(a.name()))
        aName = str(a.name())
        aName = aName.decode("utf-8").replace(u"\u007C", "_")
        
        #logging.debug(u"\u007C")
        foundSidePrefix = False
        for b in SideList:
            if (aName.find(b) == 0):
                foundSidePrefix = True
        if (aName.find(CenterPrefix) != 0 and foundSidePrefix == False): #does not have prefix
            aName = CenterPrefix + aName
        
        #logging.debug('Renaming to: ' + aName)
        rename(a, aName)
        
#makeWindow()

