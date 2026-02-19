
import os
import sys
import importlib
from collections import OrderedDict as od

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

from EvoRig import mb_rig_utilities as util
#import mb_rig_utilities as util
#util.debugging = False


if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

import ctrl; reload(ctrl);

#-----------------------------------------------------------------------------#
# Prop Ctrl Module
#-----------------------------------------------------------------------------#


class propCtrl(ctrl.ctrlModule):   
    '''Prop Control Wrapper class''' 
    _isCtrl = True
    _label = 'Prop'
    _color = (0.6,0.6,0.6)

    def __init__(self, *args, **kwargs):
        #super(type(self), self).__init__(*args, **kwargs)
        self._nodeAttributes = {}
        self.keyword = ''

        self.startJoint = ''
        self.endJoint = ''
        self.jointList = []
        self._nodeAttributes['startJoint'] = True
        self._nodeAttributes['endJoint'] = True
        self._nodeAttributes['jointList'] = True
        self.forwardAxis = od([('X',[1,0,0]),
                               ('Y',[0,1,0]),
                               ('Z',[0,0,1])])
        self.mirrorModule = False
        self.maintainOffset = False

        type(self).__bases__[0].__init__(self, *args, **kwargs)

        #bool and dict menu examples
        
        #if not hasattr(self, 'test'):
        #    self.test = True

        #if not hasattr(self, 'testMenu'):
        #    self.testMenu = od([('x',[1,0,0]),
        #                        ('y',[0,1,0]),
        #                        ('z',[0,0,1])])
                                

    def findAndCreate(self, 
                      root, 
                      moduleSpaceSwitchList = None,
                      group = None,
                      controlSize = 1.0,
                      mainCtrl=None,
                      **kwargs):
        #util.debugging = True
        '''Search Root Nodes for keywords and issue make command
           Should Be overwritten for each node to get proper args'''
        if self.keyword is False:
            return
        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        if self.jointList:
            jointList = util.getRigJoint(self.jointList)
        else:
            startJoint, endJoint = util.getRigJoint([(self.startJoint or None), (self.endJoint or None)])

            jointList = []
            if (endJoint and startJoint):
                startJoints = [startJoint]
                endJoints = [endJoint]
                for i,j in enumerate(startJoints):
                    chain = util.getChainFromStartToEnd(j, endJoints[i])
                jointList += chain
            else:
                jointList = util.findAllInChain(root, self.keyword)
                if jointList == None:
                    raise ValueError('Joint not found in hierarchy: ' + self.keyword )
                startJoints = [None]*len(jointList)
                endJoints = [None]*len(jointList)
        

        #since using mutable types are default arges can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []
        moduleSpaceSwitchList.reverse()

        util.printdebug("Module " + str(self._index) + ' adding Prop, Keyword:' + str(self.keyword))
        controlGrps, ctrls = mb_makePropControl(jointList, 
                                                conScale = controlSize * 0.8 * self.moduleSize, 
                                                SpaceSwitcherJoints = moduleSpaceSwitchList,
                                                forwardAxis = self.forwardAxis,
                                                setNameKeyword=str(self.keyword),
                                                group=group,
                                                inheritTranslation=True,
                                                spaceBlends=(self._spaceBlendDict if self.useSpaceBlending else None),
                                                maintainOffset=self.maintainOffset)
        if group:                                                   
            pm.parent(controlGrps, group)

        # Mirrored side
        mirrorJointList = []
        if self.mirrorModule:
            if self.jointList:                
                for j in jointList:
                    mj = pm.PyNode(util.mirrorName(j))
                    if mj and mj not in mirrorJointList:
                        mirrorJointList.append(mj)
            
            mirrorModuleSpaceSwitchList = []
            for j in moduleSpaceSwitchList:
                    mirrorSpace = pm.PyNode(util.mirrorName(j))
                    if mirrorSpace and mirrorSpace not in mirrorModuleSpaceSwitchList:
                        mirrorModuleSpaceSwitchList.append(mirrorSpace)

            # ethanm - mirrored controls mirror their spaceblends if any
            mirrorControlGrps, mirrorCtrls = mb_makePropControl(mirrorJointList, 
                                                                conScale = controlSize * 0.8 * self.moduleSize, 
                                                                SpaceSwitcherJoints = mirrorModuleSpaceSwitchList,
                                                                forwardAxis = self.forwardAxis,
                                                                setNameKeyword=str(self.keyword),
                                                                group=group,
                                                                inheritTranslation=True,
                                                                spaceBlends=({util.mirrorName(k):v for k,v in self._spaceBlendDict.items()} if self.useSpaceBlending else None),
                                                                maintainOffset=self.maintainOffset)
            if group:                                                   
                pm.parent(mirrorControlGrps, group)
            ctrls += mirrorCtrls
            jointList += mirrorJointList
        util.connectMessage(networkNode, 'controls', ctrls)
        connect_chain = [x.name().split('_RigJnt')[0] for x in jointList]
        util.connectMessage(networkNode, 'joints', connect_chain)

        self.createControlAttributes(ctrls)

        #create parent constraint retarget hints
        for i,joint in enumerate(map(util.getExportJoint, jointList)):
            ctr1,ctr2 = ctrls[i*2], ctrls[i*2+1]
            print('hint', ctr1, joint)
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr1)
            self.setRetargetHintAttributes(ctr1, *args, **kwargs)
            print('hint', ctr2, joint)
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr2)
            self.setRetargetHintAttributes(ctr2, *args, **kwargs)

        return ctrls
        


#-----------------------------------------------------------------------------#
#  Utitlity Functions
#-----------------------------------------------------------------------------#

def mb_makePropControl(joints=None,
                       conScale=5,
                       SpaceSwitcherJoints=[],
                       forwardAxis=(1,0,0),
                       createSet=True,
                       setNameKeyword=False,
                       inheritTranslation=False,
                       group=None,
                       spaceBlends=None,
                       maintainOffset=False):
    
    grpNodes = []
    controls = []

    for obj in joints:

        """Create Control"""
        ctrl, grp = util.makeControl(obj, conScale, shape=0, worldOrient=True) #, separateRotateOrient=True
        followCtrl, followGrp = util.makeControl(obj, conScale, constrainObj=obj, shape=10, ctrlName=util.getNiceControllerName(obj.name(), '_follow_CON'), hideAttributes=[0,0,0]) 
        
        """ Master Group """
        master = pm.group(em=True, name =  "CON_" + obj + "Grp")
        pm.parent(master, ctrl, r=True)
        pm.parent(master, w=True)
        
        util.lockAndHideAttributes(master, hideScale=True)
        pm.parent(grp, master)
        pm.parent(followGrp, master)

        if len(SpaceSwitcherJoints) == 0:
            spaceList = []
        else:
            spaceList = list(SpaceSwitcherJoints)

        # Remove hand space for main control
        followSpaceList = spaceList + [ctrl]
        util.setupSpaceSwitch(followCtrl, followSpaceList, nameDetailLevel=3, maintainOffset=maintainOffset, spaceBlends=spaceBlends)
        spaceList = spaceList[1:]   #    Remove the hand (index 0) from the list to avoid cyclic dependency. If list was not reversed it would need to be spaceList[:-1] 
        objPos = pm.xform(ctrl, translation=True, q=True, ws=True)      #rp=True
        objRot = pm.xform(ctrl, rotation=True, q=True, ws=True)

        util.setupSpaceSwitch(ctrl, spaceList, nameDetailLevel=3, maintainOffset=False, spaceBlends=spaceBlends)     #Snaps control to origin because maintainOffset is False
        
        pm.xform(ctrl, ws=True, translation=objPos)     #Restore the transform to snap the control back to the hand. This will result in non-zero values but the joint is not following this control so it's not an issue.
        pm.xform(ctrl, ws=True, rotation=objRot)
        
        pm.scaleConstraint(followCtrl, obj, mo=False, weight= 1)
        pm.scaleConstraint(obj, util.getExportJoint(obj), mo=False, weight= 1)  #constrain export rig joint
        
        util.lockAndHideAttributes(ctrl.getParent(), hideTranslation=True, hideRotation=True, hideScale=True)

        util.lockAndHideAttributes(ctrl, hideScale=True)
        util.lockAndHideAttributes(followCtrl, hideScale=False)

        #Check if _local joint exists and constrain it
        suffix = "_RigJnt"
        localJoint = util.getRigJoint(obj.name().replace(suffix, '') + '_local')
        if localJoint:
            pm.parentConstraint(obj, localJoint, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.scaleConstraint(obj, localJoint, mo=False, weight= 1)
            pm.scaleConstraint(localJoint, util.getExportJoint(localJoint), mo=False, weight= 1)
            #pm.connectAttr('{}.scale'.format(localJoint), '{}.scale'.format(util.getExportJoint(localJoint)))    #constrain export rig joint

        # michaelb - Constrain the _sec_hand joint to the opposite hand
        parents = obj.listRelatives(p=True)
        if parents:
            mHandJnt = pm.PyNode(util.mirrorName(parents[0]))
        secondaryHandJnt = None
        if localJoint:
            secondaryHandJnt = util.findAllInChain(localJoint, obj.name().replace(suffix, '') + '_sec_hand', allDescendents=False)
        if mHandJnt and secondaryHandJnt:
            pm.parentConstraint(mHandJnt, secondaryHandJnt, mo=False)

        grpNodes.append(master)
        controls.append(ctrl)
        controls.append(followCtrl)

    #Create Sets
    if createSet:
        if setNameKeyword is not False:
            setName = setNameKeyword
        else:
            setName = joints[0].name()
        newSet = pm.sets(controls, name= util.getNiceControllerName(joints[0].name()[0:2] + setName, '_ctrl_set'))      #Include prefix of first joint in the set name
        if group:
            util.addToSet(newSet, group.name() + '_set')

    return grpNodes, controls


