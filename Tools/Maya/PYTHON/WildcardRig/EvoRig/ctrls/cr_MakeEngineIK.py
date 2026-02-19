
import os, sys
from collections import OrderedDict as od

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

import mb_MakeSimpleFKControl
from EvoRig import mb_rig_utilities as util

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload

import ctrl; reload(ctrl);

#-----------------------------------------------------------------------------#
# Engine IK Module
#-----------------------------------------------------------------------------#



#-----------------------------------------------------------------------------#
# Simple Engine IK Ctrl Module
#-----------------------------------------------------------------------------#


class engineIKCtrl(ctrl.ctrlModule):   
    '''Engine IK Control Wrapper class''' 
    _isCtrl = True
    _label = 'Engine IK'
    _color = (0.4,0.6,0.4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)                    

    def findAndCreate(self, 
                      root,
                      moduleSpaceSwitchList,
                      group = None,
                      controlSize = 1.0,
                      mainCtrl=None,
                      **kwargs):
        
        rootIKName = kwargs.get('rootIKName')
        rigNetwork = kwargs.get('rigNetwork')
        self.keyword = rootIKName

        moduleNetworkName = f'{self._label}_{self.keyword}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)
        
        ikControl, footIKRoot = makeBaseEngineIKControls(root, 
                                                     controlSize, 
                                                     group, 
                                                     mainCtrl,
                                                     rootIKName=rootIKName,
                                                     spaceSwitchList=moduleSpaceSwitchList)
    
        util.connectMessage(networkNode, 'controls', ikControl)
        util.connectMessage(networkNode, 'joints', footIKRoot)

        return ikControl
    

def cr_makeEngineIK(rigParent='',
                    exportParent='',
                    exportRoot='',
                    joint='',
                    xformNode='',
                    conScale = 1,
                    SpaceSwitcherJoints=[],
                    bonePos = [],
                    rootIKName="foot_root_ik",
                    suffix="_ik",
                    group=None,
                    defaultToPlane=False,
                    isBaseJoint=False,
                    orientObject=None,
                    jointName='',
                    mainCtrl=None,
                    spaceBlends=None,
                    applyParentCnsToGroundPreProjection=True):

    if len(bonePos) ==3:
        jointXformPos = bonePos
    else:
        jointXformPos = pm.xform(joint, q=True, ws=True, rp=True)

    jointXformRot = pm.xform(joint, q=True, ws=True, ro=True)

    pm.select(cl=True)
    if not orientObject:
        orientObject = joint
    if len(jointName)==0:
        jointName = joint.name()
    
    ikJoint = pm.joint(name = util.getNiceControllerName(jointName.replace("_ik", ""), suffix))  #first param: orientObject, 
    #pm.parent(ikJoint, w=True)
    pm.xform(ikJoint, ws=True, t=jointXformPos)
    pm.xform(ikJoint, ws=True, ro=jointXformRot)
    
    if exportParent == '':
        #rootIKName = "foot_root_ik"
        footIKRoot = util.findInChain(exportRoot, rootIKName)
        exportParent = footIKRoot
        pm.parent(ikJoint, exportParent)
    else:
        pm.parent(ikJoint, exportParent)
    
    # Set up space switchers
    localSpaceSwitcherJoints = SpaceSwitcherJoints[0:3]
    print(f'joint: {joint}')
    print(f'exportParent {exportParent}')
    print(f'ikJoint {ikJoint}')

    if (joint not in localSpaceSwitcherJoints):
        localSpaceSwitcherJoints.insert(0, joint)
    if (exportParent not in localSpaceSwitcherJoints):
        localSpaceSwitcherJoints.append(exportParent)

    groundPlaneControl = None
    groundPlaneControlGrp = None
    if isBaseJoint:
        conScale *= 1.2
        ikJointXform = pm.xform(ikJoint, q=True, ws=True, rp=True)
        groundPlaneTarget = pm.createNode( 'transform', n=ikJoint.name().replace('_base_ik','_groundPlane') + '_Target' ) #, parent=ikJoint
        pm.xform(groundPlaneTarget, ws=True, t=ikJointXform)
        #pm.parent(groundPlaneTarget, w=True)
        pm.setAttr(groundPlaneTarget.name() + '.translate' + pm.upAxis(q=True, axis=True).upper(), 0)

        groundPlaneAdjustGrp = pm.group(groundPlaneTarget, name=util.getNiceControllerName(groundPlaneTarget.name()).replace("_Target", ""))
        if group:
            pm.parent(groundPlaneAdjustGrp, group)

        groundPlanePreProjection = pm.createNode( 'transform', n=ikJoint.name().replace('_base_ik','_groundPlanePreProjection') , parent=ikJoint)
        pm.parent(groundPlanePreProjection, groundPlaneAdjustGrp)
        
        groundPlaneControl = util.getGroundPlaneControl(ikJoint, group, conScale)

        pm.parentConstraint(groundPlaneControl, groundPlaneAdjustGrp, mo=True)

        # Parent constrain node to joint so it stays centered on foot when rotating
        if applyParentCnsToGroundPreProjection:
            pm.parentConstraint(joint, groundPlanePreProjection, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE) #skipTranslate = pm.upAxis(q=True, axis=True).lower() 
        else:
            pm.pointConstraint(joint, groundPlanePreProjection, mo=True)
        # Point constrain the groundPlaneTarget, which is located on the ground plane. Skip the up-Axis
        pm.pointConstraint(groundPlanePreProjection, groundPlaneTarget, mo=True, skip = pm.upAxis(q=True, axis=True).lower() )
        pm.orientConstraint(joint, groundPlaneTarget, mo=False).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        #pm.pointConstraint(joint, groundPlaneTarget, mo=True, skip = pm.upAxis(q=True, axis=True).lower() )
        

    #print ('joint:', ikJoint, 'parent obj: ', exportParent)
    ikControl, ikGrp = util.makeControl(ikJoint, conScale, constrainObj=ikJoint, worldOrient=True, shape=7, controlSuffix='_EngineIKCON') # parentObj=joint
    pm.parent(ikGrp, exportParent)
    if mainCtrl:
        pm.connectAttr(mainCtrl.name() + ".scale", ikGrp.name() + ".scale")
        if groundPlaneControlGrp:
            pm.connectAttr(mainCtrl.name() + ".scale", groundPlaneControlGrp.name() + ".scale")

    util.setupSpaceSwitch(ikControl, 
                          localSpaceSwitcherJoints, 
                          nameDetailLevel=4, 
                          nameDetailStart=0, 
                          spaceBlends=spaceBlends)

    if isBaseJoint:
        ikControlParent = ikControl.getParent()
        groundPlaneSwitchGrp = pm.group(ikControl, n=ikControl.name() + '_GroundPlane_Grp')
        groundPlaneConstraint = pm.parentConstraint([ikControlParent, groundPlaneTarget], groundPlaneSwitchGrp, mo=False, skipRotate=["x","y","z"]) 
        groundPlaneConstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
        
        pm.addAttr(ikControl, ln='groundPlane', at='double', min=0, max=1, hidden=False, k=True, defaultValue=defaultToPlane)
        weightAliases = groundPlaneConstraint.getWeightAliasList()
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation" , 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(ikControl.name() + ".groundPlane", oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        pm.connectAttr(ikControl.name() + ".groundPlane", weightAliases[1])
        
    allControls = []
    if isBaseJoint:
        allControls.append(groundPlaneControl)

    allControls.append(ikControl)

    #Add controls to set
    engineIKSetName = "EngineIK_ctrl_set"
    engineIKSet = pm.ls(engineIKSetName)
    if not engineIKSet:
        newSet = pm.sets(allControls, name=engineIKSetName)
    else:
        newSet = pm.sets(engineIKSetName, include=allControls)

    if group:
        engineIKSet = pm.ls(engineIKSetName)
        if engineIKSet:
            util.addToSet(engineIKSet, group.name() + '_set')

    return ikGrp, allControls, ikJoint


def makeBaseEngineIKControls(exportRoot, 
                         controlSize, 
                         rigGrp, 
                         mainCtrl, 
                         rootIKName="foot_root_ik", 
                         spaceSwitchList=None):
    
    print('-' * 60)
    print("IK NAME: {}".format(rootIKName))
    print('-' * 60)

    footIKRoot = pm.joint(exportRoot, name=rootIKName)
    pm.addAttr(footIKRoot, ln='engineIKRoot', at='bool')
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

    return ikControl, footIKRoot


def addIKJoints(ankleJnt, poleVector, root, controlSize, moduleSpaceSwitchList, 
                group=None, 
                ballJnt=None, 
                rootIKName="foot_root_ik", 
                baseOffset=0, 
                setBaseToFloor=True, 
                ankleOrientObject=None, 
                footControl=None,
                poleVectorName='',
                mainCtrl=None,
                engineIKBallJoint=False,
                applyParentCnsToGroundPreProjection=True,
                networkNode=None):
    #add engine IKs here
    exportRoot = util.getExportJoint(root)
    #print("+++++++++++++++ exportRoot : " + str(exportRoot) + "  root: " + str(root) )
    engineIKJoints = [util.findInChain(exportRoot, rootIKName)]
    allControls = []
    parentEngineIKJoint = ''

    #Create base joint
    if ballJnt is not None:
        baseJnt = ballJnt
    else:
        baseJnt = ankleJnt

    baseJointPos = pm.xform(baseJnt, q=True, ws=True, rp=True)
    baseJnt = ankleJnt          #Always follow ankle. Use ballJnt only to calculate the base joint position
    if footControl:
        baseJnt=footControl
    
    if setBaseToFloor:
        worldUpAxis=pm.upAxis(q=True, axis=True).upper()
        if worldUpAxis == 'Y':
            baseJointPos = [ baseJointPos[0], 0, baseJointPos[2] + baseOffset]   
        else:
            baseJointPos = [ baseJointPos[0] + baseOffset, baseJointPos[1], 0] 

    grp, ctrl, baseEngineIKJoint = cr_makeEngineIK(exportRoot=exportRoot, 
                                                   joint = baseJnt, 
                                                   SpaceSwitcherJoints=moduleSpaceSwitchList, 
                                                   conScale=controlSize,
                                                   rootIKName=rootIKName,
                                                   bonePos=baseJointPos,
                                                   suffix="_base_ik",
                                                   defaultToPlane=setBaseToFloor,
                                                   isBaseJoint=True,
                                                   group=group,
                                                   mainCtrl=mainCtrl,
                                                   applyParentCnsToGroundPreProjection=applyParentCnsToGroundPreProjection)
    engineIKJoints.append(baseEngineIKJoint)
    allControls += ctrl
    if group:
        pm.parent(grp, group)
    parentEngineIKJoint = baseEngineIKJoint


    #Create ball joint
    if ballJnt and engineIKBallJoint:
        grp, ctrl, ballEngineIKJoint = cr_makeEngineIK(exportRoot=exportRoot, 
                                            exportParent=parentEngineIKJoint,
                                            joint = ballJnt, 
                                            SpaceSwitcherJoints=moduleSpaceSwitchList, 
                                            conScale=controlSize,
                                            rootIKName=rootIKName,
                                            defaultToPlane=setBaseToFloor,
                                            group=group,
                                            orientObject=ankleOrientObject,
                                            mainCtrl=mainCtrl)
        engineIKJoints.append(ballEngineIKJoint)
        allControls += ctrl
        if group:
            pm.parent(grp, group)

        parentEngineIKJoint = ballEngineIKJoint



    #Create ankle joint
    grp, ctrl, ikJoint = cr_makeEngineIK(exportRoot=exportRoot, 
                                         exportParent=parentEngineIKJoint,
                                         joint = ankleJnt, 
                                         SpaceSwitcherJoints=moduleSpaceSwitchList, 
                                         conScale=controlSize,
                                         rootIKName=rootIKName,
                                         defaultToPlane=setBaseToFloor,
                                         group=group,
                                         orientObject=ankleOrientObject,
                                         mainCtrl=mainCtrl)
    engineIKJoints.append(ikJoint)
    allControls += ctrl
    if group:
        pm.parent(grp, group)

    parentEngineIKJoint = ikJoint
    #Create pole vector joint
    if len(poleVectorName) == 0:
        poleVectorName = poleVector.name()
    grp, ctrl, ikJoint = cr_makeEngineIK(exportRoot=exportRoot, 
                            exportParent=parentEngineIKJoint,
                            joint = poleVector, 
                            SpaceSwitcherJoints=moduleSpaceSwitchList, 
                            conScale=controlSize,
                            rootIKName=rootIKName,
                            defaultToPlane=setBaseToFloor,
                            group=group,
                            jointName=poleVectorName,
                            mainCtrl=mainCtrl)
    engineIKJoints.append(ikJoint)
    allControls += ctrl
    if group:
        pm.parent(grp, group)
    
    if networkNode:
        util.connectMessage(networkNode, 'controls', allControls)
        util.connectMessage(networkNode, 'joints', engineIKJoints)

    return allControls, engineIKJoints

