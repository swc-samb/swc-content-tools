


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
import mb_MakeLeg as leg

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

reload(util)

__author__ = 'Michael Buettner'
__version__ = '0.1.0'
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


#-----------------------------------------------------------------------------#
# Arthropod Leg Ctrl Module
#-----------------------------------------------------------------------------#

class arthropodLegCtrl(ctrl.ctrlModule):   
    '''Arthropod Leg Control Wrapper class''' 
    _isCtrl = True
    _label = 'Arthropod Leg'
    _color = (0.7,0.2,0.7)
    _isLegCtrl = True

    def __init__(self, *args, **kwargs):    
        self._nodeAttributes = {}
        
        self.keyword = 'thigh'
        self.startJoint = ''
        self.endJoint = ''
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
        self.ballPivot = False
        self.heelOnFloor = False

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

        util.printdebug("Module " + str(self._index) + ' adding leg, Keyword:' + str(self.keyword))
        
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
                mirroredStartJoint, mirroredEndJoint = util.getRigJoint([(util.mirrorName(self.startJoint) or None), 
                                                                         (util.mirrorName(self.endJoint) or None)])
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
        util.debugging = True
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
                spaceBlends = ({util.mirrorName(a):b for a,b in self._spaceBlendDict.items()} if self.useSpaceBlending else None)


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
                                   addInterIkPoleVector=self.addInterIkPoleVector,
                                   kneeSlideValue=self.kneeSlide,
                                   kneeSlideOffset=self.kneeSlideOffset,
                                   addEngineIK=self.engineIK,
                                   engineIKBallJoint=self.engineIKBallJoint,
                                   ikBaseOffset=self.ikBaseOffset,
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
        #set retarget hint attributes
        for hint_set in hint_sets:
            for ctr, joint in hint_set.items():
                print(' ', joint, '>', ctr)
                args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr)
                self.setRetargetHintAttributes(ctr, *args, **kwargs)

        return allControls



    def initDynamicLayoutParameters(self, 
                                    moduleLayout,
                                    ignoreList = None):
        ignoreList = ['twistKeyword', 'rollKeyword']                                
        super(type(self), self).initDynamicLayoutParameters(moduleLayout, ignoreList = ignoreList)

        #pm.separator(height=self._separatorHeight, style="none", parent=moduleLayout)

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

#-----------------------------------------------------------------------------#
#  Utitlity Functions
#-----------------------------------------------------------------------------#


def getLegJoint(firstjnt, keyword, searchByName=True, chain=None):
    if searchByName:
        joint = util.findInChain(firstjnt, keyword, chain=chain)
    else:
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
               addInterIkPoleVector=False,
               addHeelRoll=True,
               kneeSlideValue=0.1,
               kneeSlideOffset=0.0,
               addEngineIK=False,
               engineIKBallJoint=True,
               ikBaseOffset=0.0,
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
        connect_chain = [x.name().split('_RigJnt')[0] for x in chain]
        util.connectMessage(networkNode, 'joints', connect_chain)

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
        polePos, poleRot = leg.placePoleVector([in_thighjnt, in_kneejnt, in_anklejnt])
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
        aimCns = pm.aimConstraint(out_kneejnt, poleVectorINH, aimVector = (0, 0, 1) , upVector = aimUpVector , worldUpType = "scene") #, skip =['x','z']
        pm.delete(aimCns)

        poleVectorTarget = None
        if addInterIkPoleVector:
            inter_pvTransform = pm.createNode( 'transform', n=util.getNiceControllerName(thighJoint.name(), '_inter_PV_transform') , parent=in_kneejnt)
            pm.parent(inter_pvTransform, w=True)
            inter_polePos, inter_poleRot = leg.placeMultiJointPoleVector(in_thighjnt, in_balljnt, inter_leg_ikh)
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
        pivotObject = ik_balljnt

        if ballPivot:
            pivotObject = ik_balljnt

        pivotRot = pm.xform(pivotObject, q=True, ws=True, ro=True)

        offsetRot = pivotRot
        posCtrl, ctrlGrp = util.makeControl(pivotObject, conScale, constrainObj=None, worldOrient=True, separateRotateOrient=True)      #ik_balljnt          constrainObj=inter_leg_ikh
        pm.parent(ctrlGrp, masterGrp)
        #Create transform that will be child of posCtrl but also child of the heel, ball and tip pivot controls.
        posCtrlTransform = pm.createNode( 'transform', n=util.getNiceControllerName(posCtrl.name(),"_SubTransform") , parent=posCtrl)
        pm.parentConstraint(posCtrlTransform, inter_leg_ikh, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)     
        pm.orientConstraint(posCtrlTransform, ik_balljnt, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        rotateAnkleShape = [90,-90,0]  #[90,-90,0]
        if inter_ik_balljnt.name().find('r_') == 0:
            rotateAnkleShape = [90,90,0]
        
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

        # Added conditional 'OR' with alternative variable syntax - MM
        if worldUpAxis == 'Y' or worldUpAxis == [0, 1, 0]:
            rollControlUpVector = (0,0,1)
        else:
            rollControlUpVector = (1,0,0)

        if in_anklejnt.name().find('r_') == 0:
            ballOffset = -1.0 * ballOffset
            tipOffset = -1.0 * tipOffset
            heelOffset = -1.0 * heelOffset

        print(f"Forward Axis is: {forwardAxis}")
        if forwardAxis == 'X' or forwardAxis == [1, 0, 0]:
            ballOffsetVec = (ballOffset,0,0)
            tipOffsetVec = (tipOffset,0,0)
            heelOffsetVec = (heelOffset,0,0)
        elif forwardAxis == 'Y' or forwardAxis == [0, 1, 0]:
            ballOffsetVec = (0,ballOffset,0)
            tipOffsetVec = (0,tipOffset,0)
            heelOffsetVec = (0,heelOffset,0)
        else:
            ballOffsetVec = (0,0,ballOffset)
            tipOffsetVec = (0,0,tipOffset)
            heelOffsetVec = (0,0,heelOffset)
            
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

        if addHeelRoll:
            #Heel Roll
            heelRollTransform = pm.createNode( 'transform', n=util.getNiceControllerName(in_anklejnt.name(),"_heelGrp") , parent=posCtrl)
            heelRoll = util.makeNurbsShape(8, name=util.getNiceControllerName(in_anklejnt.name(),"_heel_CON"), scale=rollControlScale, forwardAxis=footRollControlForwardAxis)
            # pm.circle(ch=0, o=1, r=2*conScale, normal=rollControlUpVector, name=util.getNiceControllerName(in_anklejnt.name(),"_heel_CON"))[0]
            pm.xform(heelRollTransform, ws=1, translation = footRollCenterPosition)
            pm.xform(heelRollTransform, ws=1, rotation = (offsetRot))
            heelRollTransform.translateBy(heelOffsetVec, ws=False) #-30
            heelTranslation = pm.xform(heelRollTransform, q=True, ws=1, translation = True)
            if heelOnFloor:
                pm.xform(heelRollTransform, ws=1, translation = [heelTranslation[0], 0.0, heelTranslation[2]])

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
            tipTranslation = pm.xform(tipRollTransform, q=True, ws=1, translation = True)
            if heelOnFloor:
                pm.xform(tipRollTransform, ws=1, translation = [tipTranslation[0], 0.0, tipTranslation[2]])

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
        ballTranslation = pm.xform(ballRollTransform, q=True, ws=1, translation = True)
        if heelOnFloor:
            pm.xform(ballRollTransform, ws=1, translation = [ballTranslation[0], 0.0, ballTranslation[2]])


        pm.parent(ballRoll, ballRollTransform, r=True)


        if addHeelRoll:
            pm.parent(ballRollTransform, tipRollPivotTransform)
        else:
            pm.parent(ballRollTransform, posCtrl)

        pm.parentConstraint(ballRoll, posCtrlTransform, mo=True).setAttr('interpType', util.DEFAULT_INTERPTYPE)       #Constrain intermediate IK handle (which would be constrained by posctrl when not using footRoll)
        
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
        leg.createBlendColorBlend(inheritFootControlTransform.name(), inheritTransform.name(), inheritBlendTransform.name(), ankleCtrl.name() + ".autoAnkle")

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
            leg.createBlendColorBlend(ikjnt, fkjnt, outjnt, switchCtrl.name() + '.SwitchIkFk')
            chainjnt = chain[i]
            #util.printdebug("out_knee Joint: " + out_kneejnt)
            if (outjnt.name().find(out_kneejnt.name()) == 0):
                outjnt = kneeslideEndJnt   #Bind to slide joint instead of knee jnt
            if (outjnt.name().find(out_balljnt.name()) == 0):
                outjnt = out_iktweak_ballJnt   #Bind to tweak joint instead of ball jnt
            
            if (fkjnt not in toejnts):     #Do not constrain toe joints
                pm.parentConstraint(outjnt, chainjnt, mo=False).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        for i, ctrl in enumerate (fkControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', ctrl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.1)
            pm.setAttr(conditionNode.name()+ '.operation', 4) 

        ikControls = [posCtrl, ankleCtrl, poleVectorCtrl, turnCtrl, ballControl]
        for i, ctrl in enumerate (ikControls):
            conditionNode = pm.shadingNode('condition',  asUtility=True)
            pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', ctrl.getParent().name() + '.visibility')
            pm.setAttr(conditionNode.name()+ '.secondTerm', 0.9)
            pm.setAttr(conditionNode.name()+ '.operation', 2)    

        """ Add KneeSlide Attribute to SwitchCTRL """
        pm.addAttr(switchCtrl, ln = "kneeSlide", at= "double", min=0, defaultValue=kneeSlideValue, k=1)
        pm.connectAttr(switchCtrl.name()+ '.kneeSlide', kneeSlideMultNode.name() + ".input2.input2X")   
        pm.addAttr(switchCtrl, ln = "kneeSlideOffset", at= "double", defaultValue=kneeSlideOffset, k=1)
        pm.connectAttr(switchCtrl.name()+ '.kneeSlideOffset', kneeSlideMinusNode.name() + ".input1D[1]")

        """ PoleVector follows FK in FK mode"""
        weightAliases = poleVectorFKParentConstraint.getWeightAliasList()
       
        pm.connectAttr(switchCtrl.name() + '.SwitchIkFk', weightAliases[1])

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

        leg.createTwistJoints(out_anklejnt, out_kneejnt, in_kneejnt, kneeslideEndJnt=kneeslideEndJnt,
                         twistKeyword=twistKeyword, twistOffsetControl=switchCtrl)
        leg.createRollJoints(out_kneejnt, outjnts[0], thighJoint, rollKeyword=rollKeyword)


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
            engineIKSpaceSwitcherJoints = SpaceSwitcherJoints[:]
            engineIKCtrls, engineIKJoints = cr_MakeEngineIK.addIKJoints(in_anklejnt,
                                                                        poleikfkGrp,
                                                                        root,
                                                                        conScale,
                                                                        engineIKSpaceSwitcherJoints,
                                                                        group,
                                                                        in_balljnt,
                                                                        baseOffset=ikBaseOffset,
                                                                        ankleOrientObject=in_anklejnt,
                                                                        footControl=posCtrl,
                                                                        poleVectorName=pvTransform.name(),
                                                                        mainCtrl=mainCtrl,
                                                                        engineIKBallJoint=engineIKBallJoint)
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


