
import os
import sys
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
# simple FK Ctrl Module
#-----------------------------------------------------------------------------#


class simpleFKCtrl(ctrl.ctrlModule):   
    '''FK Control Wrapper class''' 
    _isCtrl = True
    _label = 'FK'
    _color = (0.4,0.6,0.4)

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

        #self.cube = False      This variable was replaced by self.controlShape
        self.controlShape = od([('Circle', 8),
                                ('Cube', 0),
                                ('Pin', 11)])
        self.mirrorModule = False
        self.inheritTranslation = False
        self.affectScale = False

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
     
        # ethanm - now tracking which joints are found with mirror module so that space blending can be mirrored accordingly



        leftPrefix = (kwargs.get('leftPrefix') or 'l_')
        rightPrefix = (kwargs.get('rightPrefix') or 'r_')

        if self.jointList:
            jointList = util.getRigJoint(self.jointList)

            # ethanm - given jointlist is not mirrored
            mirrored = [False]*len(jointList)

            if self.mirrorModule:
                mirrorJointList = []
                for j in jointList:
                    mj = pm.PyNode(util.mirrorName(j, leftPrefix, rightPrefix))
                    if mj and mj not in jointList:
                        mirrorJointList.append(mj)

                jointList += mirrorJointList

                # ethanm - update corresponding mirrored list for mirrored joints
                mirrored += [True]*len(mirrorJointList)

        else:
            startJoint, endJoint = util.getRigJoint([(self.startJoint or None), (self.endJoint or None)])
            startJoint = startJoint or endJoint
            endJoint = endJoint or startJoint

            jointList = []
            if (endJoint and startJoint):
                startJoints = [startJoint]
                endJoints = [endJoint]
                mirroredEndJoint = False
                mirroredStartJoint = False

                # ethanm - given start and end joints are not mirrored
                mirroredBase = [False]

                if self.mirrorModule:
                    mirroredStartJoint, mirroredEndJoint = util.getRigJoint([(pm.PyNode(util.mirrorName(startJoint, leftPrefix, rightPrefix)) or None), 
                                                                             (pm.PyNode(util.mirrorName(endJoint, leftPrefix, rightPrefix)) or None)])
                if (mirroredEndJoint and mirroredStartJoint):
                    startJoints.append(mirroredStartJoint)
                    endJoints.append(mirroredEndJoint)
                    
                    # ethanm - found mirrored joints are mirrored
                    mirroredBase.append(True)
                
                mirrored = []
                for i,j in enumerate(startJoints):
                    if startJoints[i] != endJoints[i]:
                        chain = util.getChainFromStartToEnd(j, endJoints[i])
                    else:
                        chain = [startJoints[i]]
                    jointList += chain
                    
                    # ethanm - fill out mirrored list for each joint if its start/end joints were mirrored or not
                    mirrored += [mirroredBase[i]]*len(chain)

            else:
                if not self.keyword:
                    raise ValueError('No Joints or Keyword Given:' + self.keyword)                    
                jointList = util.findAllInChain(root, self.keyword)
                if jointList == None:
                    raise ValueError('Joint not found in hierarchy: ' + self.keyword)
                startJoints = [None]*len(jointList)
                endJoints = [None]*len(jointList)

                # ethanm - no way to reliably tell if keyword joints space blends should be mirrored or not 
                # ethanm - if mirrored spaceblending is needed set the module for one side and check mirror module
                mirrored = [False]*len(jointList)
        
        rigNetwork = kwargs.get('rigNetwork')        
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network' if self.keyword else f'{displayModuleName}_{self.getTitle()}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        #since using mutable types are default args can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []


        # ethanm - set up space blending for each joint and mirrored as indicated by the mirrored list
        spaceBlends = []
        for mirror, joint in zip(mirrored, jointList):
            if not mirror:
                spaceBlends.append((self._spaceBlendDict if self.useSpaceBlending else None))
            else:
                spaceBlends.append(({util.mirrorName(k, leftPrefix, rightPrefix):v for k,v in self._spaceBlendDict.items()} if self.useSpaceBlending else None))

        
        util.printdebug("Module " + str(self._index) + ' adding FK, Keyword:' + str(self.keyword))
        for item in jointList:
            print(' - {}'.format(item))

        fkControlGrps, fkCtrls = mb_makeSimpleFKControl(jointList, 
                                                        conScale = controlSize * 0.8 * self.moduleSize, 
                                                        SpaceSwitcherJoints = moduleSpaceSwitchList,
                                                        forwardAxis = self.forwardAxis,
                                                        setNameKeyword=str(self.keyword),
                                                        controlShape=self.controlShape,
                                                        group=group,
                                                        inheritTranslation=self.inheritTranslation,
                                                        mainCtrl=mainCtrl,
                                                        spaceBlends=spaceBlends, # ethanm - space blends is a list of dicts for each joint 
                                                        affectScale=self.affectScale) # ethanm - Affects scale connects controls scale attribute to target joint 
        if group:                                                   
            pm.parent(fkControlGrps, group)
        
        util.connectMessage(networkNode, 'controls', fkCtrls)
        connect_chain = [x.name().split('_RigJnt')[0] for x in jointList]
        util.connectMessage(networkNode, 'joints', connect_chain)

        self.createControlAttributes(fkCtrls)

        #set retarget hint attributes
        for ctr, joint in zip(fkCtrls, jointList):
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr)
            self.setRetargetHintAttributes(ctr, *args, **kwargs)

        return fkCtrls
        


#-----------------------------------------------------------------------------#
#  Utitlity Functions
#-----------------------------------------------------------------------------#


def lockandhide(obj, leaverot, leavescale=False):
    pm.setAttr(obj + ".tx", lock=True, keyable=False)
    pm.setAttr(obj + ".ty", lock=True, keyable=False)
    pm.setAttr(obj + ".tz", lock=True, keyable=False)
    if (leaverot == 0):
        pm.setAttr(obj + ".rx", lock=True, keyable=False)
        pm.setAttr(obj + ".ry", lock=True, keyable=False)
        pm.setAttr(obj + ".rz", lock=True, keyable=False)
    if not leavescale:
        pm.setAttr(obj + ".sx", lock=True, keyable=False)
        pm.setAttr(obj + ".sy", lock=True, keyable=False)
        pm.setAttr(obj + ".sz", lock=True, keyable=False)
    pm.setAttr(obj + ".v", lock=True, keyable=False)
    
def mb_makeSimpleFKControl(joints=None, 
                           conScale = 5, 
                           SpaceSwitcherJoints=[], 
                           parentObj=None, 
                           forwardAxis=(1,0,0), 
                           createSet=True, 
                           setNameKeyword=False, 
                           inheritTranslation=False, 
                           controlShape=8, 
                           group=None, 
                           mainCtrl=None,
                           spaceBlends=None,
                           affectScale=False):
    
    #objects = cmds.ls(sl=True)
    if (joints != None):
        objects = joints
    else:
        objects = pm.ls(sl=True)

    grpNodes = []
    fkControls = []

    if not spaceBlends or len(objects) != len(spaceBlends):
        spaceBlends = [None]*len(objects)

    for i, obj in enumerate(objects):
        
        suffix = "Grp" 
        inherit = ""
        #util.printdebug("Make Simple FK Control on object: " + str(obj))
        inherit = "CON" + obj.name() + "INH"
        inherit = pm.group(em=True, name=str(inherit) )
        inheritTrans = pm.group(em=True, name=str(inherit)+"Trans" )
        
        """Create Control"""
        ctrl = util.makeNurbsShape(controlShape, name=obj.name().replace("_RigJnt", "")+"_CON", forwardAxis='X' if forwardAxis[0]==1 else 'Y')
        spans = cmds.getAttr(ctrl + ".spans")
        cmds.select(ctrl + ".cv[0:" + str(spans) + "]", r=True )
        cmds.scale(conScale , conScale , conScale, r=True)
        if obj.name().lower().find('r_') == 0:
            cmds.rotate(180,0,0, os=True)

        pm.select(ctrl, r=True)
        
        if (parentObj == None):
            """Set INH pivot to parent pivot"""
            objparent = obj.listRelatives(p=True)
            if (objparent is not None and len(objparent)>0):
                objparent = objparent[0]
        else:
            objparent = parentObj

        if (objparent is not None):
                pm.parent(inherit, objparent, r=True)
                pm.parent(inherit, w=True )

        """Match inheritTrans transform and parent to inherit"""
        pm.parent(inheritTrans, obj, r=True)
        pm.parent(inheritTrans, w=True )
        pm.parent(inheritTrans, inherit)

        """Create Group node"""
        grpNode = pm.group(ctrl, n = ctrl + suffix)
        
        """Match grpNode transform to object""" 
        pm.parent(grpNode, obj, r=True)
        pm.parent(grpNode, w=True )
        """Parent grpNode to INH node"""
        pm.parent(grpNode, inheritTrans)

        
        """ Master """
        master = pm.group(em=True, name =  "CON_" + obj + "Master")
        pm.parent(master, inherit, r=True)
        pm.parent(master, w=True)
        pm.parent(inherit, master)
        if mainCtrl:
            pm.connectAttr(mainCtrl.name() + ".scale", master.name() + ".scale")

        lockandhide(master,0)
  
        
        """Constrain joint position to control"""
        pm.pointConstraint(ctrl, obj, mo=True, weight= 1)
        
        pm.makeIdentity(grpNode, apply=True, t=1, r=1, s=1 )
        """Constrain selected object"""
        pm.orientConstraint(ctrl, obj, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)

        

        if (parentObj == None):
            parent = obj.getParent()
        else:
            parent = parentObj

        if (len(SpaceSwitcherJoints) > 0):
            perObjectSpaceSwitcherJoints = list(SpaceSwitcherJoints)
            if (parent not in perObjectSpaceSwitcherJoints):
                perObjectSpaceSwitcherJoints.insert(0, parent)
            elif(len(perObjectSpaceSwitcherJoints) > 1 and perObjectSpaceSwitcherJoints.index(parent) > 0):
                k = perObjectSpaceSwitcherJoints
                a, b = k.index(parent), 0
                k[b], k[a] = k[a], k[b]

            if (len(perObjectSpaceSwitcherJoints) > 0):
                if not inheritTranslation:
                    util.setupSpaceSwitch(pm.PyNode(ctrl), 
                                          perObjectSpaceSwitcherJoints, 
                                          nameDetailLevel=3, 
                                          inheritParentLevel=2, 
                                          fk=True,
                                          spaceBlends=spaceBlends[i])
                else:
                    util.setupSpaceSwitch(pm.PyNode(ctrl), 
                                          perObjectSpaceSwitcherJoints, 
                                          nameDetailLevel=3, 
                                          inheritParentLevel=2,
                                          spaceBlends=spaceBlends[i])
        else:  #Constrain inherit to parent joint
            if (objparent is not None): 
                pm.orientConstraint(objparent, inherit, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
                pm.pointConstraint(objparent, inherit, mo=True, weight= 1)
        lockandhide(inherit, 0)

        util.lockAndHideAttributes(ctrl, hideScale=not affectScale) # ethanm - dont lock/hide scale if it needs to scale the joint

        grpNodes.append(master)
        pmctrl = pm.PyNode(ctrl)
        fkControls.append(pmctrl)

        # ethanm - connect control scale to target joint scale if affectScale
        if affectScale:
            print('Scale {}.scale -> {}.scale'.format(ctrl, util.getExportJoint(obj)))
            pm.connectAttr('{}.scale'.format(ctrl), '{}.scale'.format(util.getExportJoint(obj)))

    #Create Sets
    if createSet:
        if setNameKeyword is not False:
            setName = setNameKeyword
        else:
            setName = joints[0].name()
        fkSet = pm.sets(fkControls, name= util.getNiceControllerName(setName, '_fk_ctrl_set'))
        if group:
            util.addToSet(fkSet, group.name() + '_set')

    return grpNodes, fkControls


#mb_makeSimpleFKControl()
