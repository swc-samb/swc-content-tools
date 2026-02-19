import sys, traceback
import re
import os
from math import *
import importlib
from functools import partial
from collections import OrderedDict as od

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMaya

from EvoRig import mb_rig_utilities as util
import mb_MakeSimpleFKControl
import cr_MakeEngineIK
#util.debugging = True


if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

reload(util)

__author__ = 'Michael Buettner, Mic Marvin'
__version__ = '0.1.82'  # <major>.<minor>.<revision>
controlSizeSlider = "controlSizeSlider"
splineCountSlider = "splineCountSlider"
#thighKeyword = "thigh"
ballKeyword = "ball"

ankleKeyword = "ankle"

kneeKeyword = "knee"

toeKeyword = "toe"

conScale = 2
legDict = {"thigh":0, "knee":1, "ankle":2, "ball":3, "toe":4}


import ctrl; reload(ctrl);
#import mb_MakeHumanLeg

#-----------------------------------------------------------------------------#
# IK/FK Leg Ctrl Module
#-----------------------------------------------------------------------------#

class legCtrl(ctrl.ctrlModule):
    """Leg Control Wrapper class"""
    _isCtrl = True
    _label = 'IK/FK Leg'
    _color = (0.4,0.6,0.6)
    _isLegCtrl = True

    def __init__(self, *args, **kwargs):    
        self._nodeAttributes = {}
        
        self.keyword = 'thigh'
        self.startJoint = ''
        self.endJoint = ''
        self.leftPrefix = ''
        self.rightPrefix = ''
        self._nodeAttributes['startJoint'] = True
        self._nodeAttributes['endJoint'] = True
        self.heelOffset = -30.0
        self.tipOffset = 40.0
        self.ballOffset = 0.0
        self.ikBaseOffset = -10.0
        self.twistKeyword = "twist"
        self.rollKeyword = "roll"
        self.flexAxis = od([('X','X'),
                            ('Y','Y'),
                            ('Z','Z'),
                            ('-X','-X'),
                            ('-Y','-Y'),
                            ('-Z','-Z')])
        self.forwardAxis = od([('X','X'),
                            ('Y','Y'),
                            ('Z','Z')])
        self.kneeSlide=0.1
        self.kneeSlideOffset=-10
        self.addInterIkPoleVector = False
        self.mirrorModule = False
        self.engineIK = False
        self.engineIKBallJoint = True
        self.humanLeg = False
        self.flyerLeg = False
        self.ballPivot = False
        self.heelOnFloor = False
        self.rollList = []
        self._nodeAttributes['rollList'] = True
        self.twistList = []
        self._nodeAttributes['twistList'] = True
        self.rollTwistAmount = 1
        self._rollTwistAmountDict = {}

        type(self).__bases__[0].__init__(self, *args, **kwargs)


    def findAndCreate(self,
                      root,
                      moduleSpaceSwitchList = None, 
                      group = None,
                      controlSize = 1.0,
                      mainCtrl=None,
                      **kwargs):
        """Search Root Node for keywords and issue create command
           Should Be overwritten for each node to get proper args"""

        #since using mutable types are default arges can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []

        util.printdebug("Module " + str(self._index) + ' adding leg, Keyword:' + str(self.keyword))

        leftPrefix = (kwargs.get('leftPrefix') or 'l_')
        rightPrefix = (kwargs.get('rightPrefix') or 'r_')
        
        startJoint, endJoint = util.getRigJoint([(self.startJoint or None), (self.endJoint or None)])
        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network' if self.keyword else f'{displayModuleName}_{self.getTitle()}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)
        
        # ethanm - tracking mirrored objects to correctly mirrored space blends   
        if (endJoint and startJoint):
            thighjnts = [startJoint]
            startJoints = [startJoint]
            endJoints = [endJoint]

            # ethanm - given object treated as not mirrored      
            mirrored = [False]

            mirroredEndJoint = False
            mirroredStartJoint = False
            if self.mirrorModule:
                mirroredStartJoint, mirroredEndJoint = util.getRigJoint([(util.mirrorName(self.startJoint, leftPrefix, rightPrefix) or None), (util.mirrorName(self.endJoint, leftPrefix, rightPrefix) or None)])
            if (mirroredEndJoint and mirroredStartJoint):
                thighjnts.append(mirroredStartJoint)
                startJoints.append(mirroredStartJoint)
                endJoints.append(mirroredEndJoint)

                # ethanm - mirrored object        
                mirrored.append(True)

        else:
            thighjnts = util.findAllInChain(root, self.keyword)
            if thighjnts == None:
                raise ValueError('Joint not found in hierarchy: ' + self.keyword )
            startJoints = [None]*len(thighjnts)
            endJoints = [None]*len(thighjnts)

            # ethanm - no way to reliably tell if keyword joints space blends should be mirrored or not 
            # ethanm - if mirrored spaceblending is needed set the module for one side and check mirror module
            mirrored = [False]*len(thighjnts)

        hint_sets = []
        legs = []
        allControls = []
        for k, j in enumerate(thighjnts):
            util.printdebug(j + str( k))
            util.printdebug("   Thigh Joint: " + str(j))
            print("\n   Thigh Joint: " + str(j))
            print("   startJoint: " + str(startJoint))
            print("   endJoint: " + str(endJoint))

            # ethanm - mirror spaceblend if control is a mirror of given joints
            if mirrored[k]:
                spaceBlends = (self._spaceBlendDict if self.useSpaceBlending else None)
            else:
                spaceBlends = ({util.mirrorName(a, leftPrefix, rightPrefix):b for a,b in self._spaceBlendDict.items()} if self.useSpaceBlending else None)
            leg_nodes = mb_makeLeg(thighJoint=j, 
                                   conScale=controlSize * self.moduleSize,
                                   FlexAxis=self.flexAxis, 
                                   forwardAxis=self.forwardAxis,
                                   SpaceSwitcherJoints=moduleSpaceSwitchList, 
                                   heelOffset=self.heelOffset,
                                   tipOffset=self.tipOffset,
                                   ballOffset=self.ballOffset,
                                   startJoint=startJoints[k],
                                   endJoint=endJoints[k],
                                   twistKeyword=self.twistKeyword,
                                   rollKeyword=self.rollKeyword,
                                   rollList=self.rollList,
                                   twistList=self.twistList,
                                   rollTwistAmount=self.rollTwistAmount,
                                   rollTwistAmountDict = self._rollTwistAmountDict,
                                   addInterIkPoleVector=self.addInterIkPoleVector,
                                   kneeSlideValue=self.kneeSlide,
                                   kneeSlideOffset=self.kneeSlideOffset,
                                   addEngineIK=self.engineIK,
                                   engineIKBallJoint=self.engineIKBallJoint,
                                   ikBaseOffset=self.ikBaseOffset,
                                   humanLeg=self.humanLeg,
                                   flyerLeg=self.flyerLeg,
                                   ballPivot=self.ballPivot,
                                   root=root,
                                   group=group,
                                   mainCtrl=mainCtrl,
                                   spaceBlends=spaceBlends,
                                   heelOnFloor=self.heelOnFloor,
                                   networkNode=networkNode)

            newLegGrp, legCtrls, engineIKCtrls, engineIKJoints = leg_nodes

            print(newLegGrp, legCtrls)
            legs.append(newLegGrp)
            allControls += legCtrls

            #set up hint mapping
            basename = lambda x: str(x).split('|')[-1].split(':')[-1]
            hint_set = {}
            hint_sets.append(hint_set)

            engineIKJoints = list(map(util.getExportJoint,engineIKJoints))
            for check in ['_fk_CON$', '_ik_CON$', '_orient_CON$', '{}_CON$'.format(basename(endJoints[k]))]:
                for x in [n for n in legCtrls if re.findall(check, str(n))]:
                    hint_set[x] = util.getPyNode(x.name()[:-(len(check)-1)])

            for x in [n for n in legCtrls if re.findall('PV_CON$', str(n))]:
                if self.engineIK:
                    hint_set[x] = util.getPyNode(x.name().replace('_PV_CON','_PV_ik'))
                else:
                    hint_set[x] = j
            for x in legCtrls:
                if cmds.objExists('{}.autoAnkle'.format(x)):
                    hint_set[x] = util.getPyNode(x.name()[:-4])
            
            if self.engineIK:
                for ejoint, ectr in zip(engineIKJoints, engineIKCtrls):
                     hint_set[ectr] = ejoint
                hint_set[util.getPyNode(engineIKJoints[0].name() + '_EngineIKCON')] = engineIKJoints[0]
            
        if group:
            pm.parent(legs, group)

        self.createControlAttributes(allControls)
        
        print('evoRetarget:')
        try:
            #set retarget hint attributes
            for hint_set in hint_sets:
                for ctr, joint in hint_set.items():
                    print(' ', joint, '>', ctr)
                    args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr)
                    self.setRetargetHintAttributes(ctr, *args, **kwargs)
        except:
            print("Exception in user code:")
            print('-'*60)
            traceback.print_exc() #file=sys.stdout
            print('-'*60)

        return allControls

    def string_to_tuple(self, string):
        mapping = {
            "X":(1, 0, 0),
            "-X":(1, 0, 0),
            "Y":(0, 1, 0),
            "-Y":(0, 1, 0),
            "Z":(0, 0, 1),
            "-Z":(0, 0, 1)
        }
        return mapping.get(string.upper(), "Invalid input")

    def validate(self, root, *args, **kwargs):
        """Run several checks for rig validation"""
        validationErrors = []

        # Check if module field is empty or not
        check = util.emptyModuleField(self, ["startJoint", "endJoint"])
        if check:
            print('=' * 80)
            print("THESE ARE THE MISSING VALUES: {}".format(check))
            print('=' * 80)
            validationErrors.append("\nModule Is Missing Required Values! {0}".format(check))
            return validationErrors  # If we don't have proper start/end joints nothing else works, return now.

        # Check that all joints are found
        startJoint, endJoint = util.getPyNode([(self.startJoint or None), (self.endJoint or None)])
        startJoints, endJoints = [startJoint], [endJoint]

        if not startJoint or not endJoint:
            thighjnts = util.findAllInChain(root, self.keyword)
            if not thighjnts:
                validationErrors.append(f"\nCouldn't Find Joints!\n Start:'{self.startJoint}' {bool(startJoint)} End:'{self.endJoint}' {bool(endJoint)}")

            startJoints, endJoints = thighjnts, [util.findInChain(jnt, toeKeyword) for jnt in thighjnts]

            if not all(endJoints):
                validationErrors.append("\nCouldn't Find End Joints:\n * {0}".format("\n * ".join(map(str, ((x[0].name(), x[1].name()) for x in (zip(startJoints, endJoints)))))))

        elif self.mirrorModule:
            mirroredStartJoint, mirroredEndJoint = util.getPyNode([(util.mirrorName(self.startJoint, self.leftPrefix, self.rightPrefix) or None),
                                                                     (util.mirrorName(self.endJoint, self.leftPrefix, self.rightPrefix) or None)])

            if not mirroredStartJoint or not mirroredEndJoint:
                validationErrors.append(f"\nCouldn't Find Mirrored Joints!\n Start:'{util.mirrorName(self.startJoint, self.leftPrefix, self.rightPrefix)}' {bool(mirroredStartJoint)} End:'{util.mirrorName(self.endJoint, self.leftPrefix, self.rightPrefix)}' {bool(mirroredEndJoint)}")

            startJoints.append(mirroredStartJoint)
            endJoints.append(mirroredEndJoint)

        fullChains = [util.getChainFromStartToEnd(start, end, raiseError=False) for start, end in zip(startJoints, endJoints)]
        chains = [x[:-1] for x in fullChains]  # Most of the time we want up to the ankle or wrist

        # Check that endjoint is a child of startjoint
        if any(isinstance(x, str) for x in fullChains):
            badJoints = util.errorOD(separator="*", tab=1)
            dictionary = {chain.split(":")[0]:chain.split(":")[1] for chain in fullChains}

            for key, value in dictionary.items():
                if not badJoints.get(key):
                    badJoints[key] = f" {value}:"
                badJoints[key] += f" {value} is not a child of {key}"

            print('=' * 80)
            print("THESE ARE THE BAD JOINTS: {}".format(dictionary.values()))
            print('=' * 80)

            if badJoints:
                validationErrors.append("\nEnd Joints Not Found Under Start Joints! {0}".format(badJoints))
                return validationErrors  # If we don't have proper start/end joints nothing else works, return now.

        # Check for planarity
        if self.humanLeg:
            checks = [util.jointChainNotPlanar(chain) for chain in chains]
            check = "".join(str(check) for check in checks)
        else:
            checks = [util.jointChainNotPlanar(chain) for chain in fullChains]
            check = "".join(str(check) for check in checks)

        print('=' * 80)
        print("THESE ARE THE BAD JOINTS: {}".format(check))
        print('=' * 80)

        if check:
            validationErrors.append("\nNon-Planar Joint Chain! {0}".format(check))

        # Check aim vector
        checks = [util.jointChainNotAimed(chain) for chain in chains]
        check = "".join(str(check) for check in checks)

        print('=' * 80)
        print(f"THESE ARE THE BAD JOINTS: {check}")
        print('=' * 80)

        if check:
            validationErrors.append("\nChild Joints Have Moved Out Of Alignment! {0}".format(check))

        # Check if joints are twisted
        checks = [util.jointsAreTwisted(chain) for chain in chains]
        check = "".join(str(check) for check in checks)

        print('=' * 80)
        print(f"THESE ARE THE BAD JOINTS: {check}")
        print('=' * 80)

        if check:
            validationErrors.append("\nJoints Are Twisted! {0}".format(check))

        # Check if flex axis matches ideal plane
        checks = [util.jointChainFlexAxisMatchesSideAxis(chain, self.flexAxis) for chain in chains]
        check = "".join(str(check) for check in checks)

        print('=' * 80)
        print(f"THESE ARE THE BAD JOINTS: {check}")
        print('=' * 80)

        if check:
            validationErrors.append("\nFlexAxis '{0}' Does Not Match Ideal Plane Axis! {1}".format(self.flexAxis, check))

        # Check twist and roll
        twistJoint = util.findAllInChain(startJoint, self.twistKeyword, allDescendents=True, disableWarning=True)
        twistMirror = util.findAllInChain(mirroredStartJoint, self.twistKeyword, allDescendents=True, disableWarning=True)
        rollJoint = util.findAllInChain(startJoint, self.rollKeyword, allDescendents=True, disableWarning=True)
        rollMirror = util.findAllInChain(mirroredStartJoint, self.rollKeyword, allDescendents=True, disableWarning=True)

        print('=' * 80)
        print("TWIST JOINTS ARE: {}".format(twistJoint))
        print("ROLL JOINTS ARE: {}".format(rollJoint))
        print("MIRRORED TWIST IS: {}".format(twistMirror))
        print("MIRRORED ROLL IS: {}".format(rollMirror))
        print('=' * 80)

        listTwistRollJoints = [x for i in (twistJoint, twistMirror, rollJoint, rollMirror) if i is not None for x in i]

        print('=' * 80)
        print("TWIST and ROLL JOINTS ARE: {}".format(listTwistRollJoints))
        print('=' * 80)

        check = util.jointsWithNonZeroAttributes(listTwistRollJoints)

        print('=' * 80)
        print("THESE ARE THE BAD JOINTS: {}".format(check))
        print('=' * 80)

        if check:
            validationErrors.append("\nTwist/Roll Joints Are Not Aligned With Parent! {0}".format(check))

        return validationErrors

    def initDynamicLayoutParameters(self, moduleLayout, ignoreList = None):
        ignoreList = ['rollList','twistList','twistKeyword', 'rollKeyword','rollTwistAmount', '_rollTwistAmountDict']                                
        super(type(self), self).initDynamicLayoutParameters(moduleLayout, ignoreList = ignoreList)

        rollText = self.rollList
        twistText = self.twistList
        
        if not util.is_iterable(rollText):
            rollText = [rollText]
        rollText = [str(node) for node in rollText]
        if not util.is_iterable(twistText):
            twistText = [twistText]
        twistText = [str(node) for node in twistText]

        #Roll/Twist objects button and field
        rollButton = pm.button("rollbutton" + str(self._index), 
                                label='Roll List >',
                                command=partial(self.updateRollTwistList, selected=True, add=True, listType='rollList'),
                                parent=moduleLayout)
        rollListTextField = pm.textField('RollListTextField'+ str(self._index), 
                                    text=','.join(rollText) if rollText else '', 
                                    editable=True, 
                                    changeCommand=partial(self.updateRollTwistList, selected=False,listType='rollList'), 
                                    annotation='',
                                    parent=moduleLayout)
        twistButton = pm.button("twistbutton" + str(self._index), 
                                label='Twist List >',
                                command=partial(self.updateRollTwistList, selected=True, add=True,listType='twistList'),
                                parent=moduleLayout)
        twistListTextField = pm.textField('TwistListTextField'+ str(self._index), 
                                    text=','.join(twistText) if twistText else '', 
                                    editable=True, 
                                    changeCommand=partial(self.updateRollTwistList, selected=False,listType='twistList'), 
                                    annotation='',
                                    parent=moduleLayout)
        
        pm.text('TwistText', label="Twist", parent=moduleLayout)

        twistKeywordTextField = pm.textField('twistKeywordTextField',
                            text=str(self.twistKeyword), 
                            editable=True, 
                            changeCommand=lambda val: (setattr(self, 'twistKeyword', val), self.updateRollTwistList()), 
                            annotation='',
                            parent=moduleLayout)

        self.setUI("twistKeyword", twistKeywordTextField)

        pm.text('RollText', label="Roll", parent=moduleLayout)
        
        rollKeywordTextField = pm.textField('rollKeywordTextField',
                            text=str(self.rollKeyword), 
                            editable=True, 
                            changeCommand=lambda val: (setattr(self, 'rollKeyword', val), self.updateRollTwistList()),
                            annotation='',
                            parent=moduleLayout)
        self.setUI("rollKeyword", rollKeywordTextField)
        
        #Twist/Roll Amount UI
        pm.separator(height=self._separatorHeight, style="none", parent=moduleLayout)
        width = [(1, self._moduleCW[1][1])]
        moduleLayout1 = pm.rowColumnLayout(nc=1, cw=width, columnAlign = (1,'left'), parent=moduleLayout) 
        
        frameLayout = pm.frameLayout("_rollTwistDictFrameLayout" + str(self._index), 
                                     label='Roll Twist Bones', 
                                     bgc=self._color,
                                     collapsable=True, 
                                     collapse=True, 
                                     parent=moduleLayout1)        
        
        rollTwistAmountfloatSliderGrp = pm.floatSliderGrp("rollTwistAmountfloatSliderGrp",
                                    l='Twist Roll Amount', 
                                    value=self.rollTwistAmount,
                                    step=0.001, 
                                    field=1, 
                                    min=0, 
                                    max=1,
                                    changeCommand=partial(setattr, self, "rollTwistAmount"),
                                    parent=frameLayout)
        
        moduleLayout2 = pm.rowColumnLayout(nc=1, cw=width, columnAlign = (1,'left'), parent=frameLayout)
        
        self.setUI('rollList', [rollButton, rollListTextField]) 
        self.setUI('twistList', [twistButton,twistListTextField])
        self.setUI('_rollTwistAmountDict', [moduleLayout1,frameLayout, rollTwistAmountfloatSliderGrp, moduleLayout2])
        self.updateRollTwistList()

#-----------------------------------------------------------------------------#
#  Utitlity Functions
#-----------------------------------------------------------------------------#


def getLegJoint(firstjnt, keyword, searchByName=True, chain=None):
    if searchByName:
        joint = util.findInChain(firstjnt, keyword, chain=chain)
    else:
        #chain = firstjnt.listRelatives( ad=True, type='joint')
        #chain.append(firstjnt)
        #chain.reverse()
        # print("################ getLegJoint firstjnt: " + str(firstjnt))
        # print("################ getLegJoint keyword : " + str(keyword))
        # print("################ getLegJoint Chain   : " + str(chain))
        joint = chain[legDict[keyword]]
    #print("Get Leg Joint returning: " + joint)
    return joint

def makeWindow():
    #Type in the name and the size of the window
    windowName = "mb_makeLegWindow"
    windowSize = (350, 120)
    #check to see if this window already exists
    if (cmds.window(windowName , exists=True)):
        cmds.deleteUI(windowName)
    window = cmds.window( windowName, title= windowName, widthHeight=(windowSize[0], windowSize[1]) )
    
    cmds.columnLayout( "mainColumn", adjustableColumn=True )
    cmds.text( label='mb Auto Rig', al='left' )
    cmds.text( label='Version '+ __version__, al='right' )
    
    cmds.intSliderGrp(controlSizeSlider, l="Control Size", min=1, max=100, fieldMaxValue=100000,value=3, step=1, field=1, parent = "mainColumn")
    #cmds.intSliderGrp(splineCountSlider, l="Spline Span Count", min=1, max=10, fieldMaxValue=100000,value=1, step=1, field=1, parent = "mainColumn")
    
    #Button
    cmds.columnLayout( "columnName02", columnAttach=('both', 5), rowSpacing=5, columnWidth=350)
    cmds.button(label = "Make Leg", command = mb_makeLegCommand, annotation='Create IK Leg. Select main joint first.', parent = "columnName02")
    cmds.showWindow( windowName )
    cmds.window( windowName, edit=True, widthHeight=(windowSize[0], windowSize[1]) )


def mb_makeLegCommand(args):
    selection = cmds.ls(sl=True)
    for each in selection:
        cmds.select(each)
        mb_makeLeg(pm.PyNode(each))
        
"""
def findInChain(parentjnt, findname):
    chain = parentjnt.listRelatives( ad=True, type='joint' )
    for i, jnt in enumerate(chain):
        
        aName = str(jnt.name())
        aName = aName.decode("utf-8").replace(u"\u007C", "_")       #replace vertical line character with "_"
        splitname = aName.split("_")[1]
        if (splitname.find(findname) >= 0) or (aName.find(findname) >= 0):
            return jnt
    
    raise TypeError('Joint not found in hierarchy: ' + findname + "  joint chain: " + str(chain) )
"""
def placePoleVector(legjoints):
    start = pm.xform(legjoints[0] ,q= 1 ,ws = 1,t =1 )
    mid = pm.xform(legjoints[1] ,q= 1 ,ws = 1,t =1 )
    end = pm.xform(legjoints[2] ,q= 1 ,ws = 1,t =1 )

    startV = OpenMaya.MVector(start[0] ,start[1],start[2])
    midV = OpenMaya.MVector(mid[0] ,mid[1],mid[2])
    endV = OpenMaya.MVector(end[0] ,end[1],end[2])

    startEnd = endV - startV
    startMid = midV - startV

    dotP = startMid * startEnd
    proj = float(dotP) / float(startEnd.length())
    startEndN = startEnd.normal()
    projV = startEndN * proj

    arrowV = startMid - projV
    arrowVN = arrowV.normal()
    arrowV = arrowVN * 0.5 * float(startEnd.length())
    finalV = arrowV + midV

    cross1 = startEnd ^ startMid
    cross1.normalize()

    cross2 = cross1 ^ arrowV
    cross2.normalize()
    arrowV.normalize()

    matrixV = [arrowV.x , arrowV.y , arrowV.z , 0 ,
    cross1.x ,cross1.y , cross1.z , 0 ,
    cross2.x , cross2.y , cross2.z , 0,
    0,0,0,1]

    matrixM = OpenMaya.MMatrix()

    OpenMaya.MScriptUtil.createMatrixFromList(matrixV , matrixM)

    matrixFn = OpenMaya.MTransformationMatrix(matrixM)

    rot = matrixFn.eulerRotation()

    #loc = cmds.spaceLocator()[0]
    outPos = (finalV.x , finalV.y ,finalV.z)
    outRot = ((rot.x/pi*180.0), (rot.y/pi*180.0), (rot.z/pi*180.0))
    return outPos, outRot
    #cmds.xform(loc , ws =1 , t= (finalV.x , finalV.y ,finalV.z))

    #cmds.xform ( loc , ws = 1 , rotation = ((rot.x/pi*180.0),
    #(rot.y/pi*180.0),
    #(rot.z/pi*180.0)))
    

def placeMultiJointPoleVector(start, end, ikh):
    transNode = pm.createNode( 'transform', n='transNode' , parent=ikh)
    tempPointConstraint = pm.pointConstraint([start, end], transNode, mo = False)
    pm.delete(tempPointConstraint)
    pm.xform(transNode, ws=0, rotation = (0,0,0))
    vec = ikh.getAttr('poleVector')
    transNode.translateBy(vec)
    pm.parent(transNode, w=True)
    outPos = pm.xform(transNode, translation=True, q=True, objectSpace=False)
    outRot = pm.xform(transNode, rotation=True, q=True, objectSpace=False)
    pm.delete(transNode)
    return outPos, outRot
    #pm.parent(heelRoll, heelRollTransform, r=True)


def createBlendColorBlend(IKJoint, FKJoint, bindJoint, switch):
    a = bindJoint
    b = IKJoint
    c = FKJoint
    
    rotBC = cmds.shadingNode('blendColors', asUtility = True, n = a + 'rotate_BC')
    tranBC = cmds.shadingNode('blendColors', asUtility = True, n = a + 'tran_BC')
    scaleBC = cmds.shadingNode('blendColors', asUtility = True, n = a + 'scale_BC')
    
    
    cmds.connectAttr(c + '.rotate', rotBC + '.color1')
    cmds.connectAttr(c + '.translate', tranBC + '.color1')
    cmds.connectAttr(c + '.scale', scaleBC + '.color1')
    
    cmds.connectAttr(b + '.rotate', rotBC + '.color2')
    cmds.connectAttr(b + '.translate', tranBC + '.color2')
    cmds.connectAttr(b + '.scale', scaleBC + '.color2')
    
    cmds.connectAttr(rotBC + '.output', a + '.rotate')
    cmds.connectAttr(tranBC + '.output', a + '.translate')
    cmds.connectAttr(scaleBC + '.output', a + '.scale')

    cmds.connectAttr(switch , rotBC + '.blender') #+ '.SwitchIkFk'
    cmds.connectAttr(switch , tranBC + '.blender')
    cmds.connectAttr(switch , scaleBC + '.blender')

    return [rotBC, tranBC, scaleBC]


def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(obj):
    return [ atoi(c) for c in re.split(r'(\d+)', obj.name()) ]

def createRollJoints(childJnt, parentJnt, constrainedParentJnt, switchCtrl = None, rollKeyword="roll", rollList=None, rollTwistAmount=1, rollTwistAmountDict = None):
    if rollList:
        rigRollJoints = []
        for jnt in rollList:
            rigJnt = util.findInChain(constrainedParentJnt, jnt.name()[2:] + '_RigJnt')
            if rigJnt:
                rigRollJoints.append(rigJnt)

    else:
        rigRollJoints = util.findAllInChain(constrainedParentJnt, rollKeyword, allDescendents=False, disableWarning=True)
        
        if not rigRollJoints:
            util.printdebug("No Roll joints found under parent joint: " + constrainedParentJnt.name())
            return

        rigRollJoints.sort(key=natural_keys)
    


    amount = len(rigRollJoints)
    util.printdebug("Roll joints: " + str(rigRollJoints))

    #maxOffset = pm.xform(childJnt, q=True, translation=True, objectSpace=True)[0]

    #Create Shoulder Inherit transform
    shoulderJnt = constrainedParentJnt.getParent()
    shoulderTransform = pm.createNode( 'transform', n=shoulderJnt.name() + "_INH" , parent=shoulderJnt)
    pm.parent(shoulderTransform, parentJnt.getParent())
    pm.parentConstraint(shoulderJnt, shoulderTransform, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

    # Top Roll joint
    rollTopJnt = pm.joint(parentJnt, name=parentJnt.name() + '_rollTop')
    rollAimJnt = pm.joint(childJnt, name=parentJnt.name() + '_rollAim')
    #pm.xform(rollAimJnt, translation=[maxOffset, 0, 0])
    pm.parent(rollAimJnt, rollTopJnt)
    pm.parent(rollTopJnt, shoulderTransform)        
    pm.pointConstraint(parentJnt, rollTopJnt, mo=True)
    pm.hide(rollTopJnt)

    firstRollJoint = rigRollJoints[0]
    for i, rigJnt in enumerate(rigRollJoints):      
        value = 1
        if rollTwistAmountDict is not None:
            slicedRollTwistAmountDict = {'_'.join(k.split('_')[1:]): v for k, v in rollTwistAmountDict.items()}
            parts = rigJnt.split('_')
            sliced = '_'.join(parts[1:-1])
            match = None
            for key in slicedRollTwistAmountDict:
                if sliced in key:  
                    match = key
                    break
            if match:
                value = slicedRollTwistAmountDict[match]
            else:
                value = 1
        if i == 0:
            continue
        rollFactor = (float(amount - i)/amount) * value
        orientCns = pm.orientConstraint([rollTopJnt, parentJnt], rigJnt, mo=True)
        if switchCtrl is not None:
            pm.createNode('multiplyDivide', n = f'{rigJnt}_multiplyDivide')
            pm.setAttr(f'{rigJnt}_multiplyDivide.input1.input1X',rollFactor)
            pm.connectAttr(switchCtrl + ".twistRollAmount",f'{rigJnt}_multiplyDivide.input2.input2X' )
            pm.connectAttr(f'{rigJnt}_multiplyDivide.output.outputX', f'{orientCns.name()}.{rollTopJnt}W0')
            pm.createNode('plusMinusAverage', n = f'{rigJnt}_plusMinusAverage')
            pm.setAttr(f'{rigJnt}_plusMinusAverage.operation', 2)
            pm.setAttr(f'{rigJnt}_plusMinusAverage.input1D[0]', 1)
            pm.connectAttr(f'{rigJnt}_multiplyDivide.output.outputX', f'{rigJnt}_plusMinusAverage.input1D[1]')
            pm.connectAttr(f'{rigJnt}_plusMinusAverage.output1D', f'{orientCns.name()}.{parentJnt}W1')
            #pm.orientConstraint(rollTopJnt, rigJnt, e=True, w= rollFactor ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            #pm.orientConstraint(parentJnt, rigJnt, e=True, w= 1.0 - rollFactor ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        else:
            pm.orientConstraint(rollTopJnt, rigJnt, e=True, w= rollFactor * rollTwistAmount  ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.orientConstraint(parentJnt, rigJnt, e=True, w= 1.0 - rollFactor * rollTwistAmount ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        orientCns.setAttr("interpType", 2)  # Set interpolation to Shortest - "Finds the shortest path between rotations from the constrained object to its targets using quaternion interpolation."
        orientCns.setAttr("offsetX", 0)
        orientCns.setAttr("offsetY", 0)
        orientCns.setAttr("offsetZ", 0)
        #print("       Amount: " + str(amount) + " i : " + str(i) + " factor: " + str(rollFactor))

    ikhandle = pm.ikHandle(startJoint=rollTopJnt, endEffector=rollAimJnt, sol="ikRPsolver")[0]
    pm.parent(ikhandle, childJnt)
    pm.xform(ikhandle, translation=[0, 0, 0])
    ikhandle.setAttr('poleVector', [0, 0, 0])
    ikhandle.rename(rollAimJnt.name() + '_ikh')

    orientCns = pm.orientConstraint([rollTopJnt, parentJnt], firstRollJoint, mo=True)
    firstRollJointFactor = 0.9*value
    if switchCtrl is not None and i == 0:
            pm.createNode('multiplyDivide', n = f'{firstRollJoint}_multiplyDivide')
            pm.setAttr(f'{firstRollJoint}_multiplyDivide.input1.input1X',firstRollJointFactor)
            pm.connectAttr(switchCtrl + ".twistRollAmount",f'{firstRollJoint}_multiplyDivide.input2.input2X' )
            pm.connectAttr(f'{firstRollJoint}_multiplyDivide.output.outputX', f'{orientCns.name()}.{rollTopJnt}W0')
            pm.createNode('plusMinusAverage', n = f'{firstRollJoint}_plusMinusAverage')
            pm.setAttr(f'{firstRollJoint}_plusMinusAverage.operation', 2)
            pm.setAttr(f'{firstRollJoint}_plusMinusAverage.input1D[0]', 1)
            pm.connectAttr(f'{firstRollJoint}_multiplyDivide.output.outputX', f'{firstRollJoint}_plusMinusAverage.input1D[1]')
            pm.connectAttr(f'{firstRollJoint}_plusMinusAverage.output1D', f'{orientCns.name()}.{parentJnt}W1')
    else:
        pm.orientConstraint(rollTopJnt, firstRollJoint, e=True, w=0.9*value ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.orientConstraint(parentJnt, firstRollJoint, e=True, w=1 - (0.9*value) ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
    orientCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
    orientCns.setAttr("offsetX", 0)
    orientCns.setAttr("offsetY", 0)
    orientCns.setAttr("offsetZ", 0)
    return rigRollJoints


def createTwistJoints(childJnt, parentJnt, constrainedParentJnt,switchCtrl=None, kneeslideEndJnt=None, twistKeyword="twist", twistList=None, rollTwistAmount=1, twistOffsetControl=None, rollTwistAmountDict = None):
    if twistList:
        rigTwistJoints = []
        for jnt in twistList:
            rigJnt = util.findInChain(constrainedParentJnt, jnt.name()[2:] + '_RigJnt')
            if rigJnt:
                rigTwistJoints.append(rigJnt)
    else:
        rigTwistJoints = util.findAllInChain(constrainedParentJnt, twistKeyword, allDescendents=False, disableWarning=True)
    
        if not rigTwistJoints:
            util.printdebug("No Twist joints found under parent joint: " + constrainedParentJnt.name())
            return

        rigTwistJoints.sort(key=natural_keys)

    amount = len(rigTwistJoints)
    util.printdebug("Twist joints: " + str(rigTwistJoints))

    #maxOffset = pm.xform(childJnt, q=True, translation=True, objectSpace=True)[0]

    mainJnt = pm.joint(parentJnt, name=parentJnt.name() + '_twistMain')
    aimJnt = pm.joint(childJnt, name=parentJnt.name() + '_twistAim')
    #pm.xform(aimJnt, translation=[maxOffset, 0, 0])
    if kneeslideEndJnt:
        pm.parent(mainJnt, kneeslideEndJnt)

    pm.parent(aimJnt, mainJnt)

    for i, rigJnt in enumerate(rigTwistJoints):
        value = 1
        if rollTwistAmountDict is not None:
            slicedRollTwistAmountDict = {'_'.join(k.split('_')[1:]): v for k, v in rollTwistAmountDict.items()}
            parts = rigJnt.split('_')
            sliced = '_'.join(parts[1:-1])
            match = None
            for key in slicedRollTwistAmountDict:
                if sliced in key:  
                    match = key
                    break
            if match:
                value = slicedRollTwistAmountDict[match]
            else:
                value = 1
        twistFactor = (float(i+1.0)/amount) * value
        orientCns = pm.orientConstraint([mainJnt, parentJnt], rigJnt, mo=True)
        print (rigJnt)
        if rollTwistAmountDict is not None:
            print (rollTwistAmountDict)
        if switchCtrl is not None:
            pm.createNode('multiplyDivide', n = f'{rigJnt}_multiplyDivide')
            pm.setAttr(f'{rigJnt}_multiplyDivide.input1.input1X',twistFactor)
            pm.connectAttr(switchCtrl+ ".twistRollAmount",f'{rigJnt}_multiplyDivide.input2.input2X' )
            pm.connectAttr(f'{rigJnt}_multiplyDivide.output.outputX', f'{orientCns.name()}.{mainJnt}W0')
            pm.createNode('plusMinusAverage', n = f'{rigJnt}_plusMinusAverage')
            pm.setAttr(f'{rigJnt}_plusMinusAverage.operation', 2)
            pm.setAttr(f'{rigJnt}_plusMinusAverage.input1D[0]', 1)
            pm.connectAttr(f'{rigJnt}_multiplyDivide.output.outputX', f'{rigJnt}_plusMinusAverage.input1D[1]')
            pm.connectAttr(f'{rigJnt}_plusMinusAverage.output1D', f'{orientCns.name()}.{parentJnt}W1')

            #pm.orientConstraint(parentJnt, rigJnt, e=True, w= 1.0 - twistFactor ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        else:
            pm.orientConstraint(mainJnt, rigJnt, e=True, w= twistFactor * rollTwistAmount ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
            pm.orientConstraint(parentJnt, rigJnt, e=True, w= 1.0 - twistFactor * rollTwistAmount ).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        orientCns.setAttr("interpType", 2) # Set interpolation to Shortest - "Finds the shortest path between rotations from the constrained object to its targets using quaternion interpolation."
        orientCns.setAttr("offsetX", 0)
        orientCns.setAttr("offsetY", 0)
        orientCns.setAttr("offsetZ", 0)

    ikhandle, effectr = pm.ikHandle(startJoint=mainJnt, endEffector=aimJnt, sol="ikSCsolver") 
    pm.parent(ikhandle, childJnt)
    pm.xform(ikhandle, translation=[0, 0, 0])
    ikhandle.setAttr('poleVector', [0, 0, 0])
    ikhandle.rename(aimJnt.name() + '_ikh')
    effectr.rename(aimJnt.name() + '_effector')

    #Add twistOffset attribute to control to get more manual control of the twist
    if twistOffsetControl:
        pm.addAttr(twistOffsetControl, ln = "twistOffset", at= "double", defaultValue=0.0, k=1)
        pm.connectAttr(twistOffsetControl.name()+ '.twistOffset', effectr.name() + ".rotateX")    
    return rigTwistJoints

#--------------------------------------------------------------------------------------------          -----------------------------------------------------------------------
#-------------------------------------------------------------------------------------------- Make Leg -----------------------------------------------------------------------
#--------------------------------------------------------------------------------------------          -----------------------------------------------------------------------
def mb_makeLeg(thighJoint=None,
               conScale = 0, 
               FlexAxis="Z", 
               forwardAxis="X",
               SpaceSwitcherJoints=[], 
               heelOffset= -30, 
               tipOffset= 40, 
               ballOffset=0, 
               startJoint=None, 
               endJoint=None,
               twistKeyword="twist",
               rollKeyword="roll",
               rollList=[],
               twistList=[],
               rollTwistAmount=1,
               rollTwistAmountDict = {},
               addInterIkPoleVector=False,
               addHeelRoll=True,
               kneeSlideValue=0.1,
               kneeSlideOffset=0.0,
               addEngineIK=False,
               engineIKBallJoint=True,
               ikBaseOffset=0.0,
               humanLeg=False,
               flyerLeg=False,
               ballPivot=False,
               root=None,
               group=None,
               mainCtrl=None,
               spaceBlends=None,
               heelOnFloor=False,
               networkNode=None):

    try:
        #util.debugging = True

        if conScale == 0:
            conScale = cmds.intSliderGrp(controlSizeSlider, q=True, value=True)
        #splineSpanCount = cmds.intSliderGrp(splineCountSlider, q=True, value=True)
        findJointsByName = True
        jnt = None

        if (startJoint != None and endJoint != None):
            pass
            
        else:
            if (thighJoint == None):
                jnt = pm.selected( type='joint' )
                if not jnt:
                    raise ValueError( 'A joint must either be specified, or selected.' )
                jnt = jnt[0]
                thighJoint = jnt
                #raise ValueError( 'startJoint and endJoint must be specified if no thighJoint is given.' )
            else:    
                jnt = thighJoint
                    
            #relativesChain = jnt.listRelatives( ad=True, type='joint' )
            startJoint = jnt
            endJoint = util.findInChain(jnt, toeKeyword)
            #chain.reverse()
            #chain.insert( 0, jnt )

        parents = util.allParents(endJoint, includeInput=True)
        if (startJoint not in parents):
            raise ValueError( 'startJoint was not found in hierarchy of endJoint' )
        startIndex = parents.index(startJoint)
        chain = parents[:startIndex+1]
        chain.reverse()
        findJointsByName = False
        thighJoint = startJoint
        jnt = thighJoint

        util.printdebug("Making leg for chain: " + str(chain))

        chainLength = len(legDict)
        hasToeJoint = True
        if legDict[toeKeyword] > (len(chain)-1):
            hasToeJoint = False
            chainLength -=1
        
        if len(chain) < chainLength:
            pm.warning('Make Leg Error: Given joint chain length of {} is not long enough for Leg Control! Needs {}! {}'.format(len(chain), 
                                                                                                                                chainLength,
                                                                                                                                ' '.join(map(str,chain))))
            return
        connect_chain = [x.name().split('_RigJnt')[0] for x in chain]
        util.connectMessage(networkNode, 'joints', connect_chain)
        firstjnt = jnt
        masterGrp = pm.group(em=True, name= str(util.getNiceControllerName(firstjnt, "MasterGrp") ))

        """ Duplicate joints for IK """
        ikjnts = []
        intikjnts = []
        fkjnts = []
        outjnts = []
        for i, jnt in enumerate(chain):
            # Duplicate one joint at a time
            dup = jnt.duplicate( parentOnly=True )[0]
            dup.rename( jnt.name() + '_ik' )
            ikjnts.append( dup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - dup.setParent( ikjnts[jntIndex] )
                util.setParent(dup, ikjnts[jntIndex])
            else:
                # ethanm - dup.setParent( masterGrp )
                util.setParent(dup, masterGrp)

            intikdup = jnt.duplicate( parentOnly=True )[0]
            intikdup.rename( jnt.name() + '_INT_ik' )
            intikjnts.append( intikdup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - intikdup.setParent( intikjnts[jntIndex] )
                util.setParent(intikdup, intikjnts[jntIndex] )
            else:
                # ethanm - intikdup.setParent( masterGrp )
                util.setParent(intikdup, masterGrp )

            fkdup = jnt.duplicate( parentOnly=True )[0]
            fkdup.rename( jnt.name() + '_fk' )
            fkjnts.append( fkdup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - fkdup.setParent( fkjnts[jntIndex] )
                util.setParent(fkdup, fkjnts[jntIndex] )
            else:
                # ethanm - fkdup.setParent( masterGrp )
                util.setParent(fkdup, masterGrp )

            #Output joints
            outdup = jnt.duplicate( parentOnly=True )[0]
            outdup.rename( jnt.name() + '_out' )
            outjnts.append( outdup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - outdup.setParent( outjnts[jntIndex] )
                util.setParent(outdup, outjnts[jntIndex] )
            else:
                # ethanm - outdup.setParent( masterGrp )
                util.setParent(outdup, masterGrp )
        

        startjnt = intikjnts[0]
        pm.makeIdentity(startjnt, apply = True)
        pm.makeIdentity(ikjnts[0], apply = True)
        pm.makeIdentity(fkjnts[0], apply = True)
        pm.makeIdentity(outjnts[0], apply = True)

        inter_ik_anklejnt = getLegJoint(intikjnts[0], ankleKeyword, findJointsByName, intikjnts)
        inter_ik_balljnt = getLegJoint(intikjnts[0], ballKeyword, findJointsByName, intikjnts)

        out_kneejnt = getLegJoint(outjnts[0], kneeKeyword, findJointsByName, outjnts)
        out_anklejnt = getLegJoint(outjnts[0], ankleKeyword, findJointsByName, outjnts)
        out_balljnt = getLegJoint(outjnts[0], ballKeyword, findJointsByName, outjnts)

        #util.printdebug( "startjnt is:" + startjnt)
        #util.printdebug( "balljnt is:" + inter_ik_balljnt)

        #endJntRot = cmds.xform(inter_ik_balljnt.name(), q=True, ws=True, ro=True)
        """ Create IK Handle for intermediate IK (3-bone)"""
        pm.parentConstraint(thighJoint.getParent(), startjnt, mo=True, skipRotate=["x","y","z"]).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        print("startjnt :" + str(startjnt))
        print("inter_ik_balljnt :" + str(inter_ik_balljnt))
        inter_handle, effectr = pm.ikHandle(startJoint=startjnt, endEffector=inter_ik_balljnt, sol="ikRPsolver")
        inter_leg_ikh = inter_handle
        inter_leg_ikh.rename("inter_leg_ikh")
        inter_leg_ikh.hide()
        effectr.rename(inter_ik_balljnt.name() + '_effector')
        pm.parent(inter_leg_ikh, masterGrp)
        #pm.parentConstraint(thighJoint.getParent(), startjnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """Pole Vector"""
        in_thighjnt = firstjnt
        in_kneejnt = getLegJoint(firstjnt, kneeKeyword, findJointsByName, chain)
        in_anklejnt = getLegJoint(firstjnt, ankleKeyword, findJointsByName, chain)
        in_balljnt = getLegJoint(firstjnt, ballKeyword, findJointsByName, chain)

        pvTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(), '_PV_transform') , parent=in_kneejnt)
        #pvTransform.setTranslation((-5*conScale,0,10*conScale))
        pm.parent(pvTransform, w=True)
        polePos, poleRot = placePoleVector([in_thighjnt, in_kneejnt, in_anklejnt])
        pm.xform(pvTransform, ws=1, t = polePos)
        #if (len(SpaceSwitcherJoints) > 0):
        #    pm.parent(pvTransform, SpaceSwitcherJoints[0])
        pm.parent(pvTransform, masterGrp)

        worldUpAxis = pm.upAxis(q=True, axis=True).upper()
        rotateShape=[-90,0,0]
        aimUpVector = [0,1,0]
        if worldUpAxis == 'Z':
            rotateShape = [90,0,90]
            aimUpVector = [0,0,1]

        poleVectorCtrl, ctrlGrp = util.makeControl(pvTransform, conScale, constrainObj=pvTransform, worldOrient=True, shape=2, rotateShape=rotateShape, forwardAxis=forwardAxis)
        poleVectorINH = poleVectorCtrl.getParent()
        aimCns = pm.aimConstraint(out_kneejnt, poleVectorINH, aimVector = (0, 0, -1) , upVector = aimUpVector , worldUpType = "scene", skip =['x','z'])
        pm.delete(aimCns)

        poleVectorTarget = None
        if addInterIkPoleVector:
            inter_pvTransform = pm.createNode( 'transform', n=util.getNiceControllerName(thighJoint.name(), '_inter_PV_transform') , parent=in_kneejnt)
            pm.parent(inter_pvTransform, w=True)
            inter_polePos, inter_poleRot = placeMultiJointPoleVector(in_thighjnt, in_balljnt, inter_leg_ikh)
            pm.xform(inter_pvTransform, ws=1, t = inter_polePos)
            pm.xform(inter_pvTransform, ws=1, ro = inter_poleRot)
            pm.parent(inter_pvTransform, poleVectorCtrl)
            poleVectorTarget = inter_pvTransform
        else:
            poleVectorTarget = poleVectorCtrl

        inter_leg_poleVectorConstraint = pm.poleVectorConstraint(poleVectorTarget, inter_leg_ikh)

        pm.parent(ctrlGrp, masterGrp)

        """ Secondary IK """

        ik_thighjnt = ikjnts[0]
        ik_anklejnt = ikjnts[1]

        ik_kneejnt = getLegJoint(ikjnts[0], kneeKeyword, findJointsByName, ikjnts)
        ik_anklejnt = getLegJoint(ikjnts[0], ankleKeyword, findJointsByName, ikjnts)
        ik_balljnt = getLegJoint(ik_thighjnt, ballKeyword, findJointsByName, ikjnts)
        if hasToeJoint:
            ik_toejnt = getLegJoint(ik_thighjnt, toeKeyword, findJointsByName, ikjnts)

        ikhandle1, effectr = pm.ikHandle(startJoint=ik_thighjnt, endEffector=ik_anklejnt, sol="ikRPsolver")
        ankle_ikh = ikhandle1
        ankle_ikh.rename("ankle_ikh")
        ankle_ikh.hide()
        effectr.rename(ik_anklejnt.name() + '_effector')

        pm.parent(ankle_ikh, inter_ik_balljnt, a=True)
        pm.parentConstraint(thighJoint.getParent(), ik_thighjnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """ Add transform to PoleVector so EngineIK joints are positioned correctly even in FK mode """
        poleVectorFKConstrainTarget = fkjnts[1]
        poleikfkGrp = pm.group(em=True, n=str(poleVectorCtrl.name()) + "_ikfk")
        pm.parent(poleikfkGrp, poleVectorCtrl, r=True)
        #pm.poleVectorConstraint(poleikfkGrp, ankle_ikh)      #Add PoleVector Constraint
        poleVectorFKParentConstraint = pm.parentConstraint([poleVectorCtrl, poleVectorFKConstrainTarget], poleikfkGrp, mo=True, weight=1)     #Add constraint so control follows the FK transforms when IK is inactive
        poleVectorFKParentConstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.poleVectorConstraint(poleVectorCtrl, ankle_ikh)

        ball_ikh = None
        ikhandle2, effectr = pm.ikHandle(startJoint=ik_anklejnt, endEffector=ik_balljnt, sol="ikSCsolver")
        ball_ikh = ikhandle2
        ball_ikh.rename("ball_ikh")
        ball_ikh.hide()
        effectr.rename(ik_balljnt.name() + '_bll_effector')
        pm.parent(ball_ikh, inter_ik_anklejnt, a=False)

        """ Control """
        if humanLeg or flyerLeg:
            pivotObject = ik_anklejnt
        else:
            pivotObject = ik_balljnt

        if ballPivot:
            pivotObject = ik_balljnt

        if flyerLeg:
            # For the flyer we always want to use the ball joint for offset -MM
            offsetRot = pm.xform(ik_balljnt, q=True, ws=True, ro=True)
            posCtrl, ctrlGrp = util.makeControl(pivotObject, conScale, None)      #ik_balljnt          constrainObj=inter_leg_ikh
        else :
            offsetRot = (0,0,0)
            posCtrl, ctrlGrp = util.makeControl(pivotObject, conScale, None, worldOrient=True)      #ik_balljnt          constrainObj=inter_leg_ikh
        pm.parent(ctrlGrp, masterGrp)
        #pm.parentConstraint(posCtrl, inter_leg_ikh, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        #Create transform that will be child of posCtrl but also child of the heel, ball and tip pivot controls.
        posCtrlTransform = pm.createNode( 'transform', n=util.getNiceControllerName(posCtrl.name(),"_SubTransform") , parent=posCtrl)
        pm.parentConstraint(posCtrlTransform, inter_leg_ikh, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        # Changing this constraint from orientConstraint to parentConstraint because orientConstraint was causing severe flipping on right side while FK/IK Blending - MM
        pm.parentConstraint(posCtrlTransform, ik_balljnt, mo=True, skipTranslate=["x", "y", "z"]).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        rotateAnkleShape = [90,-90,0]  #[90,-90,0]
        if inter_ik_balljnt.name().find('r_') == 0:
            rotateAnkleShape = [90,90,0]
        #if worldUpAxis == 'Z':
        #    rotateAnkleShape[2] = -90

        ankleCtrl, ankleCtrlGrp = util.makeControl(inter_ik_balljnt, conScale * 1, None, parentObj=None, shape=2, 
                                                rotateShape=rotateAnkleShape, translateShape=[0,1,0],
                                                ctrlName=util.getNiceControllerName(inter_ik_anklejnt.name().replace('_INT_ik', ''), '_CON'),
                                                forwardAxis=forwardAxis) #parentObj=inter_ik_anklejnt
        
        pm.parent(ankleCtrlGrp, masterGrp)
        pm.setAttr(ankleCtrl.name() + ".rx", lock=True, keyable=False)

        
        """ Knee slide joint """
        kneeslideJnt = pm.joint(out_kneejnt, name=util.getNiceControllerName(out_kneejnt.name() , "_Slide"))
        pcons = pm.pointConstraint(out_anklejnt, kneeslideJnt, mo=False)
        pm.delete(pcons)
        kneeslideEndJnt = pm.joint(out_kneejnt, name=util.getNiceControllerName(out_kneejnt.name() , "_SlideEnd"))
        pm.parent(kneeslideEndJnt, kneeslideJnt, r=False)

        negativeFlex = False
        if FlexAxis.find('-') == 0:
            negativeFlex = True
            FlexAxis = FlexAxis[1:]

        rotateChannel = ".rotate" + FlexAxis.upper()

        kneeSlideMultNode = pm.shadingNode('multiplyDivide',  asUtility=True)
        clampNode = pm.shadingNode('clamp',  asUtility=True)
        kneeSlideMinusNode = pm.shadingNode('plusMinusAverage',  asUtility=True)
        kneeSlideMultNode.setAttr("input2.input2X", 0.1)
        if not negativeFlex:
            clampNode.setAttr("maxR", 180)
        else:
            clampNode.setAttr("maxR", 0)
            clampNode.setAttr("minR", -180)

        pm.connectAttr(out_kneejnt + rotateChannel, kneeSlideMinusNode.name() + ".input1D[0]")
        pm.connectAttr(kneeSlideMinusNode.name() + ".output1D", clampNode.name()+ '.inputR')
        pm.connectAttr(clampNode.name()+ '.outputR', kneeSlideMultNode.name()+ '.input1.input1X')
        pm.connectAttr(kneeSlideMultNode.name()+ '.output.outputX', kneeslideJnt.name()+ rotateChannel) #'.rotateZ'

        
        """ Toe IK Handle       Disabled because this was causing Trike Hind Leg to fail
        if hasToeJoint:
            ikhandle_toe, effectr = pm.ikHandle(name=ik_toejnt.name() + "_ikh", startJoint=ik_balljnt, endEffector=ik_toejnt, sol="ikSCsolver")
            pm.parent(ikhandle_toe, masterGrp)
            ikhandle_toe.hide()
            ikhandle_toe.rename("toe_ikh")
            effectr.rename(ik_toejnt.name() + '_toe_effector')
        """

        """ FK Controls """
        mainfkjnts = fkjnts[1:4]
        firstfkjnt = fkjnts[0]
        #mainfkjnts.remove(firstfkjnt)
        fkGrps, fkControls = mb_MakeSimpleFKControl.mb_makeSimpleFKControl(joints=mainfkjnts, 
                                                                           conScale=conScale * 0.5, 
                                                                           SpaceSwitcherJoints=SpaceSwitcherJoints, 
                                                                           createSet=False,
                                                                           spaceBlends=spaceBlends)
        fkGrp, firstfkcontrols = mb_MakeSimpleFKControl.mb_makeSimpleFKControl(joints=[firstfkjnt], 
                                                                               conScale=conScale * 0.5, 
                                                                               SpaceSwitcherJoints=SpaceSwitcherJoints,
                                                                               parentObj=thighJoint.getParent(), 
                                                                               createSet=False,
                                                                               spaceBlends=spaceBlends)
        fkControls.append(firstfkcontrols[0])
        pm.parent(fkGrps, masterGrp)
        pm.parent(fkGrp, masterGrp)

        if worldUpAxis == 'Y':
            rollControlUpVector = (0,0,1)
            ballOffsetVec = (0,0,ballOffset)
            tipOffsetVec = (0,0,tipOffset)
            heelOffsetVec = (0,0,heelOffset)
        else:
            rollControlUpVector = (1,0,0)
            ballOffsetVec = (ballOffset,0,0)
            tipOffsetVec = (tipOffset,0,0)
            heelOffsetVec = (heelOffset,0,0)

        """ Foot Roll Control """
        footRollControlForwardAxis = 'Z'
        if hasToeJoint:
            heightTrans = pm.xform(fkjnts[4] ,q= 1 ,ws = 1,t =1 )
        else:
            heightTrans = pm.xform(fkjnts[3] ,q= 1 ,ws = 1,t =1 )
        if heelOnFloor:
            heightTrans[1] = 0.0
        xzTrans = pm.xform(in_balljnt ,q= 1 ,ws = 1,t =1 )
        footRollCenterPosition = (xzTrans[0],heightTrans[1],xzTrans[2])
        rollControlScale = [1.0*conScale,1.0*conScale,0.5*conScale]

        """ Flyer Leg -Mic 
            When selecting flyer leg it will now place the foot controls for: heel, ball and tip aligned with the angle
            of the foot. Previously it would always be aligned to world-z.
        """
        if flyerLeg:
            axes = ["X", "Y", "Z"]
            axisIndex = axes.index(forwardAxis.upper())

            # Multiply by negative one to get the right side values. There should be a better way.
            negative = 1
            if inter_ik_balljnt.name().find('r_') == 0:
                negative = -1

            heelOffsetVec = [negative * heelOffset if axisIndex is i else 0 for i in range(3)]
            tipOffsetVec = [negative * tipOffset if axisIndex is i else 0 for i in range(3)]
            ballOffsetVec = [negative * ballOffset if axisIndex is i else 0 for i in range(3)]

            # We need the space of the ball joint
            if ballPivot:
                ballOffsetVec = ik_balljnt.offsetParentMatrix.get() * pm.datatypes.Vector(ballOffsetVec)
                tipOffsetVec = ik_balljnt.offsetParentMatrix.get() * pm.datatypes.Vector(tipOffsetVec)
                heelOffsetVec = ik_balljnt.offsetParentMatrix.get() * pm.datatypes.Vector(heelOffsetVec)
            # Otherwise, We need the space of the ankle joint
            else:
                ballOffsetVec = ik_balljnt.inverseMatrix.get() * pm.datatypes.Vector(ballOffsetVec)
                tipOffsetVec = ik_balljnt.inverseMatrix.get() * pm.datatypes.Vector(tipOffsetVec)
                heelOffsetVec = ik_balljnt.inverseMatrix.get() * pm.datatypes.Vector(heelOffsetVec)

        if addHeelRoll:
            #Heel Roll
            heelRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_heelGrp") , parent=posCtrl)
            heelRoll = util.makeNurbsShape(8, name=util.getNiceControllerName(in_anklejnt.name(),"_heel_CON"), scale=rollControlScale, forwardAxis=footRollControlForwardAxis)
            # pm.circle(ch=0, o=1, r=2*conScale, normal=rollControlUpVector, name=util.getNiceControllerName(in_anklejnt.name(),"_heel_CON"))[0]
            pm.xform(heelRollTransform, ws=1, translation = footRollCenterPosition)
            pm.xform(heelRollTransform, ws=1, rotation = (offsetRot))
            heelRollTransform.translateBy(heelOffsetVec, ws=False) #-30
            pm.parent(heelRoll, heelRollTransform, r=True)
            # Heel Roll Pivot
            heelRollPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_heelPivot") , parent=heelRoll)
            multNode = pm.shadingNode('multiplyDivide', asUtility=True)
            pm.connectAttr(heelRoll.name() + '.translate', multNode.name() + '.input1')
            pm.connectAttr(multNode.name() + '.output', heelRollPivotTransform.name() + '.translate')
            pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])

            # Tip Roll
            tipRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_tipGrp") , parent=posCtrl)
            tipRoll = util.makeNurbsShape(8, name=util.getNiceControllerName(in_anklejnt.name(),"_tip_CON"), scale=rollControlScale, forwardAxis=footRollControlForwardAxis)
            #pm.circle(ch=0, o=1, r=2*conScale, normal=rollControlUpVector, name=util.getNiceControllerName(in_anklejnt.name(),"_tip_CON"))[0]

            ###position tip Control Here
            pm.xform(tipRollTransform, ws=1, rotation = (offsetRot))
            pm.xform(tipRollTransform, ws=1, translation = footRollCenterPosition)
            tipRollTransform.translateBy(tipOffsetVec, ws=False)

            pm.parent(tipRoll, tipRollTransform, r=True)
            pm.parent(tipRollTransform, heelRollPivotTransform)
            # Tip Roll Pivot
            tipRollPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_tipPivot") , parent=tipRoll)
            multNode = pm.shadingNode('multiplyDivide', asUtility=True)
            pm.connectAttr(tipRoll.name() + '.translate', multNode.name() + '.input1')
            pm.connectAttr(multNode.name() + '.output', tipRollPivotTransform.name() + '.translate')
            pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])

        # Ball Roll
        ballRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_ballGrp") , parent=posCtrl)
        ballRoll = util.makeNurbsShape(8, name=util.getNiceControllerName(in_anklejnt.name(),"_ball_CON"), scale=rollControlScale, forwardAxis=footRollControlForwardAxis)
        #pm.circle(ch=0, o=1, r=2*conScale, normal=rollControlUpVector, name=util.getNiceControllerName(in_anklejnt.name(),"_ball_CON"))[0]
        
        pm.xform(ballRollTransform, ws=1, rotation = (offsetRot))
        pm.xform(ballRollTransform, ws=1, translation = footRollCenterPosition)
        ballRollTransform.translateBy(ballOffsetVec, ws=False)


        pm.parent(ballRoll, ballRollTransform, r=True)


        if addHeelRoll:
            pm.parent(ballRollTransform, tipRollPivotTransform)
        else:
            pm.parent(ballRollTransform, posCtrl)

        pm.parentConstraint(ballRoll, posCtrlTransform, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)       #Constrain intermediate IK handle (which would be constrained by posctrl when not using footRoll)
        
        #if hasToeJoint:
        #    pm.parentConstraint(ballRoll, ikhandle_toe, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE) 

        out_iktweak_ballJnt = pm.joint(out_balljnt, name=out_balljnt.name() + '_orient')
        #ballControl, ballGrp = util.makeControl(out_iktweak_ballJnt, newscale=conScale*0.6, constrainObj=out_iktweak_ballJnt, shape=8) #, parentObj=out_balljnt
        ballOrientSpaceSwitcherJoints = SpaceSwitcherJoints[:]
        if (posCtrl not in ballOrientSpaceSwitcherJoints):
            ballOrientSpaceSwitcherJoints += [posCtrl, heelRoll, tipRoll, ballRoll]
        ballGrps, ballControls  = mb_MakeSimpleFKControl.mb_makeSimpleFKControl([out_iktweak_ballJnt], 
                                                                                 conScale=conScale * 0.5, 
                                                                                 SpaceSwitcherJoints=ballOrientSpaceSwitcherJoints, 
                                                                                 parentObj=out_balljnt, 
                                                                                 createSet=False,
                                                                                 spaceBlends=spaceBlends)
        ballControl = ballControls[0]
        ballControl.rename(ballControl.name().replace('_out', ''))
        pm.parent(ballGrps[0], masterGrp)

        """ Turn Controls """
        #Turn Control
        posInh = posCtrl.getParent()
        posPivotGrp = pm.group(posCtrl, name=util.getNiceControllerName(posCtrl.name()) + "_PivotGrp")
        rotateShape = [0,0,0]
        if worldUpAxis == 'Z':
            rotateShape = [0,0,90]
        turnCtrl, turnGrp = util.makeControl(posPivotGrp, conScale, shape=4, worldOrient=True, rotateShape=rotateShape)
        pm.xform(turnGrp, ws=True, translation=[0,0,0])
        pm.parent(turnGrp, masterGrp)

        #Pivot Transform
        turnPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(turnCtrl.name(),"_turnPivot") , parent=turnCtrl)
        multNode = pm.shadingNode('multiplyDivide', asUtility=True)
        pm.connectAttr(turnCtrl.name() + '.translate', multNode.name() + '.input1')
        pm.connectAttr(multNode.name() + '.output', turnPivotTransform.name() + '.translate')
        pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])
        #Inherit foot control INH transform for space switching
        pm.parentConstraint(posInh, turnCtrl.getParent(), mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        #Constrain the pivot group
        pm.parentConstraint(turnPivotTransform, posPivotGrp, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """ Base Foot Position Control 
        basePosTransformGrp = pm.group(posCtrl, name= posCtrl.name().replace('_CON', '_base_TransformGrp') )
        basePosCtrl, basePosGrp = util.makeControl(basePosTransformGrp, conScale*1.2, constrainObj=basePosTransformGrp, shape=9, worldOrient=True, ctrlName = posCtrl.name().replace('_CON', '_base_CON'))
        pm.parent(basePosGrp, masterGrp)
        #Inherit foot control INH transform for space switching
        pm.parentConstraint(posPivotGrp, basePosCtrl.getParent(), mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        
        #Move verts to ground
        
        pm.select(basePosCtrl.longName() + ".cv[0:" + str(pm.getAttr(basePosCtrl + ".spans")) + "]", r=True )
        if worldUpAxis == 'Y':
            basePosCtrlTransformY = pm.xform(basePosCtrl, q=True, ws=True, rp=True)[1]
            pm.move ([0,-1 * basePosCtrlTransformY,0], r=True, os=False, wd=True)
        else:
            basePosCtrlTransformY = pm.xform(basePosCtrl, q=True, ws=True, rp=True)[2]
            pm.move ([0,0,-1 * basePosCtrlTransformY], r=True, os=False, wd=True)
        """

        """ Auto Ankle Attribute - inherit rotation from intermediate ik """
        tempOrientCns = pm.orientConstraint(inter_ik_anklejnt, ankleCtrlGrp, mo=False).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.delete(tempOrientCns)

        pm.addAttr(ankleCtrl, ln = "autoAnkle", at= "double", min=0, max=1, defaultValue=1, k=1)
        pm.setAttr(ankleCtrl.name() + ".autoAnkle", 1)

        inheritTransform = pm.createNode( 'transform', n=util.getNiceControllerName(ankleCtrl.name(), '_AutoAnkle_transform') , parent=inter_ik_balljnt)
        pm.parent(inheritTransform, w=True)
        pm.parent(inheritTransform, masterGrp)
        inheritFootControlTransform = inheritTransform.duplicate()[0]
        inheritFootControlTransform.rename(util.getNiceControllerName(ankleCtrl.name(), '_Control_transform'))
        inheritBlendTransform = inheritTransform.duplicate()[0]
        inheritBlendTransform.rename(util.getNiceControllerName(ankleCtrl.name(), '_Blend_transform'))
        pm.parentConstraint(inter_ik_anklejnt, inheritTransform, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.parentConstraint(ballRoll, inheritFootControlTransform, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        ankleInherit = ankleCtrl.getParent()
        aa_bc_nodes = createBlendColorBlend(inheritFootControlTransform.name(), inheritTransform.name(), inheritBlendTransform.name(), ankleCtrl.name() + ".autoAnkle")
        util.connectMessage(networkNode, 'blendColors', aa_bc_nodes)
        
        pm.parentConstraint(inheritBlendTransform, ankleInherit, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.orientConstraint(ankleCtrl, inter_ik_balljnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """ Connect inter_leg poleVectorConstraint to Auto ankle """
        pm.addAttr(ankleCtrl, ln = "autoAnkleRoll", at= "double", min=0, max=1, defaultValue=1, k=1)
        weightAliases = inter_leg_poleVectorConstraint.getWeightAliasList()
        pm.connectAttr(ankleCtrl.name() + ".autoAnkleRoll", weightAliases[0])

        """Constrain to posCtrl for when auto ankle is not active"""
        ball_ikh_orientConstraint = pm.orientConstraint(posCtrlTransform, ball_ikh , mo=True)
        ball_ikh_orientConstraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
        weightAliases = ball_ikh_orientConstraint.getWeightAliasList()
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation" , 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(ankleCtrl.name() + ".autoAnkleRoll", oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        #pm.connectAttr(ankleCtrl.name() + ".rotateX", inter_leg_ikh.name() + ".twist")
        
        
        if humanLeg:
            cmds.setAttr(ankleCtrl.name() + ".autoAnkleRoll", 0, lock=True, keyable=False)
            cmds.setAttr(ankleCtrl.name() + ".autoAnkle", 0, lock=True, keyable=False)

        """ IK FK Switch Control """
        switchTransform = pm.createNode( 'transform', n=util.getNiceControllerName(posCtrl.name(), '_switch_transform') , parent=out_anklejnt)
        pm.parent(switchTransform, w=True )
        if worldUpAxis == 'Y':
            switchTransform.translateBy((0,0,-2*conScale), ws=True)
        else:
            switchTransform.translateBy((-2*conScale,0,0), ws=True)
        pm.parent(switchTransform, masterGrp)
        rotateShape = [0,0,0]
        if worldUpAxis == 'Z':
            rotateShape = [0,0,90]

        switchCtrl, ctrlGrp = util.makeControl(switchTransform, conScale, worldOrient=True, shape=3, rotateShape=rotateShape) #parentObj=switchTransform
        pm.parent(ctrlGrp, masterGrp)
        util.lockAndHideAttributes(switchCtrl, True, True)
        switchINH = switchCtrl.getParent()
        pm.parentConstraint(out_anklejnt, switchINH, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """ IK FK Switch and constrain the main joints"""
        pm.addAttr(switchCtrl, longName="SwitchIkFk", attributeType='double', min=0, max=1, k=1)
        util.printdebug("Outjnts is: " + str(outjnts))
        if hasToeJoint:
            toejnts = fkjnts[4:]
        else:
            toejnts = []
        for i, outjnt in enumerate(outjnts):
            ikjnt = ikjnts[i]
            fkjnt = fkjnts[i]
            #util.printdebug("Constraining " + outjnt.name() + " to " + ikjnt.name())
            main_bc_nodes = createBlendColorBlend(ikjnt, fkjnt, outjnt, switchCtrl.name() + '.SwitchIkFk')
            util.connectMessage(networkNode, 'blendColors', main_bc_nodes)

            chainjnt = chain[i]
            #util.printdebug("out_knee Joint: " + out_kneejnt)
            if (outjnt.name().find(out_kneejnt.name()) == 0):
                outjnt = kneeslideEndJnt   #Bind to slide joint instead of knee jnt
            if (outjnt.name().find(out_balljnt.name()) == 0):
                outjnt = out_iktweak_ballJnt   #Bind to tweak joint instead of ball jnt
            
            if (fkjnt not in toejnts):     #Do not constrain toe joints
                pm.parentConstraint(outjnt, chainjnt, mo=False).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        for i, fkControl in enumerate (fkControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', fkControl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.1)
            pm.setAttr(conditionNode.name()+ '.operation', 4) 

        ikControls = [posCtrl, ankleCtrl, poleVectorCtrl, turnCtrl, ballControl]
        for i, ikControl in enumerate (ikControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', ikControl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.9)
            pm.setAttr(conditionNode.name()+ '.operation', 2)    

        """ Add KneeSlide Attribute to SwitchCTRL """
        pm.addAttr(switchCtrl, ln = "kneeSlide", at= "double", min=0, defaultValue=kneeSlideValue, k=1)
        pm.connectAttr(switchCtrl.name()+ '.kneeSlide', kneeSlideMultNode.name() + ".input2.input2X")   
        pm.addAttr(switchCtrl, ln = "kneeSlideOffset", at= "double", defaultValue=kneeSlideOffset, k=1)
        pm.connectAttr(switchCtrl.name()+ '.kneeSlideOffset', kneeSlideMinusNode.name() + ".input1D[1]")
        
        """ TwistRollAmount Attribute"""
        pm.addAttr(switchCtrl, ln = "twistRollAmount", at= "double", min=0, max=1, defaultValue=rollTwistAmount, k=1)

        """ PoleVector follows FK in FK mode"""
        weightAliases = poleVectorFKParentConstraint.getWeightAliasList()
        # Activate FK
        """conditionNode = pm.shadingNode('condition', asUtility=True)
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
        pm.connectAttr(conditionNode.name() + '.outColor.outColorR', poleVectorFKParentConstraint + '.' + weightAliases[0].attrName(longName=True))
        pm.setAttr(conditionNode.name() + '.secondTerm', 0.99)
        pm.setAttr(conditionNode.name() + '.operation', 2)      #greater than"""

        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', weightAliases[1])

        # Activate IK
        """conditionNode = pm.shadingNode('condition', asUtility=True)
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
        pm.connectAttr(conditionNode.name() + '.outColor.outColorR', poleVectorFKParentConstraint + '.' + weightAliases[1].attrName(longName=True))
        pm.setAttr(conditionNode.name() + '.secondTerm', 0.99)
        pm.setAttr(conditionNode.name() + '.operation', 5)      #less or equal"""

        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation", 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])

        ikjnts[0].hide()
        fkjnts[0].hide()
        outjnts[0].hide()
        intikjnts[0].hide()

        """ Space Switches """
        if (len(SpaceSwitcherJoints) > 0):
            util.setupSpaceSwitch(posCtrl, SpaceSwitcherJoints, inheritParentLevel=3, spaceBlends=spaceBlends)
        
        localSpaceSwitcherJoints = SpaceSwitcherJoints[:]
        if (posCtrl not in localSpaceSwitcherJoints):
            localSpaceSwitcherJoints.append(posCtrl)
        util.setupSpaceSwitch(poleVectorCtrl, localSpaceSwitcherJoints, spaceBlends=spaceBlends)

        twistAJnts = createTwistJoints(out_anklejnt, out_kneejnt, in_kneejnt, switchCtrl, kneeslideEndJnt=kneeslideEndJnt,
                         twistKeyword=twistKeyword, twistList=twistList,rollTwistAmount=rollTwistAmount, twistOffsetControl=switchCtrl, rollTwistAmountDict=rollTwistAmountDict) or []
        # Also constrain twist joints that are between ankle and ball.
        twistBJnts = createTwistJoints(out_balljnt, out_anklejnt, in_anklejnt, switchCtrl, kneeslideEndJnt=None,
                         twistKeyword=twistKeyword, twistList=twistList,rollTwistAmount=rollTwistAmount, twistOffsetControl=None,rollTwistAmountDict=rollTwistAmountDict) or []
        rollJnts = createRollJoints(out_kneejnt, outjnts[0], thighJoint, switchCtrl, rollKeyword=rollKeyword, rollList=rollList,rollTwistAmount=rollTwistAmount,rollTwistAmountDict=rollTwistAmountDict) or []
        
        twistRollJnts = twistAJnts + twistBJnts + rollJnts
        connectRollTwist = [x.name().split('_RigJnt')[0] for x in twistRollJnts]
        util.connectMessage(networkNode, 'joints', connectRollTwist)
        

        if addHeelRoll:
            ikControls += [ballRoll, heelRoll, tipRoll]
        else:
            ikControls += [ballRoll]

        ikControls.append(switchCtrl)
        #Create Sets
        newNameStart = firstjnt.lower()     #.replace('thigh', 'leg').replace('__','_')
        ikSet = pm.sets(ikControls, name= util.getNiceControllerName(newNameStart, '_ik_ctrl_set'))
        fkSet = pm.sets(fkControls, name= util.getNiceControllerName(newNameStart, '_fk_ctrl_set'))
        mainSet = pm.sets( ikSet, fkSet, n=util.getNiceControllerName(newNameStart, '_ctrl_set'))
        pm.sets(mainSet, edit=True, fe=[ikSet, fkSet] )
        if group:
            util.addToSet(mainSet, group.name() + '_set')
        allControls = fkControls + ikControls

        engineIKCtrls = []
        engineIKJoints = []
        if addEngineIK:
            rootIKName = f'foot_root_ik'
            engineIKNetwork = ctrl.findNetworkByInfo(networkNode.parent.get(), 'cr_MakeEngineIK.engineIKCtrl', rootIKName)
            engineIKSpaceSwitcherJoints = SpaceSwitcherJoints[:]

            engineIKCtrls, engineIKJoints = cr_MakeEngineIK.addIKJoints(in_anklejnt,
                                                                        poleikfkGrp,
                                                                        root,
                                                                        conScale,
                                                                        engineIKSpaceSwitcherJoints,
                                                                        group,
                                                                        in_balljnt,
                                                                        rootIKName=rootIKName,
                                                                        baseOffset=ikBaseOffset,
                                                                        ankleOrientObject=in_anklejnt,
                                                                        footControl=posCtrl,
                                                                        poleVectorName=pvTransform.name(),
                                                                        mainCtrl=mainCtrl,
                                                                        engineIKBallJoint=engineIKBallJoint,
                                                                        applyParentCnsToGroundPreProjection=False,
                                                                        networkNode=engineIKNetwork)

        if mainCtrl:
            pm.connectAttr(mainCtrl.name() + '.scale', masterGrp.name() + '.scale')
            
        util.connectMessage(networkNode, 'controls', allControls)

        return masterGrp, allControls, engineIKCtrls, engineIKJoints
    except:
        print("Exception in user code:")
        print('-'*60)
        traceback.print_exc() #file=sys.stdout
        print('-'*60)
        return None, None, None, None

#makeWindow()
