# mb_makeAdditiveIkSpline
# By Michael Buettner
#
# Copyright 2017-2018 Wildcard Studios
# October 11, 2017
#

import os
import sys
import re
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from math import *

from EvoRig import mb_rig_utilities as util
from collections import OrderedDict as od
from maya import OpenMaya

# import mb_rig_utilities as util
# util.debugging = False

__author__ = 'Michael Buettner'
__version__ = '1.0.1'
controlSizeSlider = "controlSizeSlider"
splineCountSlider = "splineCountSlider"


if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

if sys.version_info.major >= 3.12:    
    unicode = str

import ctrl; reload(ctrl);


# -----------------------------------------------------------------------------#
# Additive Spline Ctrl Module
# -----------------------------------------------------------------------------#


class additiveSplineCtrl(ctrl.ctrlModule):
    '''FK Control Wrapper class'''
    _isCtrl = True
    _label = 'Additive IK Spline'
    _color = (0.6, 0.4, 0.6)

    def __init__(self, *args, **kwargs):
        # super(type(self), self).__init__(*args, **kwargs)
        self._nodeAttributes = {}
        self.keyword = 'spine'
        self.startJoint = ''
        self.endJoint = ''
        self._nodeAttributes['startJoint'] = True
        self._nodeAttributes['endJoint'] = True
        self.forwardAxis = od([('X', [1, 0, 0]),
                               ('Y', [0, 1, 0]),
                               ('Z', [0, 0, 1])])
        self.splineSpanCount = 1
        self.newIKNaming = False
        self.enableTwist = True

        type(self).__bases__[0].__init__(self, *args, **kwargs)

    def findAndCreate(self,
                      root,
                      moduleSpaceSwitchList=None,
                      group=None,
                      controlSize=1.0,
                      mainCtrl=None,
                      **kwargs):
        '''Search Root Node for keywords and issue create command
           Should Be overwritten for each node to get proper args'''

        # since using mutable types are default arges can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []

        util.printdebug("Module " + str(self._index) + ' adding SplineIK, Keyword:' + str(self.keyword))

        startJoint, endJoint = util.getRigJoint([(self.startJoint or None), (self.endJoint or None)])

        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network' if self.keyword else f'{displayModuleName}_{self.getTitle()}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        spinejnts = util.findAllInChain(root, self.keyword)
        print(f'END JOINT: {endJoint}')
        if (spinejnts is not None):
            spinejnts.reverse()
        connect_chain = [startJoint.name().split('_RigJnt')[0], endJoint.name().split('_RigJnt')[0]] + [x.name().split('_RigJnt')[0] for x in spinejnts]
        util.connectMessage(networkNode, 'joints', connect_chain)
        if (endJoint and startJoint):
            spinejnts = None
        

        # print("StartJoint: " + str(startJoint))
        # print("EndJoint: " + str(endJoint))

        # util.printdebug("   Spine Joints: " + str(spinejnts))
        if not spinejnts and (not endJoint or not startJoint):
            raise ValueError('Joint not found in hierarchy: ' + self.keyword)

        splineControlGrp, splineCtrls = mb_makeAdditiveIkSpline(spinejnts,
                                                                startJoint=startJoint,
                                                                endJoint=endJoint,
                                                                conScale=self.moduleSize * 1.5 * controlSize,
                                                                splineSpanCount=self.splineSpanCount,
                                                                spaceSwitcherJoints=moduleSpaceSwitchList,
                                                                forwardAxis=self.forwardAxis,
                                                                group=group,
                                                                mainCtrl=mainCtrl,
                                                                spaceBlends=(self._spaceBlendDict if self.useSpaceBlending else None),
                                                                newIKNaming=self.newIKNaming,
                                                                root=root,
                                                                enableTwist=self.enableTwist,
                                                                networkNode=networkNode)

        if group:
            pm.parent(splineControlGrp, group)
        util.connectMessage(networkNode, 'controls', splineCtrls)

        self.createControlAttributes(splineCtrls)

        # set up retarget hints
        hints = {}
        hints[splineCtrls[0]] = self.startJoint
        endCtrl = [x for x in splineCtrls if re.findall('{}_ikCON$'.format(self.endJoint), str(x))][0]
        hints[endCtrl] = self.endJoint
        for x in splineCtrls:
            if re.findall('_fkCON$', str(x)):
                hints[x] = util.getPyNode(str(x)[:-6])

        for target, source in hints.items():
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(source) or source, target)
            self.setRetargetHintAttributes(target, *args, **kwargs)

        return splineCtrls


# -----------------------------------------------------------------------------#
#  Utitlity Functions
# -----------------------------------------------------------------------------#


def makeWindow():
    # Type in the name and the size of the window
    windowName = "mb_makeAdditiveIkSplineWindow"
    windowSize = (350, 120)
    # check to see if this window already exists
    if (cmds.window(windowName, exists=True)):
        cmds.deleteUI(windowName)
    window = cmds.window(windowName, title=windowName, widthHeight=(windowSize[0], windowSize[1]))

    cmds.columnLayout("mainColumn", adjustableColumn=True)
    cmds.text(label='mb Make Additive IK Spline', al='left')
    cmds.text(label='Version ' + __version__, al='right')

    cmds.intSliderGrp(controlSizeSlider, l="Control Size", min=1, max=100, fieldMaxValue=100000, value=3, step=1,
                      field=1, parent="mainColumn")
    cmds.intSliderGrp(splineCountSlider, l="Spline Span Count", min=1, max=10, fieldMaxValue=100000, value=1, step=1,
                      field=1, parent="mainColumn")

    # Button
    cmds.columnLayout("columnName02", columnAttach=('both', 5), rowSpacing=5, columnWidth=350)
    cmds.button(label="Make Additive Spline IK", command=mb_makeAdditiveIkSplineCommand,
                annotation='Create IKSpline. Select Root joint first.', parent="columnName02")
    cmds.showWindow(windowName)
    cmds.window(windowName, edit=True, widthHeight=(windowSize[0], windowSize[1]))


def lockandhide(sobj, leaverot, leavetrans, leavescale=False):
    #if type(sobj) not in [str, unicode]:
    #    sobj = str(sobj)
    sobj = str(sobj)
    if (leavetrans == 0):
        cmds.setAttr(sobj + ".tx", lock=True, keyable=False)
        cmds.setAttr(sobj + ".ty", lock=True, keyable=False)
        cmds.setAttr(sobj + ".tz", lock=True, keyable=False)
    if (leaverot == 0):
        cmds.setAttr(sobj + ".rx", lock=True, keyable=False)
        cmds.setAttr(sobj + ".ry", lock=True, keyable=False)
        cmds.setAttr(sobj + ".rz", lock=True, keyable=False)
    if (leavescale == 0):
        cmds.setAttr(sobj + ".sx", lock=True, keyable=False)
        cmds.setAttr(sobj + ".sy", lock=True, keyable=False)
        cmds.setAttr(sobj + ".sz", lock=True, keyable=False)


def mb_makeAdditiveIkSplineCommand(args):
    selection = cmds.ls(sl=True)
    for each in selection:
        cmds.select(each)
        mb_makeAdditiveIkSpline([each])


def vectorDifference(startNode, endNode):
    start = pm.xform(startNode, q=1, ws=1, t=1)
    end = pm.xform(endNode, q=1, ws=1, t=1)

    startV = OpenMaya.MVector(start[0], start[1], start[2])
    endV = OpenMaya.MVector(end[0], end[1], end[2])
    startToEnd = endV - startV
    dif = startToEnd.normal()
    # print('%s,%s,%s'%(dif.x,dif.y,dif.z))

    return (dif.x, dif.y, dif.z)


def mb_makeAdditiveIkSpline(joints=None, 
                            conScale=0, 
                            splineSpanCount=0, 
                            startJoint=None, 
                            endJoint=None,
                            spaceSwitcherJoints=None, 
                            forwardAxis=(1, 0, 0), 
                            group=None, 
                            mainCtrl=None,
                            spaceBlends=None,
                            newIKNaming=False,
                            root=None,
                            enableTwist=True,
                            networkNode=None):
                            
    if (joints == None):
        if (startJoint == None or endJoint == None):
            raise TypeError('startJoint and endJoint must be specified if no joints list is given.')
        parents = util.allParents(endJoint, includeInput=True)
        if (startJoint not in parents):
            raise TypeError('startJoint was not found in hierarchy of endJoint')
        startIndex = parents.index(startJoint)
        joints = parents[:startIndex + 1]
        joints.reverse()
    else:
        startJoint = joints[0]

    if (conScale == 0):
        conScale = cmds.intSliderGrp(controlSizeSlider, q=True, value=True)
    if (splineSpanCount == 0):
        splineSpanCount = cmds.intSliderGrp(splineCountSlider, q=True, value=True)
    chain = None

    if (len(joints) <= 1):
        if len(joints) == 1:
            jnt = joints[0]
        else:
            jnt = pm.selected(type='joint')

        sel = pm.selected(type='joint')
        util.printdebug(jnt)
        if not jnt:
            raise TypeError('A joint must either be specified, or selected.')
        jnt = jnt[0]

        chain = jnt.listRelatives(ad=True, type='joint')
        chain.reverse()
        chain.insert(0, jnt)
    elif (len(joints) > 1):
        jnt = joints[0]
        chain = joints
    
    firstjnt = jnt

    masterGrp = pm.group(em=True, name=str(firstjnt + "MasterGrp"))
    scaleGrp = pm.group(em=True, name=str(firstjnt + "ScaleGrp"))
    pm.parent(scaleGrp, masterGrp)
    pm.connectAttr(mainCtrl.name() + ".scale", scaleGrp.name() + ".scale")

    util.printdebug("Chain: " + str(chain))
    """ Duplicate joints for IK """
    ikjnts = []
    for i, jnt in enumerate(chain):
        util.printdebug("Duplicating for IK: " + jnt.name())
        # Duplicate one joint at a time
        dup = jnt.duplicate(parentOnly=True)[0]
        dup.rename(jnt.name() + '_ik')
        ikjnts.append(dup)
        # If the parent is in the chain, it has already been duplicated
        if jnt.getParent() in chain:
            jntIndex = chain.index(jnt.getParent())
            # ethanm - dup.setParent(ikjnts[jntIndex])
            util.setParent(dup, ikjnts[jntIndex])
        else:
            # ethanm - dup.setParent(scaleGrp)
            util.setParent(dup, scaleGrp)

    """ Duplicate joints for FK """
    fkjnts = []
    fkcompjnts = []
    for i, jnt in enumerate(chain):
        # Duplicate one joint at a time
        dup = jnt.duplicate(parentOnly=True)[0]
        dup.rename(jnt.name() + '_fk')
        fkjnts.append(dup)
        # Constrain the original with the new FK duplicate
        # pm.pointConstraint(dup, jnt)                     #Micro Controls constrain the main now instead of the fk joint
        # pm.orientConstraint(dup, jnt).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        # pm.scaleConstraint(dup, jnt)

        # Duplicate compensation joint to fix scale issue
        nextjnt = chain[min(len(chain) - 1, i + 1)]
        compdup = jnt.duplicate(parentOnly=True)[0]
        compdup.rename(jnt.name() + '_fkcomp')
        compdup.setAttr("segmentScaleCompensate", 1)        #Make sure this bone compensates scale!
        fkcompjnts.append(compdup)
        newconstraint = pm.pointConstraint(nextjnt, compdup, mo=False, weight=1)
        pm.delete(newconstraint)

        # ethanm - compdup.setParent(dup)
        util.setParent(compdup, dup)

        # If the parent is in the chain, it has already been duplicated
        if jnt.getParent() in chain:
            jntIndex = chain.index(jnt.getParent())
            # ethanm - dup.setParent(fkcompjnts[jntIndex])
            util.setParent(dup, fkcompjnts[jntIndex])
        else:
            # ethanm - dup.setParent(scaleGrp)
            util.setParent(dup, scaleGrp)

    startjnt = ikjnts[0]
    pm.makeIdentity(startjnt, apply = True)
    pm.makeIdentity(fkjnts[0], apply = True)

    ikchain = startjnt.listRelatives(ad=True, type='joint')
    util.printdebug("ikchain is:" + str(ikchain))
    endjnt = ikchain[0]
    util.printdebug("startjnt is:" + startjnt)
    util.printdebug("endjnt is:" + endjnt)

    endJntRot = pm.xform(endjnt, q=True, ws=True, ro=True)
    handle = pm.ikHandle(startJoint=startjnt,
                         endEffector=endjnt,
                         sol="ikSplineSolver",
                         pcv=False, scv=True,
                         ns=splineSpanCount,
                         ccv=True,
                         tws="linear",
                         roc=1)
    util.printdebug(handle)

    """ Parent IKHandle to scaleGrp """
    ikHandleSolver = handle[0]
    pm.parent(ikHandleSolver, scaleGrp)
    ikHandleSolver.hide()
    ikcurve = handle[2]
    pm.parent(ikcurve, masterGrp)
    ikcurve.hide()
    ikhandles = []
    cmds.select(str(ikcurve) + ".cv[0]")
    startcls = pm.cluster()[1]
    ikhandles.append(startcls)
    curveShape1 = pm.listRelatives(ikcurve, shapes=True)[0]
    cvs = curveShape1.getAttr('cp', s=1)
    midcls = []
    for i in range(1, cvs - 1):
        cmds.select(str(ikcurve) + ".cv[" + str(i) + "]")
        newcls = pm.cluster()[1]
        midcls.append(newcls)
        ikhandles.append(newcls)

    pm.select(str(ikcurve) + ".cv[" + str(cvs - 1) + "]")
    endcls = pm.cluster()[1]
    ikhandles.append(endcls)
    """print(startcls)
    print(endcls)
    print(midcls)
    print(startcls.name())"""
    startcls.rename("Start_" + startcls.name())
    endcls.rename("End_" + endcls.name())
    for cls in midcls:
        cls.rename("Mid_" + cls.name())

    """ Measure curve length for stretchy IK joints """
    prefix = ikcurve.name()
    splineNormalizeNode = prefix + 'spline_normalize_multiplyDivide'
    splineMultiplyNode = prefix + 'spline_multiplier_multiplyDivide'
    curveInfo = prefix + 'spline_curveInfo1'
    # CREATE CURVE INFO AND MULTIPLYDIVIDE NODES
    curveInfoNode = pm.arclen(ikcurve, ch=True)
    util.connectMessage(networkNode, 'curveInfoNodes', curveInfoNode)

    multiplierNode = pm.shadingNode('multiplyDivide', n=splineNormalizeNode + '1', au=True)
    splineNormalize = multiplierNode
    socket = multiplierNode + '.input1X'
    connector = curveInfoNode.name() + '.arcLength'
    pm.connectAttr(connector, socket, force=True)
    # SET INPUT2X TO ARCLENGTH VALUE AND SET MULTIPLEDIVED NODES OPERATION TO DIVIDE
    socketAttribute = '.input2X'
    multiplierNode.setAttr('operation', 2)
    arcLength = curveInfoNode.getAttr('arcLength')

    # Multiply original length by rig size
    rigSizeMultiplyNode = pm.shadingNode('multiplyDivide', n=splineMultiplyNode + 'Size', au=True)
    rigSizeMultiplyNode.setAttr('operation', 1)
    pm.connectAttr(mainCtrl.name() + '.scaleX', rigSizeMultiplyNode.name() + '.input1X')
    rigSizeMultiplyNode.setAttr('input2X', arcLength)
    pm.connectAttr(rigSizeMultiplyNode.name() + '.outputX', multiplierNode.name() + '.input2X')

    curveInfoNode.rename(curveInfo)

    """ Squash and stretch BC nodes and attrs on handle xform """
    stretchBC = pm.shadingNode('blendColors', asUtility=True, n=prefix + 'stretch_BC')
    squashBC = pm.shadingNode('blendColors', asUtility=True, n=prefix + 'squash_BC')
    util.connectMessage(networkNode, 'blendColors', [stretchBC, squashBC])

    pm.connectAttr(multiplierNode.name() + '.outputX', stretchBC + '.color1R')
    stretchBC.setAttr('color2R', 1)
    pm.addAttr(endcls, ln='stretch', at="float", k=True)
    pm.connectAttr(endcls.longName() + '.stretch', stretchBC + '.blender')

    pm.addAttr(endcls, ln='squash', at="float", k=True)
    pm.addAttr(endcls, ln='squashAmount', at="float", k=True)

    pm.connectAttr(multiplierNode.name() + '.outputX', squashBC + '.color1R')
    squashBC.setAttr('color2R', 1)
    endcls.squash >> squashBC.blender
   
    posctrls = []

    """ Main Control """
    mainCtrl, mainCtrlGrp = util.makeControl(pm.PyNode(startJoint), (conScale * 0.3, conScale * 1.5, conScale * 2),
                                             None, worldOrient=True)
    pm.parent(mainCtrlGrp, scaleGrp)
    posctrls.append(mainCtrl)

    worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    if worldUpAxis == 'Z':
        compareAxis = 2
    else:
        compareAxis = 1

    if worldUpAxis == 'Y' and (vectorDifference(startjnt, endjnt)[compareAxis] > 0.5):
        pm.select(mainCtrl.longName() + ".cv[0:" + str(pm.getAttr(mainCtrl + ".spans")) + "]", r=True)
        pm.rotate(0, 90, 0, os=True)

    """ Pivot Control """
    pivotCtrl, pivotGrp = util.makeControl(mainCtrl, conScale * 2, parentObj=mainCtrl, shape=5, worldOrient=True,
                                           ctrlName=mainCtrl.name().replace('_CON', '') + "_Pivot_CON",
                                           forwardAxis='X' if forwardAxis[0] == 1 else 'Y')
    pm.parent(pivotGrp, scaleGrp)
    posctrls.append(pivotCtrl)

    pivotTransform = pm.createNode('transform', n=pivotCtrl.name() + "_Pivot", parent=pivotCtrl)
    multNode = pm.shadingNode('multiplyDivide', asUtility=True)
    pm.connectAttr(pivotCtrl.name() + '.translate', multNode.name() + '.input1')
    pm.connectAttr(multNode.name() + '.output', pivotTransform.name() + '.translate')
    pm.setAttr(multNode.name() + '.input2', [-1, -1, -1])

    midposctrlgrps = []
    midposctrlsINH = []
    visctrls = []
    for i, cls in enumerate(ikhandles):
        cls.hide()
        pm.parent(cls, scaleGrp)
        sobj = str(cls)
        inherit = "CON" + sobj + "INH"
        inherit = pm.group(em=True, name=str(inherit))
        
        jntindex = min(len(ikjnts) - 1, i ) # * splineSpanCount
        ikjnt = ikjnts[jntindex]
        if not newIKNaming:
            clusterName = "" #"_c" + str(i)
        else:
            clusterNameBegin = cls.name().find("cluster")
            if clusterNameBegin >= 0:
                clusterName = cls.name()[clusterNameBegin:]
            else:
                clusterName = cls.name()

            clusterName = "_" + clusterName.replace("Mid_", "").replace("Handle", "").replace("uster", "")
        if (i >= (len(ikhandles) - 1)):  # make sure last control has name of last bone
            jntindex = len(chain) - 1
            clusterName = ""            #Do not add cluster name to start and end joint control
        elif (i == 0):
            clusterName = ""
        currentjnt = chain[jntindex]
        util.printdebug("joint name:" + currentjnt.name())
        util.printdebug("clusterName:" + clusterName)
        newControlName = currentjnt.name() + clusterName + "_ikCON"
        
        newControlName = newControlName.replace("_RigJnt", "")
        if (cls == endcls):
            ikjnt = ikjnts[len(ikjnts) - 1]
            conPivot = pm.xform(ikjnt, q=True, ws=True, rp=True)

        if (cls == endcls or cls == startcls):
            """Create Pos Control Cube Shape"""
            posctrl = pm.curve(d=1, p=[(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
                                       (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
                                       (-1, -1, 1), (1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1),
                                       (-1, 1, 1), (-1, 1, -1)],
                               name=newControlName)
        else:
            """Create Mid Pos Control Square"""
            posctrl = pm.curve(d=1, p=[(0, 1, 1), (0, -1, 1), (0, -1, -1), (0, 1, -1), (0, 1, 1)],
                               name=newControlName)
            midposctrlsINH.append(inherit)

        if (cls == endcls):
            endctrl = posctrl
        elif (cls == startcls):
            startctrl = posctrl

        spans = posctrl.getAttr("spans")
        cmds.select(posctrl.longName() + ".cv[0:" + str(spans) + "]", r=True)
        cmds.scale(conScale, conScale, conScale, r=True)
        posctrls.append(posctrl)
        util.lockAndHideAttributes(posctrl, hideScale=True)

        """Set INH pivot to parent pivot"""

        pm.parent(inherit, sobj, r=True)
        pm.parent(inherit, w=True)
        pm.parent(inherit, scaleGrp)
        conPivot = pm.xform(sobj, q=True, ws=True, rp=True)

        pm.xform(inherit, ws=True, t=[conPivot[0], conPivot[1], conPivot[2]])
        if (cls == endcls):
            pm.xform(inherit, ws=True, ro=[endJntRot[0], endJntRot[1], endJntRot[2]])
        else:
            newconstraint = pm.orientConstraint(ikjnt, inherit, mo=False)
            newconstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.delete(newconstraint)

        """Create Group node"""
        grpNode = pm.group(posctrl, n=str(posctrl) + "Grp")

        """Match grpNode transform to inherit"""
        pm.parent(grpNode, inherit, r=True)
        util.printdebug("parenting:" + grpNode.name())
        pm.parent(grpNode, w=True)
        """Parent grpNode to INH node"""
        pm.parent(grpNode, inherit)
        if (cls == endcls):
            endctrlGroup = grpNode
            endctrlInhGroup = inherit
        elif (cls == startcls):
            startctrlGroup = grpNode
            startctrlInhGroup = inherit
        else:
            midposctrlgrps.append(grpNode)

        """Constrain inherit to parent joint"""
        if (cls == endcls or cls == startcls):
            # jntparent = firstjnt.listRelatives(p=True)
            # if (jntparent is not None and len(jntparent) > 0):
            #    jntparent = jntparent[0]
            # util.printdebug( "jntparent is:" + jntparent)
            pm.parentConstraint(pivotTransform, inherit, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)  # mainCtrl
            lockandhide(inherit, 0, 0)

        """Constrain cluster to control"""
        pm.orientConstraint(posctrl, sobj, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.pointConstraint(posctrl, sobj, mo=True, weight=1)

        if (cls == endcls):
            pm.orientConstraint(endctrl, ikjnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

    """ Creating math nodes to handle squash and stretch logic """
    # jntMultNode handles base stretch logic
    jntMultNode = pm.shadingNode('multiplyDivide', n=splineMultiplyNode + str(1), au=True)

    # Reduce scaleY and scaleZ when stretching in scaleX
    inv_sqrt_node = pm.createNode("multiplyDivide", n=f'{jntMultNode}_invSqrtVol')
    inv_sqrt_node.setAttr("operation", 3)      
    inv_sqrt_node.setAttr("input2X", -0.5)  
    squashBC.outputR >> inv_sqrt_node.input1X   

    squash_amt = pm.createNode("multiplyDivide", n=f'{jntMultNode}_squashAmt')
    squash_amt.setAttr("operation", 3)      

    inv_sqrt_node.outputX >> squash_amt.input1X
    endcls.squashAmount >> squash_amt.input2X
    
    """ Make IK joints stretchy """
    for i, stretchjnt in enumerate(ikjnts):
        # Connect base scaleX stretch value 
        connectorAttribute1 = '.outputX'
        connector1 = splineNormalize.name() + connectorAttribute1
        socketAttribute1 = '.input'
        
        socket1 = jntMultNode.name() + (socketAttribute1 + '1X')
        
        # Connect additional scaleY/scaleZ values for squash and stretch
        pm.connectAttr(squash_amt.outputX, stretchjnt.sy, force=True)
        pm.connectAttr(squash_amt.outputX, stretchjnt.sz, force=True)
        pm.connectAttr(connector1, socket1, force=True)
        pm.connectAttr(stretchBC + '.outputR', stretchjnt.longName() + '.scaleX', force=True)

        # Clamp connection to skinned joint to ensure we will never hit an infinite value and break the skeleton
        skinned_jnt = pm.PyNode(stretchjnt.name().split('_RigJnt_ik')[0])
        clamp_node = pm.createNode('clamp', n=f'{stretchjnt}_clamp')
        util.connectMessage(networkNode, 'clamps', clamp_node)
        stretchjnt.sy >> clamp_node.input.inputR
        stretchjnt.sz >> clamp_node.input.inputG
        clamp_node.minR.set(0.001)
        clamp_node.minG.set(0.001)
        clamp_node.maxR.set(100000)
        clamp_node.maxG.set(100000)

        clamp_node.output.outputR >> skinned_jnt.sy
        clamp_node.output.outputG >> skinned_jnt.sz

    # Finished math node setup

    """ Stretch attribute """
    pm.addAttr(endctrl, ln='stretch', at="float", k=True, min=0, max=1)
    pm.connectAttr(endctrl + '.stretch', endcls + '.stretch')

    pm.addAttr(endctrl, ln='squash', at="float", k=True, min=0, max=1)
    endctrl.squash >> endcls.squash

    pm.addAttr(endctrl, ln='squashAmount', at="float", k=True, min=.2, max=5, dv=1)
    endctrl.squashAmount >> endcls.squashAmount    


    """ Constrain mid controls to start and end controls """
    for i, midctrlINH in enumerate(midposctrlsINH):
        if i < floor(len(midposctrlsINH) / 2.0):
            pm.parentConstraint(startctrl, midctrlINH, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        else:
            pm.parentConstraint(endctrl, midctrlINH, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        lockandhide(inherit, 0, 0)

    """ Make rotation control as parent for ik endctrl """
    newControlName = firstjnt.name() + "_RotCON"  # [-10:]
    rotctrl = pm.curve(d=1, p=[(0, 1, 1), (0, -1, 1), (0, -1, -1), (0, 1, -1), (0, 1, 1)],
                       name=newControlName)
    rotctrl.setAttr("visibility", keyable=False, cb=True)
    spans = rotctrl.getAttr("spans")
    cmds.select(rotctrl + ".cv[0:" + str(spans) + "]", r=True)
    pm.scale(conScale * 1.5, conScale * 1.5, conScale * 1.5, r=True)
    pm.parent(rotctrl, startctrl, r=True)
    pm.parent(rotctrl, w=True)
    pm.parent(endctrlGroup, rotctrl)

    """Create Group node to zero transforms"""
    grpNode = pm.group(em=True, n=str(rotctrl) + "Grp")
    pm.parent(grpNode, rotctrl, r=True)
    pm.parent(grpNode, w=True)
    pm.parent(grpNode, endctrlInhGroup)
    pm.parent(rotctrl, grpNode)

    """Create Group node to zero ROTCTRL transforms"""
    rotInhGrpNode = pm.group(em=True, n=str(rotctrl) + "InhGrp")
    pm.parent(rotInhGrpNode, rotctrl, r=True)
    pm.parent(rotInhGrpNode, w=True)
    pm.parent(rotInhGrpNode, grpNode)
    pm.parent(rotctrl, rotInhGrpNode)
    """ Inherit Rot """
    """inheritOrientGrp = pm.group(em=True, n=str(rotctrl) + "INH")
    pm.parent(inheritOrientGrp, rotctrl, r=True)
    pm.parent(inheritOrientGrp, w=True)
    pm.parent(inheritOrientGrp, scaleGrp)

    pm.orientConstraint(inheritOrientGrp, rotInhGrpNode, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
    """

    """ Inherit Rot for RotCtrl """
    """objparent = pm.listRelatives(sobj, p=True)
    if (objparent is not None):
        # jntparent = firstjnt.listRelatives(p=True)
        # if (jntparent is not None and len(jntparent) > 0):
        #    jntparent = jntparent[0]
        # cmds.orientConstraint(jntparent.name(), inheritOrientGrp, mo=True, weight= 1)
        pm.orientConstraint(pivotTransform, inheritOrientGrp, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.addAttr(rotctrl, ln="inheritRot", at="double", min=0, max=1, defaultValue=1, k=1)
        pm.setKeyframe(inheritOrientGrp, breakdown=0)

        pm.setDrivenKeyframe(inheritOrientGrp, at='blendPoint1', v=1, cd=rotctrl + '.inheritRot')
        pm.setDrivenKeyframe(inheritOrientGrp, at='blendOrient1', v=1, cd=rotctrl + '.inheritRot')

        list = pm.listConnections(inheritOrientGrp + ".rx", t='pairBlend', d=False, s=True)
        if (list is not None and len(list) > 0):
            blendnode = list[0]
            blendnode.setAttr("rotInterpolation", 1)
        rotctrl.setAttr("inheritRot", 0)
        pm.setDrivenKeyframe(inheritOrientGrp, at='blendOrient1', v=0, cd=rotctrl + '.inheritRot')
        rotctrl.setAttr("inheritRot", 1)
    """

    """ Create Visibility Control"""
    visctrl = pm.curve(degree=1, \
                       knot=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, \
                             16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30], \
                       point=[(0, 0, 0), \
                              (6.8580220752251786e-016, 5.6000000000000005, 0), \
                              (0.20683760000000073, 5.6279536000000006, 0), \
                              (0.39966240000000075, 5.7078255999999996, 0), \
                              (0.56568960000000068, 5.8343100000000003, 0), \
                              (0.69217500000000076, 6.0003378000000005, 0), \
                              (0.77204560000000089, 6.1931621999999997, 0), \
                              (0.80000600000000066, 6.4000000461260003, 0), \
                              (0, 6.4000000000000004, 0), \
                              (6.8580220752251786e-016, 5.6000000000000005, 0), \
                              (-0.20683759999999932, 5.6279536000000006, 0), \
                              (-0.39966239999999931, 5.7078256000000005, 0), \
                              (-0.56568959999999924, 5.8343100000000003, 0), \
                              (-0.69217499999999932, 6.0003378000000005, 0), \
                              (-0.77204559999999933, 6.1931622000000006, 0), \
                              (-0.80000599999999933, 6.4000000461260003, 0), \
                              (-0.77204559999999933, 6.6068376000000004, 0), \
                              (-0.69217499999999921, 6.7996623999999999, 0), \
                              (-0.56568959999999913, 6.965689600000001, 0), \
                              (-0.39966239999999914, 7.092175000000001, 0), \
                              (-0.20683759999999915, 7.1720456000000006, 0), \
                              (8.8174643017417381e-016, 7.200006000000001, 0), \
                              (0.20683760000000093, 7.1720456000000006, 0), \
                              (0.39966240000000092, 7.092175000000001, 0), \
                              (0.5656896000000009, 6.965689600000001, 0), \
                              (0.69217500000000098, 6.7996623999999999, 0), \
                              (0.77204560000000089, 6.6068376000000004, 0), \
                              (0.80000600000000066, 6.4000000461260003, 0), \
                              (-0.80000599999999933, 6.4000000461260003, 0), \
                              (0, 6.4000000000000004, 0), \
                              (8.8174643017417381e-016, 7.200006000000001, 0)] \
                       , n=str(firstjnt) + "_VisCON"
                       )

    spans = visctrl.getAttr("spans")
    cmds.select(visctrl.longName() + ".cv[0:" + str(spans) + "]", r=True)
    pm.scale(conScale * 0.6, conScale * 0.6, conScale * 0.6, r=True)
    if forwardAxis[0] == 1:
        cmds.rotate(90, 0, 90, os=True)

    worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    if worldUpAxis == 'Z':
        pm.rotate(0, 90, 0, os=True)

    visctrls.append(visctrl)

    """Create VisCON Group node to zero transforms"""
    grpNode = pm.group(em=True, n=str(visctrl) + "Grp")
    pm.parent(grpNode, startctrlInhGroup, r=True)
    pm.parent(grpNode, w=True)
    pm.parent(grpNode, startctrlInhGroup)
    """Parent vis control to group"""
    pm.parent(visctrl, startctrl, r=True)
    pm.parent(visctrl, w=True)
    pm.parent(visctrl, grpNode)
    lockandhide(visctrl, 0, 0, 0)
    """Add visibility attributes"""
    pm.addAttr(visctrl, ln="FK_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    pm.addAttr(visctrl, ln="IK_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    pm.addAttr(visctrl, ln="MidIK_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    pm.addAttr(visctrl, ln="Micro_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    pm.addAttr(visctrl, ln="First_Micro_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    pm.addAttr(visctrl, ln="Pivot_Visibility", at="bool", min=0, max=1, defaultValue=0, k=0)  # Hide pivot ctrl -MIC
    visctrl.setAttr("visibility", keyable=False, cb=True)
    visctrl.setAttr("FK_Visibility", keyable=False, cb=True)
    visctrl.setAttr("IK_Visibility", keyable=False, cb=True)
    visctrl.setAttr("MidIK_Visibility", keyable=False, cb=True)
    visctrl.setAttr("Micro_Visibility", keyable=False, cb=True)
    visctrl.setAttr("First_Micro_Visibility", keyable=False, cb=True)
    visctrl.setAttr("Pivot_Visibility", keyable=False, cb=True)  # Hide pivot ctrl -MIC

    """Connect Pivot visibility attributes -MIC"""
    pm.connectAttr(visctrl.longName() + '.Pivot_Visibility', pivotGrp.longName() + '.visibility')

    """Connect IK visibility attributes"""
    for i, ctrlgrp in enumerate(midposctrlgrps):
        cmds.connectAttr(visctrl.longName() + '.MidIK_Visibility', ctrlgrp.longName() + '.visibility')
    pm.connectAttr(visctrl.longName() + '.IK_Visibility', startctrlGroup.longName() + '.visibility')
    pm.connectAttr(visctrl.longName() + '.IK_Visibility', endctrlGroup.longName() + '.visibility')
    pm.connectAttr(visctrl.longName() + '.IK_Visibility', rotctrl.longName() + '.visibility')

    """ Twist Controls """
    """ WARNING: Must set ikHandle -> Forward Axis to Negative X after creation if joints have flipped rotations """
    ikHandleSolver.setAttr("dTwistControlEnable", enableTwist)
    ikHandleSolver.setAttr("dWorldUpType", 4)
    if (firstjnt.find('r_') == 0):
        ikHandleSolver.setAttr("dForwardAxis", 1)
    pm.connectAttr(startctrl.longName() + ".worldMatrix", ikHandleSolver.longName() + ".dWorldUpMatrix", force=True)
    pm.connectAttr(endctrl.longName() + ".worldMatrix", ikHandleSolver.longName() + ".dWorldUpMatrixEnd", force=True)
    fkctrls = []
    microctrls = []

    for i, jnt in enumerate(fkjnts):
        ikjnt = ikjnts[i]

        """ Create group above fk joints and connect rotation to ik joints """
        jntGroup = pm.group(em=True, n=jnt.name() + "Grp")

        pm.parent(jntGroup, jnt, r=True)
        pm.parent(jntGroup, w=True)
        jntparent = jnt.listRelatives(p=True)
        if (jntparent is not None and len(jntparent) > 0):
            jntparent = jntparent[0]
            pm.parent(jntGroup, jntparent)

        pm.parent(jnt, jntGroup)
        pm.connectAttr(ikjnt.longName() + '.rotate', jntGroup.longName() + '.rotate')
        pm.connectAttr(ikjnt.longName() + '.scale', jnt.longName() + '.scale')
        if (i == 0):
            pm.pointConstraint(ikjnt, jntGroup, mo=True)
            
            # ethanm - command error from parenting
            if jntGroup.getParent() != scaleGrp:
                pm.parent(jntGroup, scaleGrp)


        """********* Create group to resemble frozen jointOrient ******************"""
        orientGroup = pm.group(em=True, n=jnt.name() + "OrientGrp")

        pm.parent(orientGroup, jnt, r=True)
        pm.parent(orientGroup, w=True)
        jntparent = jntGroup.listRelatives(p=True)
        if (jntparent is not None and len(jntparent) > 0):
            jntparent = jntparent[0]
            pm.parent(orientGroup, jntparent)

        pm.parent(jntGroup, orientGroup)
        pm.connectAttr(ikjnt + '.jointOrient', orientGroup + '.rotate')

        if (i == 0):
            jnt.hide()
            ikjnt.hide()

        """******************** Create Micro Controls ********************"""
        """##############################################################"""

        sobj = str(jnt)
        suffix = "Grp"
        microinherit = ""
        microinherit = "CON_MICRO_" + util.getNiceControllerName(sobj, "_INH")
        microinherit = cmds.group(em=True, name=str(microinherit))

        newControlName = util.getNiceControllerName(sobj, "_MICRO_CON")
        """Create Pos Control Cube Shape"""
        if i > 0:
            microctrl = pm.curve(d=1, p=[(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
                                         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
                                         (-1, -1, 1), (1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1),
                                         (-1, 1, 1), (-1, 1, -1)],
                                 name=newControlName)
            spans = microctrl.getAttr("spans")
            cmds.select(microctrl + ".cv[0:" + str(spans) + "]", r=True)
            pm.scale(conScale * 0.5, conScale * 0.5, conScale * 0.5, r=True)
        else:
            microctrl = util.makeNurbsShape(9, name=newControlName, scale=conScale,
                                            forwardAxis='X' if forwardAxis[0] == 1 else 'Y')

        microctrls.append(microctrl)

        """Set INH pivot to parent pivot"""
        conPivot = pm.xform(microctrl, q=True, ws=True, rp=True)
        objparent = pm.listRelatives(sobj, p=True)[0]
        if (objparent is not None):
            pm.parent(microinherit, objparent, r=True)
            pm.parent(microinherit, w=True)
        else:
            parentPivot = [0, 0, 0]

        pm.parent(microinherit, scaleGrp)

        """Create Group node"""
        microgrpNode = pm.group(microctrl, n=str(microctrl) + "Grp")

        """Match microgrpNode transform to object"""
        pm.parent(microgrpNode, sobj, r=True)
        pm.parent(microgrpNode, w=True)
        """Parent microgrpNode to INH node"""
        pm.parent(microgrpNode, microinherit)
        """Connect visibility attribute"""
        if i > 0:
            pm.connectAttr(visctrl + '.Micro_Visibility', microgrpNode + '.visibility')
        else:
            pm.connectAttr(visctrl + '.First_Micro_Visibility', microgrpNode + '.visibility')

        """Constrain joint position to micro control"""
        pm.orientConstraint(microctrl, chain[i], mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.pointConstraint(microctrl, chain[i], mo=True, weight=1)
        pm.makeIdentity(microgrpNode, apply=True, t=1, r=1, s=1)

        util.lockAndHideAttributes(microctrl, hideScale=True)
        """******************** End of Create Micro Controls ********************"""
        """##############################################################"""

        """******************** Create FK controls ***************************"""

        sobj = str(jnt)
        suffix = "Grp"
        inherit = ""
        inherit = "CON" + sobj + "INH"
        inherit = pm.group(em=True, name=str(inherit))

        """Create Control"""
        ctrl = pm.circle(ch=0, o=1, r=1, nr=forwardAxis, name=util.getNiceControllerName(sobj, "CON"))
        ctrl = ctrl[0]

        fkctrls.append(ctrl)
        spans = ctrl.getAttr("spans")
        cmds.select(ctrl.longName() + ".cv[0:" + str(spans) + "]", r=True)
        pm.scale(conScale, conScale, conScale, r=True)
        pm.symmetricModelling(symmetry=False)
        # pm.rotate(90,90,0, os=True)
        cmds.select(ctrl.longName(), r=True)

        """Set INH pivot to parent pivot"""
        conPivot = pm.xform(ctrl, q=True, ws=True, rp=True)
        objparent = pm.listRelatives(sobj, p=True)[0]
        if (objparent is not None):
            pm.parent(inherit, objparent, r=True)
            pm.parent(inherit, w=True)
        else:
            parentPivot = [0, 0, 0]

        pm.parent(inherit, scaleGrp)

        """Create Group node"""
        grpNode = pm.group(ctrl, n=str(ctrl) + "Grp")

        """Match grpNode transform to object"""
        pm.parent(grpNode, sobj, r=True)
        pm.parent(grpNode, w=True)
        """Parent grpNode to INH node"""
        pm.parent(grpNode, inherit)
        """Connect visibility attribute"""
        pm.connectAttr(visctrl + '.FK_Visibility', grpNode + '.visibility')

        """Constrain inherit to parent joint"""
        if (objparent is not None):
            pm.orientConstraint(objparent, inherit, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.pointConstraint(objparent, inherit, mo=True, weight=1)

        """Constrain micro joint inherit to fk control. First micro is constrained to IK startctrl with a switch"""
        if i == 0:
            constrainList = [startctrl, ctrl]
            oriCns = pm.parentConstraint(constrainList, microinherit, mo=True)
            oriCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
            
            pm.addAttr(startctrl, at="bool", ln="followIk", k=True)
            startctrl.setAttr("followIk", False)
            weightAliases = oriCns.getWeightAliasList()
            for a, jnt in enumerate(constrainList):
                conditionNode = pm.shadingNode('condition', asUtility=True)
                conditionNode.setAttr("secondTerm", a)
                conditionNode.setAttr("colorIfTrueR", 1)
                conditionNode.setAttr("colorIfFalseR", 0)
                pm.connectAttr(startctrl.name() + ".followIk", conditionNode.name() + '.firstTerm')
                pm.connectAttr(conditionNode.name() + '.outColor.outColorR',
                               oriCns.name() + '.' + weightAliases[a].attrName(longName=True))
                print("+++++++++++++++++++++++++++++++++++++++++++++++++++")
                print("Weight Aliases:{}".format(weightAliases))
        else:
            pm.orientConstraint(ctrl, microinherit, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.pointConstraint(ctrl, microinherit, mo=True, weight=1)

        """Constrain joint position to control"""
        pm.orientConstraint(ctrl, sobj, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.pointConstraint(ctrl, sobj, mo=True, weight=1)
        pm.makeIdentity(grpNode, apply=True, t=1, r=1, s=1)

        util.lockAndHideAttributes(ctrl, hideScale=True)

        """ Inherit Rot """
        if (objparent is not None):
            pm.addAttr(ctrl, ln="inheritRot", at="double", min=0, max=1, defaultValue=1, k=1)
            ctrl.setAttr("visibility", keyable=False, cb=True)
            pm.setKeyframe(inherit, breakdown=0)
            #pm.setKeyframe(inherit, at='blendPoint1', breakdown=0)
            #pm.setKeyframe(inherit, at='blendOrient1', breakdown=0)

            pm.setDrivenKeyframe(inherit, at='blendPoint1', v=1, cd=ctrl + '.inheritRot')
            pm.setDrivenKeyframe(inherit, at='blendOrient1', v=1, cd=ctrl + '.inheritRot')

            list = pm.listConnections(inherit + ".rx", t='pairBlend', d=False, s=True)
            if (list is not None and len(list) > 0):
                blendnode = list[0]
                blendnode.setAttr("rotInterpolation", 1)

            ctrl.setAttr("inheritRot", 0)

            pm.setDrivenKeyframe(inherit, at='blendOrient1', v=0, cd=ctrl + '.inheritRot')
            ctrl.setAttr("inheritRot", 1)

        lockandhide(inherit, 0, 0)
        lockandhide(ctrl, 1, 1)

    """ Space Switches """

    parent = firstjnt.getParent()
    perObjectSpaceSwitcherJoints = spaceSwitcherJoints[:]
    if ((parent is not None) and parent not in perObjectSpaceSwitcherJoints):
        if parent != root:
            perObjectSpaceSwitcherJoints.insert(0, parent)
    elif (len(perObjectSpaceSwitcherJoints) > 1 and perObjectSpaceSwitcherJoints.index(parent) > 0):
        k = perObjectSpaceSwitcherJoints
        a, b = k.index(parent), 0
        k[b], k[a] = k[a], k[b]

    endctrlSpaceSwitcherJoints = perObjectSpaceSwitcherJoints[:]
    endctrlSpaceSwitcherJoints.insert(0, mainCtrl)

    if (len(perObjectSpaceSwitcherJoints) > 0):
        util.setupSpaceSwitch(mainCtrl, perObjectSpaceSwitcherJoints, inheritParentLevel=2, spaceBlends=spaceBlends)
        util.setupSpaceSwitch(endctrl, endctrlSpaceSwitcherJoints, inheritParentLevel=4, spaceBlends=spaceBlends)

    # Do not follow root by default, because root is not constrained
    """if (perObjectSpaceSwitcherJoints[0].name().find('root') >= 0):
        pm.setAttr(mainCtrl.name() + ".space", 1)
        pm.setAttr(endctrl.name() + ".space", 1)
    """
    
    # Make Sets

    # cmds.select(posctrls)
    # cmds.select(rotctrl, add=True)
    posRotCtrls = posctrls + [rotctrl]
    ikSet = pm.sets(posRotCtrls, name=str(firstjnt).replace('_RigJnt', '') + '_ik_ctrl_set')
    # cmds.select(fkctrls)
    fkSet = pm.sets(fkctrls, name=str(firstjnt).replace('_RigJnt', '') + '_fk_ctrl_set')
    microSet = pm.sets(microctrls, name=str(firstjnt).replace('_RigJnt', '') + '_micro_ctrl_set')

    mainSet = pm.sets(ikSet, fkSet, microSet, n=util.getNiceControllerName(str(firstjnt), '_spline_ctrl_set'))
    pm.sets(mainSet, edit=True, fe=[ikSet, fkSet, microSet])
    if group:
        util.addToSet(mainSet, group.name() + '_set')

    # Control Color
    allctrls = posctrls + fkctrls + visctrls + microctrls
    allctrls.append(rotctrl)
    for actrl in allctrls:
        shapes = pm.listRelatives(str(actrl), shapes=True)
        if shapes:
            ashape = shapes[0]
            if (actrl.find('l_') == 0):
                ashape.setAttr("overrideEnabled", 1)
                ashape.setAttr("overrideColor", 6)
            elif (actrl.find('r_') == 0):
                ashape.setAttr("overrideEnabled", 1)
                ashape.setAttr("overrideColor", 13)
            elif (actrl.find('c_') == 0):
                ashape.setAttr("overrideEnabled", 1)
                if (actrl.lower().find('microcon') > 0):
                    ashape.setAttr("overrideColor", 21)
                elif (actrl.lower().find('fkcon') > 0):
                    ashape.setAttr("overrideColor", 22)
                else:
                    ashape.setAttr("overrideColor", 17)

    pm.select(endctrl)

    return masterGrp, allctrls

