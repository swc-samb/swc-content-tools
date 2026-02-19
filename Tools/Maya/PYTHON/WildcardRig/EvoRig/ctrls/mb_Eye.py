import os, sys
from collections import OrderedDict as od
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

from EvoRig import mb_rig_utilities as util

# import mb_rig_utilities as util
# util.debugging = False

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload

import ctrl;

reload(ctrl);


# -----------------------------------------------------------------------------#
# Eye Ctrl Module
# -----------------------------------------------------------------------------#


class eyeLookAtCtrl(ctrl.ctrlModule):
    '''eye Control Wrapper class'''
    _isCtrl = True
    _label = 'Eye'
    _color = (0.6, 0.2, 0.4)

    def __init__(self, *args, **kwargs):
        # super(type(self), self).__init__(*args, **kwargs)
        self._nodeAttributes = {}
        self.keyword = ''
        self.jointList = []
        self._nodeAttributes['jointList'] = True

        self.forwardAxis = od([('X', [1, 0, 0]),
                               ('Y', [0, 1, 0]),
                               ('Z', [0, 0, 1])])
        self.forwardOffset = 100.0
        self.eyeForwardOffset = 100.0  # micm - adding a unique offset for the lookAtTarget
        self.mirrorModule = False

        type(self).__bases__[0].__init__(self, *args, **kwargs)

    def findAndCreate(self,
                      root,
                      moduleSpaceSwitchList=None,
                      group=None,
                      controlSize=1.0,
                      mainCtrl=None,
                      **kwargs):
        # util.debugging = True
        '''Search Root Nodes for keywords and issue make command
           Should Be overwritten for each node to get proper args'''
        if self.keyword is False:
            return

        if not self.jointList:
            print("No joints defined for eyeLookAtCtrl, exiting!")
            return
        
        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        leftPrefix = (kwargs.get('leftPrefix') or 'l_')
        rightPrefix = (kwargs.get('rightPrefix') or 'r_')

        # ethanm - now tracking which joints are found with mirror module so that space blending can be mirrored accordingly
        jointList = util.getRigJoint(self.jointList)

        # ethanm - given jointlist is not mirrored
        mirrored = [False] * len(jointList)

        if self.mirrorModule:
            mirrorJointList = []
            for j in jointList:
                mj = pm.PyNode(util.mirrorName(j, leftPrefix=leftPrefix, rightPrefix=rightPrefix))
                if mj and mj not in jointList:
                    mirrorJointList.append(mj)

            jointList += mirrorJointList

            # ethanm - update corresponding mirrored list for mirrored joints
            mirrored += [True] * len(mirrorJointList)
        
        connect_chain = [x.name().split('_RigJnt')[0] for x in jointList]
        util.connectMessage(networkNode, 'joints', connect_chain)

        # since using mutable types are default args can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []

        # ethanm - set up space blending for each joint and mirrored as indicated by the mirrored list
        spaceBlends = []
        for mirror, joint in zip(mirrored, jointList):
            if not mirror:
                spaceBlends.append((self._spaceBlendDict if self.useSpaceBlending else None))
            else:
                spaceBlends.append(({util.mirrorName(k, leftPrefix=leftPrefix, rightPrefix=rightPrefix): v for k, v in
                                     self._spaceBlendDict.items()} if self.useSpaceBlending else None))

        util.printdebug("Module " + str(self._index) + ' adding EyeLookAt, Keyword:' + str(self.keyword))
        for item in jointList:
            print(' - {}'.format(item))

        controlGrps, ctrls = mb_makeEyeLookAt(jointList,
                                              conScale=controlSize * 0.8 * self.moduleSize,
                                              SpaceSwitcherJoints=moduleSpaceSwitchList,
                                              forwardAxis=self.forwardAxis,
                                              eyeForwardOffset=self.eyeForwardOffset,
                                              # micm - a float setting eye offset
                                              group=group,
                                              spaceBlends=spaceBlends,
                                              # ethanm - space blends is a list of dicts for each joint
                                              forwardOffset=self.forwardOffset,
                                              leftPrefix=leftPrefix, 
                                              rightPrefix=rightPrefix,
                                              mirrorModule=self.mirrorModule
                                              )
        if group:
            pm.parent(controlGrps, group)
        util.connectMessage(networkNode, 'controls', ctrls)
        self.createControlAttributes(ctrls)

        # set retarget hint attributes
        for ctr, joint in zip(ctrls, jointList):
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint, ctr)
            self.setRetargetHintAttributes(ctr, *args, **kwargs)

        return ctrls

        return allControls


# -----------------------------------------------------------------------------#
#  Utitlity Functions
# -----------------------------------------------------------------------------#

def mb_makeEyeLookAt(jointList,
                     conScale=1,
                     SpaceSwitcherJoints=[],
                     forwardAxis=(1, 0, 0),
                     eyeForwardOffset=100,
                     group=None,
                     spaceBlends=None,
                     forwardOffset=100,
                     leftPrefix='l_', 
                     rightPrefix='r_',
                     mirrorModule=False):
    """ ctrl Group """

    truncatedName = jointList[0].name()[2:]
    ctrlGrp = pm.group(em=True, name="CON_" + truncatedName + "Grp")
    pm.parent(ctrlGrp, w=True)

    objPos = pm.xform(jointList[0], translation=True, q=True, ws=True)
    aimPos = objPos
    aimPos[0] = 0
    aimPos[2] = aimPos[2] + forwardOffset  # Position Aim Control at the center and offset forward into look direction
    aimNode = pm.createNode('transform', ss=True, parent=ctrlGrp, name='{}_Aim'.format(truncatedName))
    pm.xform(aimNode, a=True, ws=True, translation=aimPos)
    allCtrls = []
    parentRigJnt = jointList[0].getParent()
    aimCtrl, aimGrp = util.makeControl(aimNode, conScale, constrainObj=aimNode, parentObj=None, shape=7,
                                       ctrlName=util.getNiceControllerName(aimNode.name(), '_CON'),
                                       hideAttributes=[0, 0, 0])
    allCtrls.append(aimCtrl)
    pm.parent(aimGrp, ctrlGrp)

    spans = pm.getAttr(aimCtrl.name() + ".spans")
    pm.select(aimCtrl.name() + ".cv[0:" + str(spans) + "]", r=True)
    pm.rotate([90, 0, 0], os=True)

    for i, currentJnt in enumerate(jointList):
        suffix = "Grp"
        inherit = ""

        inherit = "CON" + currentJnt.name() + "INH"
        inherit = pm.group(em=True, name=str(inherit))
        inheritTrans = pm.group(em=True, name=str(inherit) + "Trans")
        pm.parent(inherit, ctrlGrp)
        pm.parentConstraint(parentRigJnt, inheritTrans)

        """Create Control"""
        forwardAxisString = 'X' if forwardAxis[0] == 1 else 'Y'
        if forwardAxis[2] == 1:
            forwardAxisString = 'Z' 
        ctrl = util.makeNurbsShape(8, name=currentJnt.name().replace("_RigJnt", "") + "_CON",
                                   forwardAxis=forwardAxisString)

        spans = cmds.getAttr(ctrl + ".spans")
        cmds.select(ctrl + ".cv[0:" + str(spans) + "]", r=True)
        cmds.scale(conScale, conScale, conScale, r=True)
        if currentJnt.name().lower().find('r_') == 0:
            cmds.rotate(180, 0, 0, os=True)
        pm.select(ctrl, r=True)
        allCtrls.append(ctrl)

        """Set INH pivot to parent pivot"""
        objparent = currentJnt.listRelatives(p=True)
        if (objparent is not None and len(objparent) > 0):
            objparent = objparent[0]

        """Match inheritTrans transform and parent to inherit"""
        pm.parent(inheritTrans, currentJnt, r=True)
        pm.parent(inheritTrans, w=True)
        pm.parent(inheritTrans, inherit)

        """Create Group node"""
        grpNode = pm.group(ctrl, n=ctrl + suffix)

        """Match grpNode transform to object"""
        pm.parent(grpNode, currentJnt, r=True)
        pm.parent(grpNode, w=True)
        """Parent grpNode to INH node"""
        pm.parent(grpNode, inheritTrans)

        """Create lookat target"""
        lookAtTarget = pm.group(em=True, name=str(currentJnt.name() + "_LookAtTarget"))
        pm.parent(lookAtTarget, currentJnt, r=True)

        side = util.getPrefixSide(currentJnt, leftPrefix, rightPrefix)

        # micm - adding a separate variable to set offset for Look At Target independent of AimPos
        print("------------------+++++++++++++++++++++++++++++++++++++++++++++++++     Side is: {}".format(side))
        forwardVector = pm.datatypes.Vector((forwardAxis))
        offset = eyeForwardOffset * forwardVector
        if side == -1 and mirrorModule:
            offset = offset * -1.0

        lookAtTarget.setTranslation(offset)
        pm.parent(lookAtTarget, aimCtrl)

        eyeupxform = pm.xform(grpNode, q=True, ws=True, m=True)
        UpVectorObject = pm.createNode( 'transform', n=grpNode.name() + '_Up', parent=inheritTrans)
        pm.xform(UpVectorObject, ws=True, m=eyeupxform)
        pm.aimConstraint(lookAtTarget, grpNode, mo=False, wut="objectrotation", wuo=UpVectorObject)
        rotConstraint = pm.orientConstraint(ctrl, currentJnt, mo=True)
        scaleConstraint = pm.scaleConstraint(ctrl, currentJnt)

        singleAimCtrl, singleAimGrp = util.makeControl(lookAtTarget, conScale, constrainObj=lookAtTarget,
                                                       parentObj=aimCtrl, shape=14,
                                                       ctrlName=util.getNiceControllerName(lookAtTarget.name(), '_CON'),
                                                       hideAttributes=[0, 0, 0])
        allCtrls.append(singleAimCtrl)
        pm.parent(singleAimGrp, ctrlGrp)

        """ Add follow attribute
        pm.addAttr(ctrl, ln="Follow", at="float", min=0, max=1, defaultValue=1, k=True)

        # Allow disabling auto-follow 
        parentFollowCns = pm.parentConstraint([inheritTrans, followTransformNode], grpNode, mo=True)
        parentFollowCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
        weightAliases = parentFollowCns.getWeightAliasList()
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation" , 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(aimCtrl.name() + ".Follow", oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        pm.connectAttr(aimCtrl.name() + ".Follow", weightAliases[1])
        """
    print(f"SpaceBlends: {spaceBlends}")
    print(f"SpaceSwitcherJoints: {SpaceSwitcherJoints}")

    localSpaceSwitcherJoints = SpaceSwitcherJoints[:]
    if (parentRigJnt not in localSpaceSwitcherJoints):
        localSpaceSwitcherJoints.insert(0, parentRigJnt)

    util.setupSpaceSwitch(aimCtrl,
                          localSpaceSwitcherJoints,
                          nameDetailLevel=2,
                          nameDetailStart=0,
                          spaceBlends=None)  # spaceBlends

    return ctrlGrp, allCtrls
