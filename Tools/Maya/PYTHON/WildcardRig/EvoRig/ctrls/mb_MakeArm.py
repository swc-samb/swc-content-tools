

import os
import sys, traceback
import re
from math import *
import importlib
from collections import OrderedDict as od
from functools import partial


import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMaya

from EvoRig import mb_rig_utilities as util
import mb_MakeSimpleFKControl
#util.debugging = False

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

reload(util)

__author__ = 'Michael Buettner, Ethan McCaughey'
__version__ = '0.1.1'

armDict = {"shoulder":0, "elbow":1, "wrist":2, "ball":3, "finger":4}

if 2 < sys.version_info.major <= 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
    reload = __import__('importlib').reload 

import ctrl; reload(ctrl);
from mb_MakeLeg import *

#-----------------------------------------------------------------------------#
# IK/FK Arm Ctrl Module
#-----------------------------------------------------------------------------#

class armCtrl(ctrl.ctrlModule):   
    '''Arm Control Wrapper class''' 
    _isCtrl = True
    _label = 'IK/FK Arm'
    _color = (0.4,0.4,0.6)
    _isArmCtrl = True

    def __init__(self, *args, **kwargs):      
        self._nodeAttributes = {}        
        self.keyword = 'shoulder'
        self.shoulderJoint = ''
        self.wristJoint = ''        
        self._nodeAttributes['shoulderJoint'] = True
        self._nodeAttributes['wristJoint'] = True

        self.ballOffset = 0.0

        self.flexAxis = od([('X','X'),
                            ('Y','Y'),
                            ('Z','Z'),
                            ('-X','-X'),
                            ('-Y','-Y'),
                            ('-Z','-Z')])
        self.elbowSlide = 0.01
        self.elbowSlideOffset = -10
        self.mirrorModule = False
        self.engineIK = False
        self.engineIKBallJoint = True
        self.worldOrient=True
        self.separateOrient=True
        self.twistKeyword = "twist"
        self.rollKeyword = "roll"
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
        '''Search Root Node for keywords and issue create command
           Should Be overwritten for each node to get proper args'''

        #since using mutable types are default arges can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []

        util.printdebug("Module " + str(self._index) + ' adding arm, Keyword:' + str(self.keyword))

        leftPrefix = (kwargs.get('leftPrefix') or 'l_')
        rightPrefix = (kwargs.get('rightPrefix') or 'r_')

        startJoint, endJoint = util.getRigJoint([(self.shoulderJoint or None), (self.wristJoint or None)])

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
                mirroredStartJoint, mirroredEndJoint = util.getRigJoint([(pm.PyNode(util.mirrorName(self.shoulderJoint, leftPrefix, rightPrefix)) or None), ( pm.PyNode(util.mirrorName(self.wristJoint, leftPrefix, rightPrefix)) or None)])
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
            util.printdebug(j + str(k))

            util.printdebug("   Shoulder Joint: " + str(j))
            print("\n   Shoulder Joint: " + str(j))
            print("   startJoint: " + str(startJoint))
            print("   endJoint: " + str(endJoint))

            # ethanm - mirror spaceblend if control is a mirror of given joints
            if mirrored[k]:
                spaceBlends = (self._spaceBlendDict if self.useSpaceBlending else None)
            else:
                spaceBlends = ({util.mirrorName(a, leftPrefix, rightPrefix):b for a,b in self._spaceBlendDict.items()} if self.useSpaceBlending else None)

            arm_nodes = mb_makeArm(shoulderJoint=j, 
                                   conScale=controlSize * self.moduleSize, 
                                   FlexAxis=self.flexAxis, 
                                   SpaceSwitcherJoints=moduleSpaceSwitchList, 
                                   heelOffset=0,
                                   tipOffset=0,
                                   ballOffset=self.ballOffset,
                                   startJoint=startJoints[k], 
                                   endJoint=endJoints[k],
                                   twistKeyword=self.twistKeyword,
                                   rollKeyword=self.rollKeyword,
                                   rollList=self.rollList,
                                   twistList=self.twistList,
                                   rollTwistAmount=self.rollTwistAmount,
                                   rollTwistAmountDict = self._rollTwistAmountDict,
                                   addInterIkPoleVector=False,
                                   addHeelRoll=False,
                                   elbowSlideValue=self.elbowSlide,
                                   elbowSlideOffset=self.elbowSlideOffset,
                                   addEngineIK=self.engineIK,
                                   engineIKBallJoint=self.engineIKBallJoint,
                                   root=root,
                                   group=group,
                                   worldOrient=self.worldOrient,
                                   separateRotateOrient=self.separateOrient,
                                   mainCtrl=mainCtrl,
                                   spaceBlends=spaceBlends,
                                   networkNode=networkNode)
            
            newLegGrp, legCtrls, engineIKCtrls, engineIKJoints = arm_nodes

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
                    
            if self.engineIK:
                for ejoint, ectr in zip(engineIKJoints, engineIKCtrls):
                     hint_set[ectr] = ejoint
                hint_set[util.getPyNode(engineIKJoints[0].name() +'_EngineIKCON')] = engineIKJoints[0]

        if group:
            pm.parent(legs, group)
                
        self.createControlAttributes(allControls)

        print('evoRetarget:')
        #set retarget hint attributes
        for hint_set in hint_sets:
            for ctr, joint in hint_set.items():
                print(' ', joint, '>', ctr)
                args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr)
                self.setRetargetHintAttributes(ctr, *args, **kwargs)

        return allControls

    def validate(self, root, *args, **kwargs):
        """Run several checks for rig validation"""
        validationErrors = []

        # Check if module field is empty or not
        check = util.emptyModuleField(self, ["shoulderJoint", "wristJoint"])
        if check:
            print('=' * 80)
            print("THESE ARE THE MISSING VALUES: {}".format(check))
            print('=' * 80)
            validationErrors.append("\nModule Is Missing Required Values! {0}".format(check))
            return validationErrors  # If we don't have proper start/end joints nothing else works, return now.

        # Check that all joints are found
        startJoint, endJoint = util.getPyNode([(self.shoulderJoint or None), (self.wristJoint or None)])
        startJoints, endJoints = [startJoint], [endJoint]

        if not startJoint or not endJoint:
            thighjnts = util.findAllInChain(root, self.keyword)
            if not thighjnts:
                validationErrors.append(f"\nCouldn't Find Joints!\n Start:'{self.shoulderJoint}' {bool(startJoint)} End:'{self.wristJoint}' {bool(endJoint)}")

            startJoints, endJoints = thighjnts, [util.findInChain(jnt, toeKeyword) for jnt in thighjnts]

            if not all(endJoints):
                validationErrors.append("\nCouldn't Find End Joints:\n * {0}".format("\n * ".join(map(str, ((x[0].name(), x[1].name()) for x in (zip(startJoints, endJoints)))))))

        elif self.mirrorModule:
            mirroredStartJoint, mirroredEndJoint = util.getPyNode([(util.mirrorName(self.shoulderJoint, leftPrefix, rightPrefix) or None), (util.mirrorName(self.wristJoint, leftPrefix, rightPrefix) or None)])

            if not mirroredStartJoint or not mirroredEndJoint:
                validationErrors.append(f"\nCouldn't Find Mirrored Joints!\n Start:'{util.mirrorName(self.shoulderJoint)}' {bool(mirroredStartJoint)} End:'{util.mirrorName(self.wristJoint, leftPrefix, rightPrefix)}' {bool(mirroredEndJoint)}")

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

            if badJoints:
                validationErrors.append("\nEnd Joints Not Found Under Start Joints! {0}".format(badJoints))
                return validationErrors  # If we don't have proper start/end joints nothing else works, return now.

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

    def initDynamicLayoutParameters(self, 
                                    moduleLayout,
                                    ignoreList = None):
        ignoreList = ['rollList','twistList','twistKeyword', 'rollKeyword','rollTwistAmount', '_rollTwistAmountDict']    
        super(type(self), self).initDynamicLayoutParameters(moduleLayout, 
                                                            ignoreList = ignoreList)

        #pm.separator(height=self._separatorHeight, style="none", parent=moduleLayout)
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
        pm.text('TwistText', 
                        label="Twist", 
                        parent=moduleLayout)
        twistKeywordTextField = pm.textField('twistKeywordTextField',
                            text=str(self.twistKeyword), 
                            editable=True, 
                            changeCommand=partial(setattr, self, "twistKeyword"), annotation='',
                            parent=moduleLayout)
        self.setUI("twistKeyword", twistKeywordTextField)

        pm.text('RollText', 
                        label="Roll", 
                        parent=moduleLayout)
        rollKeywordTextField = pm.textField('rollKeywordTextField',
                            text=str(self.rollKeyword), 
                            editable=True, 
                            changeCommand=partial(setattr, self, "rollKeyword"), annotation='',
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

def getArmJoint(firstjnt, keyword, searchByName=True, chain=None):
    if searchByName:
        joint = util.findInChain(firstjnt, keyword, chain=chain)
    else:
        print("################ getArmJoint Chain: " + str(chain))
        joint = chain[armDict[keyword]]
    return joint


def mb_makeArm(shoulderJoint=None, 
               conScale = 0, 
               FlexAxis="z", 
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
               addHeelRoll=False,
               elbowSlideValue=0.1,
               elbowSlideOffset=0.0,
               addEngineIK=False,
               engineIKBallJoint=True,
               root=None,
               group=None,
               worldOrient=True,
               separateRotateOrient=True,
               mainCtrl=None,
               spaceBlends=None,
               networkNode=None):
    try:
        #util.debugging = True

        if (conScale == 0):
            conScale = cmds.intSliderGrp(controlSizeSlider, q=True, value=True)
        findJointsByName = True
        jnt = None

        if (startJoint != None and endJoint != None):
            pass
            
        else:
            if (shoulderJoint == None):
                jnt = pm.selected( type='joint' )
                if not jnt:
                    raise ValueError( 'A joint must either be specified, or selected.' )
                jnt = jnt[0]
                shoulderJoint = jnt
                #raise ValueError( 'startJoint and endJoint must be specified if no shoulderJoint is given.' )
            else:    
                jnt = shoulderJoint
                    
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
        shoulderJoint = startJoint
        jnt = shoulderJoint
        connect_chain = [x.name().split('_RigJnt')[0] for x in chain]
        util.connectMessage(networkNode, 'joints', connect_chain)
        util.printdebug("Making arm for chain: " + str(chain))

        hasToeJoint = True
        if legDict[toeKeyword] > (len(chain)-1):
            hasToeJoint = False
        hasBallJoint = True
        if legDict[ballKeyword] > (len(chain)-1):
            hasBallJoint = False

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

            fkdup = jnt.duplicate( parentOnly=True )[0]
            fkdup.rename( jnt.name() + '_fk' )
            fkjnts.append( fkdup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - fkdup.setParent( fkjnts[jntIndex] )
                util.setParent(fkdup, fkjnts[jntIndex])
            else:
                # ethanm - fkdup.setParent( masterGrp )
                util.setParent(fkdup, masterGrp)

            #Output joints
            outdup = jnt.duplicate( parentOnly=True )[0]
            outdup.rename( jnt.name() + '_out' )
            outjnts.append( outdup )
            # If the parent is in the chain, it has already been duplicated
            if jnt.getParent() in chain:
                jntIndex = chain.index( jnt.getParent() )
                # ethanm - outdup.setParent( outjnts[jntIndex] )
                util.setParent(outdup, outjnts[jntIndex])

            else:
                # ethanm - outdup.setParent( masterGrp )
                util.setParent(outdup, masterGrp)
        
        startjnt = ikjnts[0]
        pm.makeIdentity(startjnt, apply = True)# -t 1 -r 1 -s 1 -n 0 -pn 1;
        pm.makeIdentity(fkjnts[0], apply = True)
        pm.makeIdentity(outjnts[0], apply = True)
        #startjnt = intikjnts[0]
        
        out_kneejnt = getLegJoint(outjnts[0], kneeKeyword, findJointsByName, outjnts)
        out_anklejnt = getLegJoint(outjnts[0], ankleKeyword, findJointsByName, outjnts)
        if hasBallJoint:
            out_balljnt = getLegJoint(outjnts[0], ballKeyword, findJointsByName, outjnts)


        print("startjnt :" + str(startjnt))
        
        #pm.parentConstraint(shoulderJoint.getParent(), startjnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        """Pole Vector"""
        in_thighjnt = firstjnt
        in_kneejnt = getLegJoint(firstjnt, kneeKeyword, findJointsByName, chain)
        in_anklejnt = getLegJoint(firstjnt, ankleKeyword, findJointsByName, chain)
        if hasBallJoint:
            in_balljnt = getLegJoint(firstjnt, ballKeyword, findJointsByName, chain)

        pvTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(), '_PV_transform') , parent=in_kneejnt)  #shoulderJoint.name()
        
        pm.parent(pvTransform, w=True)
        polePos, poleRot = placePoleVector([in_thighjnt, in_kneejnt, in_anklejnt])
        pm.xform(pvTransform, ws=1, t = polePos)
        pm.parent(pvTransform, masterGrp)

        worldUpAxis = pm.upAxis(q=True, axis=True).upper()
        rotateShape=[90,0,0]
        aimUpVector = [0,1,0]
        if worldUpAxis == 'Z':
            rotateShape = [90,0,-90]
            aimUpVector = [0,0,1]
        
        poleVectorCtrl, ctrlGrp = util.makeControl(pvTransform, conScale, constrainObj=pvTransform, worldOrient=True, shape=2, rotateShape=rotateShape )
        poleVectorINH = poleVectorCtrl.getParent()
        aimCns = pm.aimConstraint(out_kneejnt, poleVectorINH, aimVector = (0, 0, -1) , upVector = aimUpVector , worldUpType = "scene", skip =['x','z'])
        pm.delete(aimCns)

        poleVectorTarget = None
        
        poleVectorTarget = poleVectorCtrl

        #inter_leg_poleVectorConstraint = pm.poleVectorConstraint(poleVectorTarget, inter_leg_ikh)

        pm.parent(ctrlGrp, masterGrp)

        """ Secondary IK """

        ik_thighjnt = ikjnts[0]
        ik_anklejnt = ikjnts[1]

        ik_kneejnt = getLegJoint(ikjnts[0], kneeKeyword, findJointsByName, ikjnts)
        ik_anklejnt = getLegJoint(ikjnts[0], ankleKeyword, findJointsByName, ikjnts)
        if hasBallJoint:
            ik_balljnt = getLegJoint(ik_thighjnt, ballKeyword, findJointsByName, ikjnts)
        if hasToeJoint:
            ik_toejnt = getLegJoint(ik_thighjnt, toeKeyword, findJointsByName, ikjnts)

        ikhandle1 = pm.ikHandle(startJoint=ik_thighjnt, endEffector=ik_anklejnt, sol="ikRPsolver")
        ankle_ikh = ikhandle1[0]
        ankle_ikh.rename("ankle_ikh")
        ankle_ikh.hide()

        pm.parent(ankle_ikh, masterGrp, a=True)
        #pm.parent(ankle_ikh, inter_ik_balljnt, a=True)
        pm.parentConstraint(shoulderJoint.getParent(), ik_thighjnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        
        # merged from foot ctrl - etham
        """ Add transform to PoleVector so EngineIK joints are positioned correctly even in FK mode """
        poleVectorFKConstrainTarget = fkjnts[1]
        poleikfkGrp = pm.group(em=True, n=str(poleVectorCtrl.name()) + "_ikfk")
        pm.parent(poleikfkGrp, poleVectorCtrl, r=True)
        #pm.poleVectorConstraint(poleikfkGrp, ankle_ikh)      #Add PoleVector Constraint
        #Add constraint so control follows the FK transforms when IK is inactive
        poleVectorFKParentConstraint = pm.parentConstraint([poleVectorCtrl, poleVectorFKConstrainTarget], poleikfkGrp, mo=True, weight=1) 
        # - ethanm

        pm.poleVectorConstraint(poleVectorCtrl, ankle_ikh)

        """ikhandle2 = pm.ikHandle(startJoint=ik_anklejnt, endEffector=ik_balljnt, sol="ikSCsolver")
        ball_ikh = ikhandle2[0]
        ball_ikh.rename("ball_ikh")
        ball_ikh.hide()
        """
        #pm.parent(ball_ikh, inter_ik_anklejnt, a=False)

        """ Control """
        posCtrl, ctrlGrp = util.makeControl(ik_anklejnt, conScale, constrainObj=None, worldOrient=worldOrient, separateRotateOrient=separateRotateOrient) #constrainObj=ankle_ikh     #arm control positioned at akme
        pm.parent(ctrlGrp, masterGrp)
        
        #pm.parentConstraint(posCtrl, inter_leg_ikh, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        
        """rotateAnkleShape = [90,-90,0]
        if inter_ik_balljnt.name().find('r_') == 0:
            rotateAnkleShape = [90,90,0]
        ankleCtrl, ankleCtrlGrp = util.makeControl(inter_ik_balljnt, conScale * 1, None, parentObj=None, shape=2, 
                                                rotateShape=rotateAnkleShape, translateShape=[0,1,0],
                                                ctrlName=util.getNiceControllerName(inter_ik_anklejnt.name().replace('_INT_ik', ''), '_CON')) #parentObj=inter_ik_anklejnt
        
        pm.parent(ankleCtrlGrp, masterGrp)"""

        
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
        

        """ Toe IK Handle """
        if hasToeJoint:
            ikhandle_toe = pm.ikHandle(name=ik_toejnt.name() + "_ikh", startJoint=ik_balljnt, endEffector=ik_toejnt, sol="ikSCsolver")[0]
            pm.parent(ikhandle_toe, masterGrp)
            ikhandle_toe.hide()
            #pm.parentConstraint(posCtrl, ikhandle_toe, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)


        """ Filter Space Switches """
        #When an arm is mirrored, prevent cycle by removing the joint from the space switcher list
        localSpaceSwitcherJoints = SpaceSwitcherJoints[:]
        for i,j in enumerate(localSpaceSwitcherJoints):
            if in_anklejnt == j:
                localSpaceSwitcherJoints.pop(i)
                break


        """ FK Controls """
        mainfkjnts = fkjnts[1:3]
        firstfkjnt = fkjnts[0]
        #mainfkjnts.remove(firstfkjnt)
        fkGrps, fkControls = mb_MakeSimpleFKControl.mb_makeSimpleFKControl(joints=mainfkjnts, 
                                                                           conScale=conScale * 0.5, 
                                                                           SpaceSwitcherJoints=localSpaceSwitcherJoints, 
                                                                           createSet=False,
                                                                           spaceBlends=spaceBlends)
        fkGrp, firstfkcontrols = mb_MakeSimpleFKControl.mb_makeSimpleFKControl(joints=[firstfkjnt], 
                                                                               conScale=conScale * 0.5, 
                                                                               SpaceSwitcherJoints=localSpaceSwitcherJoints, 
                                                                               parentObj=shoulderJoint.getParent(), 
                                                                               createSet=False,
                                                                               spaceBlends=spaceBlends)
        fkControls.append(firstfkcontrols[0])
        pm.parent(fkGrps, masterGrp)
        pm.parent(fkGrp, masterGrp)
        
        """ Foot Roll Control """
        if hasToeJoint:
            heightTrans = pm.xform(fkjnts[4] ,q= 1 ,ws = 1,t =1 )
        elif hasBallJoint:
            heightTrans = pm.xform(fkjnts[3] ,q= 1 ,ws = 1,t =1 )
        else:
            heightTrans = pm.xform(fkjnts[2] ,q= 1 ,ws = 1,t =1 )
        
        if hasBallJoint:
            centerJoint = in_balljnt
        else:
            centerJoint = in_anklejnt

        xzTrans = pm.xform(centerJoint ,q= 1 ,ws = 1,t =1 )
        
        footRollCenterPosition = (xzTrans[0],heightTrans[1],xzTrans[2])

        if addHeelRoll:
            #Heel Roll
            heelRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_heelGrp") , parent=posCtrl)
            heelRoll = pm.circle(ch=0, o=1, r=2*conScale, normal=(0,0,1), name=util.getNiceControllerName(in_anklejnt.name(),"_heel_CON"))[0]
            pm.xform(heelRollTransform, ws=1, translation = footRollCenterPosition)
            pm.xform(heelRollTransform, ws=1, rotation = (0,0,0))
            heelRollTransform.translateBy((0,0,heelOffset)) #-30
            pm.parent(heelRoll, heelRollTransform, r=True)
            # Heel Roll Pivot
            heelRollPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_heelPivot") , parent=heelRoll)
            multNode = pm.shadingNode('multiplyDivide', asUtility=True)
            pm.connectAttr(heelRoll.name() + '.translate', multNode.name() + '.input1')
            pm.connectAttr(multNode.name() + '.output', heelRollPivotTransform.name() + '.translate')
            pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])
            # Tip Roll
            tipRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_tipGrp") , parent=posCtrl)
            tipRoll = pm.circle(ch=0, o=1, r=2*conScale, normal=(0,0,1), name=util.getNiceControllerName(in_anklejnt.name(),"_tip_CON"))[0]
            pm.xform(tipRollTransform, ws=1, rotation = (0,0,0))
            pm.xform(tipRollTransform, ws=1, translation = footRollCenterPosition)
            tipRollTransform.translateBy((0,0,tipOffset)) #40
            pm.parent(tipRoll, tipRollTransform, r=True)
            pm.parent(tipRollTransform, heelRollPivotTransform)
            # Tip Roll Pivot
            tipRollPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_tipPivot") , parent=tipRoll)
            multNode = pm.shadingNode('multiplyDivide', asUtility=True)
            pm.connectAttr(tipRoll.name() + '.translate', multNode.name() + '.input1')
            pm.connectAttr(multNode.name() + '.output', tipRollPivotTransform.name() + '.translate')
            pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])

        # Ball Roll
        ballRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_PivotGrp") , parent=ik_anklejnt)
        ballRoll = pm.circle(ch=0, o=1, r=2*conScale, normal=(1,0,0), name=util.getNiceControllerName(in_anklejnt.name(),"_Pivot_CON"))[0]
        pm.xform(ballRollTransform, ws=1, translation = footRollCenterPosition)
        ballRollTransform.translateBy((0,0,ballOffset))
        pm.parent(ballRoll, ballRollTransform, r=True)

        # Ball Pivot
        ballRollPivotTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_Pivot") , parent=ballRoll)
        multNode = pm.shadingNode('multiplyDivide', asUtility=True)
        pm.connectAttr(ballRoll.name() + '.translate', multNode.name() + '.input1')
        pm.connectAttr(multNode.name() + '.output', ballRollPivotTransform.name() + '.translate')
        pm.setAttr(multNode.name()+ '.input2', [-1,-1,-1])


        if addHeelRoll:
            pm.parent(ballRollTransform, tipRollPivotTransform)
        else:
            pm.parent(ballRollTransform, posCtrl)

        if addHeelRoll:
            spans = cmds.getAttr(heelRoll.name() + ".spans")
            cmds.select(heelRoll.name() + ".cv[0:" + str(spans) + "]", r=True )
            cmds.scale(1 , 0.5 , 1, r=True)
            spans = cmds.getAttr(tipRoll.name() + ".spans")
            cmds.select(tipRoll.name() + ".cv[0:" + str(spans) + "]", r=True )
            cmds.scale(1 , 0.5 , 1, r=True)

        spans = cmds.getAttr(ballRoll.name() + ".spans")
        cmds.select(ballRoll.name() + ".cv[0:" + str(spans) + "]", r=True )
        cmds.scale(1 , 0.5 , 1, r=True)

        #pm.parentConstraint(ballRoll, inter_leg_ikh, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)       #Constrain intermediate IK handle (which would be constrained by posctrl when not using footRoll)
        pm.parentConstraint(ballRollPivotTransform, ankle_ikh, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)       #Constrain IK handle (which would be constrained by posctrl when not using footRoll)
        pm.orientConstraint(ballRollPivotTransform, ik_anklejnt, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        if hasToeJoint:
            pm.parentConstraint(ballRoll, ikhandle_toe, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)


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

        """ Base Hand Position Control 
        basePosTransformGrp = pm.group(posCtrl, name= posCtrl.name().replace('_CON', '_base_TransformGrp') )
        basePosCtrl, basePosGrp = util.makeControl(posCtrl, conScale*1.2, constrainObj=basePosTransformGrp, shape=9, worldOrient=True, separateRotateOrient=True, ctrlName = posCtrl.name().replace('_CON', '_base_CON'))
        pm.parent(basePosGrp, masterGrp)
        #Inherit foot control INH transform for space switching
        pm.parentConstraint(posPivotGrp, basePosCtrl.getParent(), mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        """

        """ Auto Ankle Attribute - inherit rotation from intermediate ik """
        """tempOrientCns = pm.orientConstraint(inter_ik_anklejnt, ankleCtrlGrp, mo=False)
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
        createBlendColorBlend(inheritFootControlTransform.name(), inheritTransform.name(), inheritBlendTransform.name(), ankleCtrl.name() + ".autoAnkle")

        pm.parentConstraint(inheritBlendTransform, ankleInherit, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        pm.orientConstraint(ankleCtrl, inter_ik_balljnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)
        """

        """ Connect inter_leg poleVectorConstraint to Auto ankle """
        """pm.addAttr(ankleCtrl, ln = "autoAnkleRoll", at= "double", min=0, max=1, defaultValue=1, k=1)
        weightAliases = inter_leg_poleVectorConstraint.getWeightAliasList()
        pm.connectAttr(ankleCtrl.name() + ".autoAnkleRoll", weightAliases[0])
        """

        """Constrain to posCtrl for when auto ankle is not active"""
        
        """
        ball_ikh_orientConstraint = pm.orientConstraint(posCtrl, ball_ikh , mo=True)
        ball_ikh_orientCosntraint.setAttr('interpType', util.DEFAULT_INTERPTYPE)
        weightAliases = ball_ikh_orientConstraint.getWeightAliasList()
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation" , 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(ankleCtrl.name() + ".autoAnkleRoll", oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        #pm.connectAttr(ankleCtrl.name() + ".rotateX", inter_leg_ikh.name() + ".twist")
        """

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
            if (fkjnt not in toejnts):     #Do not constrain toe joints
                pm.parentConstraint(outjnt, chainjnt, mo=False).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        for i, fkControl in enumerate (fkControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', fkControl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.1)
            pm.setAttr(conditionNode.name()+ '.operation', 4) 

        ikControls = [posCtrl, poleVectorCtrl, turnCtrl]
        for i, ikControl in enumerate (ikControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', ikControl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.9)
            pm.setAttr(conditionNode.name()+ '.operation', 2)   

        """ Add elbowSlide Attribute to SwitchCTRL """
        pm.addAttr(switchCtrl, ln = "elbowSlide", at= "double", min=0, defaultValue=elbowSlideValue, k=1)
        pm.connectAttr(switchCtrl.name()+ '.elbowSlide', kneeSlideMultNode.name() + ".input2.input2X")    
        pm.addAttr(switchCtrl, ln = "elbowSlideOffset", at= "double", defaultValue=elbowSlideOffset, k=1)
        pm.connectAttr(switchCtrl.name()+ '.elbowSlideOffset', kneeSlideMinusNode.name() + ".input1D[1]")    

        """ TwistRollAmount Attribute"""
        pm.addAttr(switchCtrl, ln = "twistRollAmount", at= "double", min=0, max=1, defaultValue=rollTwistAmount, k=1)
        
        # merged from foot ctrl - ethanm
        """ PoleVector follows FK in FK mode"""
        weightAliases = poleVectorFKParentConstraint.getWeightAliasList()
        # Activate FK
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', weightAliases[1])
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation", 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        # - ethanm
        
        ikjnts[0].hide()
        fkjnts[0].hide()
        outjnts[0].hide()
        #intikjnts[0].hide()

        if (len(localSpaceSwitcherJoints) > 0):
            util.setupSpaceSwitch(posCtrl, 
                                  localSpaceSwitcherJoints, 
                                  nameDetailLevel=3, 
                                  inheritParentLevel=3,
                                  nameDetailStart=0,
                                  spaceBlends=spaceBlends)
        
        if (posCtrl not in localSpaceSwitcherJoints):
            localSpaceSwitcherJoints.append(posCtrl)
        util.setupSpaceSwitch(poleVectorCtrl, 
                              localSpaceSwitcherJoints, 
                              nameDetailLevel=3,
                              nameDetailStart=0,
                              spaceBlends=spaceBlends)

        twistJnts = createTwistJoints(out_anklejnt, out_kneejnt, in_kneejnt, switchCtrl, kneeslideEndJnt=kneeslideEndJnt, 
                            twistKeyword=twistKeyword, twistList=twistList, rollTwistAmount = rollTwistAmount, twistOffsetControl=switchCtrl,rollTwistAmountDict=rollTwistAmountDict) or []
        rollJnts = createRollJoints(out_kneejnt, outjnts[0], shoulderJoint, switchCtrl, rollKeyword=rollKeyword, rollList=rollList, rollTwistAmount = rollTwistAmount, rollTwistAmountDict=rollTwistAmountDict) or []
        
        connectRollTwist = [x.name().split('_RigJnt')[0] for x in twistJnts + rollJnts]
        util.connectMessage(networkNode, 'joints', connectRollTwist)
        
        ikControls.append(switchCtrl)
        if addHeelRoll:
            ikControls += [ballRoll, heelRoll, tipRoll]
        else:
            ikControls += [ballRoll]

        #Create Sets
        newNameStart = firstjnt.lower()     #.replace('__','_')    #.replace('arm', '')   .replace('shoulder', 'arm')
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
            ball = None
            if hasBallJoint:
                ball = in_balljnt
            engineIKSpaceSwitcherJoints = SpaceSwitcherJoints[:]
            rootIKName = f'hand_root_ik'
            engineIKNetwork = ctrl.findNetworkByInfo(networkNode.parent.get(), 'cr_MakeEngineIK.engineIKCtrl', rootIKName)
            engineIKSpaceSwitcherJoints = SpaceSwitcherJoints[:]
            #engineIKSpaceSwitcherJoints.insert(0, basePosCtrl)
            # merged from foot ctrl - ethanm
            engineIKCtrls, engineIKJoints = cr_MakeEngineIK.addIKJoints(in_anklejnt,
                                                                        poleikfkGrp,
                                                                        root,
                                                                        conScale,
                                                                        engineIKSpaceSwitcherJoints,
                                                                        group,
                                                                        ball,
                                                                        rootIKName=rootIKName,
                                                                        setBaseToFloor=True,
                                                                        poleVectorName=pvTransform.name(),
                                                                        mainCtrl=mainCtrl,
                                                                        engineIKBallJoint=engineIKBallJoint,
                                                                        applyParentCnsToGroundPreProjection=False,
                                                                        networkNode=engineIKNetwork)
            # - ethanm

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
    
