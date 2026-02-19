
import os, sys
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
# Muscle Ctrl Module
#-----------------------------------------------------------------------------#


class torsoMuscleCtrl(ctrl.ctrlModule):   
    '''Torso Muscle Control Wrapper class''' 
    _isCtrl = True
    _label = 'Torso Muscle'
    _color = (0.6,0.6,0.4)

    def __init__(self, *args, **kwargs):
        #super(type(self), self).__init__(*args, **kwargs)
        self._nodeAttributes = {}
        self.keyword = ''

        self.pectoral = ''
        self.latissimus = ''
        self.scapular = ''
        self.trapezius = ''
        self.torso = ''
        self.shoulder = ''
        self.neck = ''
        self._nodeAttributes['pectoral'] = True
        self._nodeAttributes['latissimus'] = True
        self._nodeAttributes['scapular'] = True
        self._nodeAttributes['trapezius'] = True
        self._nodeAttributes['torso'] = True
        self._nodeAttributes['shoulder'] = True
        self._nodeAttributes['neck'] = True
        self.forwardAxis = od([('X',[1,0,0]),
                               ('Y',[0,1,0]),
                               ('Z',[0,0,1])])
        self.mirrorModule = False

        type(self).__bases__[0].__init__(self, *args, **kwargs)
                                

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

        pectoralJoint, latissimusJoint, scapularJoint, trapeziusJoint, torsoJoint, shoulderJoint, neckJoint = util.getRigJoint([(self.pectoral or None),
                                                                                                    (self.latissimus or None),
                                                                                                    (self.scapular or None),
                                                                                                    (self.trapezius or None),
                                                                                                    (self.torso or None), 
                                                                                                    (self.shoulder or None),
                                                                                                    (self.neck or None)])
        muscleJoints = [pectoralJoint, latissimusJoint, scapularJoint, trapeziusJoint]

        allControls = []
        for i, muscleJoint in enumerate(muscleJoints):

            if (muscleJoint and torsoJoint and shoulderJoint):
                pectoralJoints = [muscleJoint]
                shoulderJoints = [shoulderJoint]
                mPectoralJoint = False
                mShoulderJoint = False

                if self.mirrorModule:
                    mPectoralJoint, mShoulderJoint = util.getRigJoint([(pm.PyNode(util.mirrorName(muscleJoint.name())) or None), ( pm.PyNode(util.mirrorName(shoulderJoint.name())) or None)])

                    if (mPectoralJoint and mShoulderJoint):
                        util.printdebug("Found mirrored Muscle Joint: " + mPectoralJoint.name() )
                        pectoralJoints.append(mPectoralJoint)
                        shoulderJoints.append(mShoulderJoint)
                    else:
                        util.printdebug("Did not find mirrored Muscle Joint")
            else:
                continue
                #raise ValueError('Joints not defined')

            #since using mutable types are default arges can be problematic
            if moduleSpaceSwitchList == None:
                moduleSpaceSwitchList = []
            
            util.printdebug("Module " + str(self._index) + ' adding Muscle, Keyword:' + str(self.keyword))

            #Adjust how the muscle joint follows the other joints
            followScale = [0.5,0.5,0.5]
            aimJoint = None
            if muscleJoint == latissimusJoint:
                followScale = [0.5,0.3,0.5]
            elif muscleJoint == trapeziusJoint:
                followScale = [1.0,1.0,1.0]
                aimJoint = neckJoint
            elif muscleJoint == scapularJoint:
                followScale = [1.0,0.7,0.9]
                aimJoint = torsoJoint
            grps = []
            aimVector = (-1, 0, 0)
            
            for k, j in enumerate(pectoralJoints):
                if j.name().find('r_') == 0:    # Check name to flip the aimVector on the right side. There is probably a better way than checking for the name prefix.
                    aimVector = (1, 0, 0)
                #util.printdebug(j)

                util.printdebug("   Muscle Joint: " + str(j))
                util.printdebug("\n   Shoulder Joint: " + str(shoulderJoints[k]))
                util.printdebug("   Torso Joint: " + str(torsoJoint))

                newGrp, ctrls = mb_makeTorsoMuscle(muscleJoint=j, 
                                                   shoulderJoint=shoulderJoints[k],
                                                   torsoJoint=torsoJoint,
                                                   conScale=controlSize * self.moduleSize,
                                                   followScale=followScale,
                                                   aimJoint=aimJoint,
                                                   aimVector=aimVector
                                                   )
                grps.append(newGrp)            
                allControls += ctrls
                
            if group:
                pm.parent(grps, group)

            
        newSet = pm.sets(allControls, name= util.getNiceControllerName(self.keyword, '_ctrl_set'))
        if group:
            util.addToSet(newSet, group.name() + '_set')

        self.createControlAttributes(allControls)
        connect_chain = [x.name().split('_RigJnt')[0] for x in muscleJoints]
        util.connectMessage(networkNode, 'joints', connect_chain)
        util.connectMessage(networkNode, 'controls', allControls)

        return allControls
    


#-----------------------------------------------------------------------------#
#  Utitlity Functions
#-----------------------------------------------------------------------------#

def mb_makeTorsoMuscle( muscleJoint, 
                        shoulderJoint,
                        torsoJoint,
                        conScale=1,
                        followScale=[0.5,0.5,0.5],
                        aimJoint=None,
                        aimVector=(-1, 0, 0) ):

    ctrl, ctrlGrp = util.makeControl(muscleJoint, conScale, constrainObj=muscleJoint, worldOrient=False, shape=0)
    ctrlINH = ctrl.getParent()
    
    msclTransformGrp = pm.createNode( 'transform', n=util.getNiceControllerName(muscleJoint.name(),"_Grp") , parent=muscleJoint)
    pm.parent(msclTransformGrp, torsoJoint)
    msclFollow = msclTransformGrp.duplicate()[0]
    pm.parent(msclFollow, msclTransformGrp)

    followCns = pm.pointConstraint([torsoJoint, shoulderJoint], msclFollow, mo=True)

    pm.disconnectAttr(followCns.name() + ".constraintTranslateX", msclFollow.name() + ".translateX")
    pm.disconnectAttr(followCns.name() + ".constraintTranslateY", msclFollow.name() + ".translateY")
    pm.disconnectAttr(followCns.name() + ".constraintTranslateZ", msclFollow.name() + ".translateZ")

    multNode = pm.shadingNode('multiplyDivide', asUtility=True)
    pm.connectAttr(followCns.name() + '.constraintTranslate', multNode.name() + '.input1')
    pm.connectAttr(multNode.name() + '.output', msclFollow.name() + '.translate')
    pm.setAttr(multNode.name()+ '.input2', followScale)

    msclCns = pm.parentConstraint(msclFollow, ctrlINH, mo=True)
    msclCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
    
    if aimJoint is not None:
        aimCns = pm.aimConstraint(aimJoint, msclFollow, aimVector = aimVector, upVector = (0,-1, 0), worldUpType = "object", worldUpObject=torsoJoint, mo=True) #worldUpType = "objectrotation"
        

    return ctrlGrp, [ctrl]



