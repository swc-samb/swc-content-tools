
from doctest import master
import os
import re
import sys
from collections import OrderedDict as od
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
import pymel.core.datatypes as pymeldt

from EvoRig import mb_rig_utilities as util
import mb_MakeSimpleFKControl


util.debugging = True

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 
    
import ctrl; reload(ctrl);
import em_rig_nodes as rn; reload(rn);

#-----------------------------------------------------------------------------#
# WingFeathers Ctrl Module
#-----------------------------------------------------------------------------#


class wingFeathersCtrl(ctrl.ctrlModule):   
    '''Wing Feathers Control Wrapper class''' 
    _isCtrl = True
    _label = 'WingFeathers'
    _color = (0.2,0.4,0.6)

    def __init__(self, *args, **kwargs):
        #super(type(self), self).__init__(*args, **kwargs)
        self._nodeAttributes = {}
        self.keyword = ''

        self.jointList = []
        self.masterList = []
        self._nodeAttributes['jointList'] = True
        self._nodeAttributes['masterList'] = True
        self.forwardAxis = od([('X',[1,0,0]),
                               ('Y',[0,1,0]),
                               ('Z',[0,0,1])])

        #self.cube = False      This variable was replaced by self.controlShape
        self.controlShape = od([('Circle', 8)])  #,
                                #('Cube', 0),
                                #('Pin', 11)]
        self.mirrorModule = False
        self.inheritTranslation = False
        self.affectScale = False
        self.rigChildJoints = True

        # ethanm - match master joint children with joint children
        self.useMasterChildJoints = False

        # ethanm - treat non control joints as membrane (like a bat wing)
        self.membrane = False

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
        mirrorJointList = []
        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = util.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network' if self.keyword else f'{displayModuleName}_{self.getTitle()}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        if self.jointList:
            jointList = util.getRigJoint(self.jointList)
            masterList = util.getRigJoint(self.masterList)

            # ethanm - given jointlist is not mirrored
            mirrored = [False]*len(jointList)
            mirroredMaster = [False]*len(jointList)

            if self.mirrorModule:
                mirrorJointList = []
                for j in jointList:
                    mj = pm.PyNode(util.mirrorName(j))
                    if mj and mj not in jointList:
                        mirrorJointList.append(mj)

                #jointList += mirrorJointList

                # ethanm - update corresponding mirrored list for mirrored joints
                mirrored += [True]*len(mirrorJointList)

                #Mirror Master List
                mirrorMasterJointList = []
                for j in masterList:
                    mmj = pm.PyNode(util.mirrorName(j))
                    if mmj and mmj not in mirrorMasterJointList:
                        mirrorMasterJointList.append(mmj)

                mirroredMaster += [True]*len(mirrorMasterJointList)
                #masterList += mirrorMasterJointList

        #since using mutable types are default args can be problematic
        if moduleSpaceSwitchList == None:
            moduleSpaceSwitchList = []


        # michael - set up space blending for each joint. Cannot merge them into one list because finding feather master controls is based on proximity. Do not want a left side control to affect a right side control
        spaceBlends = []
        mSpaceBlends = []
        for joint in jointList:
            spaceBlends.append((self._spaceBlendDict if self.useSpaceBlending else None))
        
        for joint in mirrorJointList:
            mSpaceBlends.append(({util.mirrorName(k):v for k,v in self._spaceBlendDict.items()} if self.useSpaceBlending else None))
        
        
        util.printdebug("Module " + str(self._index) + ' adding Wing, Keyword:' + str(self.keyword))
        for item in jointList:
            print(' - {}'.format(item))
        for item in mirrorJointList:
            print(' - {}'.format(item))

        # ethanm - added jointListTotal output to handle joints found recursively in the function
        wingControlGrps, wingCtrls, jointListTotal = mb_makeWingFeathersControls(jointList, 
                                                                                masterList,
                                                                                conScale = controlSize * 0.8 * self.moduleSize, 
                                                                                SpaceSwitcherJoints = moduleSpaceSwitchList,
                                                                                forwardAxis = self.forwardAxis,
                                                                                setNameKeyword=str(self.keyword),
                                                                                controlShape=self.controlShape,
                                                                                group=group,
                                                                                mainCtrl=mainCtrl,
                                                                                spaceBlends=spaceBlends, # ethanm - space blends is a list of dicts for each joint 
                                                                                affectScale=self.affectScale, # ethanm - Affects scale connects controls scale attribute to target joint
                                                                                rigChildJoints=self.rigChildJoints,
                                                                                useMasterChildJoints = self.useMasterChildJoints,# ethanm - match master joint children with joint children
                                                                                membrane=self.membrane,
                                                                                networkNode=networkNode) # ethanm - treat non control joints as membrane (like a bat wing)
        
        # ethanm - added jointListTotal output to handle joints found recursively in the function
        if self.mirrorModule:
            mwingControlGrps, mwingCtrls, mjointListTotal = mb_makeWingFeathersControls(mirrorJointList, 
                                                                                        mirrorMasterJointList,
                                                                                        conScale = controlSize * 0.8 * self.moduleSize, 
                                                                                        SpaceSwitcherJoints = moduleSpaceSwitchList,
                                                                                        forwardAxis = self.forwardAxis,
                                                                                        setNameKeyword=str(self.keyword),
                                                                                        controlShape=self.controlShape,
                                                                                        group=group,
                                                                                        mainCtrl=mainCtrl,
                                                                                        spaceBlends=mSpaceBlends, # ethanm - space blends is a list of dicts for each joint 
                                                                                        affectScale=self.affectScale,# ethanm - Affects scale connects controls scale attribute to target joint
                                                                                        rigChildJoints=self.rigChildJoints,
                                                                                        useMasterChildJoints = self.useMasterChildJoints,# ethanm - match master joint children with joint children
                                                                                        membrane=self.membrane,
                                                                                        networkNode=networkNode) # ethanm - treat non control joints as membrane (like a bat wing) 

            wingControlGrps += mwingControlGrps
            wingCtrls += mwingCtrls
            jointListTotal += mjointListTotal


        if group:                                                   
            pm.parent(wingControlGrps, group)

        self.createControlAttributes(wingCtrls)

        #set retarget hint attributes
        for ctr, joint in zip(wingCtrls, jointListTotal):
            args, kwargs = ctrl.retargets.modules['Parent Constraint']._hint(util.getExportJoint(joint) or joint,ctr)
            self.setRetargetHintAttributes(ctr, *args, **kwargs)

        return wingCtrls
        


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


def getWeightsByDistance(joint, masters):
    
    if len(masters) < 2:
        return [1.0, 0.0]

    A = pymeldt.Vector(pm.xform(masters[0], q=True, ws=True, rp=True))
    B = pymeldt.Vector(pm.xform(masters[1], q=True, ws=True, rp=True))
    P = pymeldt.Vector(pm.xform(joint, q=True, ws=True, rp=True))
    distA = pymeldt.length(A-P)
    distB = pymeldt.length(B-P)

    delta = A-B
    deltaLength = pymeldt.length(delta)
    deltaNormalized = pymeldt.normal(delta)
    wA = deltaNormalized.dot(P-B) / deltaLength 
    
    #wA = (distA / distB) / 2.0
    #wA = 1.0 - wA
    wA = max(min(wA, 1.0), 0.0) #clamp value
    weights = [wA, 1.0 - wA]
    #print(f"Weights of joint {joint.name()} are A: {weights[0]} and B: {weights[1]}")
    #print(f"Distances are {distA} and {distB}")

    return weights



def findTwoNearestMasters(joint, masterList):    
    # ethanm - checking for nearest master joints who are on both sides of joint
    
    if len(masterList) == 1:
        return [masterList[0]]

    # store points and sort masterlist by distance from joint
    point = pymeldt.Vector(pm.xform(joint,q=True,ws=True,sp=True))
    points = {x:pymeldt.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in masterList}
    distances = {x:(point - points[x]).length() for x in masterList}
    masterList.sort(key=lambda x: distances.get(x))
    near_point = points[masterList[0]]

    # Get list of master joints who are on the other side of joint from the nearest master joint using rn.deltDot
    # deltadot = dot(joint-nearest, next_nearest-nearest)
    in_between = lambda x: sys.float_info.epsilon < rn.deltaDot(joint,[x,masterList[0]]) <= (near_point - points[x]).length()
    valid_masters = [x for x in masterList if x != masterList[0] and in_between(x)]

    #if no combination of master joints is on both side of joint, just return the next nearest joint
    return [masterList[0], (valid_masters or [masterList[1]])[0]]


    closestIndeces = []
    distances = []
    distancePairList = []
    for i, masterJnt in enumerate(masterList):
        masterPos = pymeldt.Vector(pm.xform(masterJnt, q=True, ws=True, rp=True))
        jointPos = pymeldt.Vector(pm.xform(joint, q=True, ws=True, rp=True))
        #print("masterPos is {} and jointPos is {}".format(masterPos, jointPos))
        #dist = pymeldt.dist(masterPos, jointPos)
        dist = pymeldt.length(masterPos - jointPos)
        distancePairList.append((dist, i))

    distancePairList.sort()   #sort by first element in tuple       key=lambda y: y[1]

    distances, indeces = zip(*distancePairList)
    #take two closest
    closestIndeces = indeces[0:2]
    
    #debug
    # names = []
    # for j in closestIndeces:
    #     names.append(masterList[j].name())
    #print (f"--------------------\nDistance pair list {distancePairList}")
    #print (f"--------------------\nThe closest indeces to {joint.name()} are \n{closestIndeces} with the names \n{names}")
    
    #build list from indeces
    closestJointsPair = []
    for j in closestIndeces:
        closestJointsPair.append(masterList[j])

    return closestJointsPair

def getNeighborMastersAndWeights(joint, masterList):
    masterPair = findTwoNearestMasters(joint, masterList)
    weights = getWeightsByDistance(joint, masterPair)

    return masterPair, weights

    
def mb_makeWingFeathersControls(jointList, 
                                masterList,
                                conScale = 5, 
                                SpaceSwitcherJoints = [],
                                forwardAxis = (1,0,0), 
                                setNameKeyword=False, 
                                controlShape=8, 
                                group=None,
                                mainCtrl=None,
                                spaceBlends=None, 
                                affectScale=True,
                                rigChildJoints=True,
                                useMasterChildJoints=True,# ethanm - match master joint children with joint children
                                membrane=False,
                                networkNode=None): # ethanm - treat non control joints as membrane (like a bat wing)
    
    if setNameKeyword is not False:
        setName = setNameKeyword
    else:
        setName = masterList[0].name()

    grpName = setName
    # michaelb - Add a side prefix to the group name because a single module can create a group for each side.
    if util.getPrefixSide(grpName) == 0:
        grpName = util.getSidePrefixString(masterList[0]) + grpName

    grpNodes = []
    allControls = []

    """ Main Group """
    mainGrp = pm.group(em=True, name = grpName + "_MainGrp")
    pm.parent(mainGrp, masterList[0], r=True)
    pm.parent(mainGrp, w=True)
    
    if mainCtrl:
        pm.connectAttr(mainCtrl.name() + ".scale", mainGrp.name() + ".scale")

    lockandhide(mainGrp,0)
    
    visctrl = makeVisControl(mainGrp, masterList[0], grpName, conScale=conScale)

    if not spaceBlends or len(jointList) != len(spaceBlends):
        spaceBlends = [None]*len(jointList)


    # ethanm control lookup
    controlLookup = {}

    # ethanm - match master joint children with joint children
    jointListTotal = []
    workList = [[masterList,jointList]]
    for w,lists in enumerate(workList):
        masterList,jointWorkList = lists
        masterChildren = pm.listRelatives(masterList, c=True,type='joint')
        jointChildren = pm.listRelatives(jointWorkList, c=True,type='joint')

        # ethanm - if any master joint has children, but some dont, add the childless ones to the child list.
        if masterChildren:
            masterChildren.extend([x for x in masterList if not pm.listRelatives(x,c=True,type='joint')])

        if rigChildJoints and useMasterChildJoints and masterChildren and jointChildren:
            workList.append([masterChildren, jointChildren])
        if w:
            spaceBlends = [None]*len(jointWorkList)

        for i, obj in enumerate(jointWorkList):
            jointListTotal.append(obj)
            print('connecting ', obj)

            suffix = "Grp" 
            inherit = ""
            #util.printdebug("Make Simple FK Control on object: " + str(obj))
            inherit = "CON" + obj.name() + "INH"
            inherit = pm.group(em=True, name=str(inherit) )
            inheritTrans = pm.group(em=True, name=str(inherit)+"Trans" )
            pm.parent(inherit, mainGrp)
            isMaster = False
            """Create Control"""
            if obj in masterList:
                controlShape = 13
                isMaster = True
            else:
                controlShape = 8

            ctrl = util.makeNurbsShape(controlShape, name=obj.name().replace("_RigJnt", "")+"_CON", forwardAxis='X' if forwardAxis[0]==1 else 'Y')
            #ethanm - control lookup
            controlLookup[obj] = ctrl

            spans = cmds.getAttr(ctrl + ".spans")
            cmds.select(ctrl + ".cv[0:" + str(spans) + "]", r=True )
            cmds.scale(conScale , conScale , conScale, r=True)
            if obj.name().lower().find('r_') == 0:
                cmds.rotate(180,0,0, os=True)

            pm.select(ctrl, r=True)
            
            
            """Set INH pivot to parent pivot"""
            objparent = obj.listRelatives(p=True)
            if (objparent is not None and len(objparent)>0):
                objparent = objparent[0]
        

            #if (objparent is not None):
            #        pm.parent(inherit, objparent, r=True)
            #        pm.parent(inherit, w=True )

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

            """Create followTransformNode node"""
            followTransformNode = pm.group(ctrl, n = ctrl + "FollowTransform" + suffix)
            pm.parent(followTransformNode, obj, r=True)
            #pm.parent(grpNode, w=True )
            pm.parent(followTransformNode, inheritTrans)

            """Set influence by feather master controls """
            pm.parent(ctrl, w=True )    #move ctrl to world space because grpNode will change rotation when constraint weights are uneven
            masterNeighborJoints, weights = None, None
            if obj not in masterList:
                masterNeighborJoints, weights = getNeighborMastersAndWeights(obj, masterList)
            
            scaleConstraint = None
            if masterNeighborJoints:
                # ethanm - membranes now use membrane aim constraint towards the delta between neighbord child joints
                if membrane:
                    pm.xform(followTransformNode,a=True,ws=True,matrix=pm.xform(obj,q=True,ws=True,matrix=True))
                    if pm.listRelatives(obj,c=True,type='joint'):
                        followAim = pm.createNode('transform',ss=True,parent=followTransformNode,name='{}_Aim'.format(followTransformNode))
                        pm.xform(followAim,a=True,ws=True,matrix=pm.xform(rn.getAimEndNode(obj),q=True,ws=True,matrix=True))
                    rn.membraneAimConstraint(followTransformNode, masterNeighborJoints, parent=mainGrp)
                    if affectScale:
                        scaleConstraint = pm.scaleConstraint(ctrl, obj)
                else:
                    parentCns = pm.orientConstraint(masterNeighborJoints, followTransformNode, mo=True)
                    parentCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
                    #for a,b in zip(masterNeighborJoints, parentCns.getWeightAliasList()):
                    #    print('{}  ->  {}'.format(a,b))

                    for w, weightAlias in enumerate(parentCns.getWeightAliasList()):
                        parentCns.setAttr(weightAlias.attrName(longName=True), weights[w])
                    

            pm.parent(ctrl, grpNode)    #parent control back to group

            """ Allow disabling auto-follow """
            parentFollowCns = pm.parentConstraint([inheritTrans, followTransformNode], grpNode, mo=True)
            parentFollowCns.setAttr('interpType', util.DEFAULT_INTERPTYPE)
            weightAliases = parentFollowCns.getWeightAliasList()
            oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
            oneMinusNode.setAttr("operation" , 2)
            pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)
            pm.connectAttr(visctrl.name() + ".Follow", oneMinusNode + ".input1D[1]")
            pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
            pm.connectAttr(visctrl.name() + ".Follow", weightAliases[1])

            # ethanm - scale constraint isnt related to follow logic, its just ctrl.scale->joint.scale
            # if membrane and scaleConstraint:
            #     weightAliasesScale = scaleConstraint.getWeightAliasList()
            #     pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliasesScale[0])
            #     pm.connectAttr(visctrl.name() + ".Follow", weightAliasesScale[1])

            
            # ethanm -          
            if membrane and (obj not in masterList and obj not in jointList):
                # ethanm - propogating parent transforms for membranes under first tier to counteract aim when adjusting rotation
                current_ctrl = ctrl
                current_obj = obj
                parent_list = []
                while current_obj not in jointList:
                    current_obj = current_obj.getParent()
                    parent_list.append(current_obj)    
                parent_list.reverse()        
                print('parent_check', obj, parent_list)
                if len(parent_list) > 1:
                    mult_last = pm.createNode('multMatrix',ss=True)
                    pm.connectAttr(controlLookup[parent_list[0]].matrix, mult_last.matrixIn[0])
                    pm.connectAttr(controlLookup[parent_list[1]].matrix, mult_last.matrixIn[1])
                    for n in range(2, len(parent_list)):
                        mult_new = pm.createNode('multMatrix',ss=True)
                        pm.connectAttr(mult_last.matrixSum, mult_new.matrixIn[0])
                        pm.connectAttr(controlLookup[parent_list][n].matrix, mult_last.matrixIn[1])
                        mult_last = mult_new
                    output_attribute = mult_last.matrixSum
                else:
                    output_attribute = controlLookup[parent_list[0]].matrix

                follow_switch  = pm.createNode('blendMatrix',ss=True)
                pm.connectAttr(inheritTrans.offsetParentMatrix, follow_switch.target[0].targetMatrix)
                pm.connectAttr(output_attribute, follow_switch.target[1].targetMatrix)
                reverse = pm.createNode('reverse',ss=True)
                pm.connectAttr(visctrl.Follow, reverse.inputX)
                pm.connectAttr(reverse.outputX, follow_switch.target[0].weight)
                pm.connectAttr(visctrl.Follow, follow_switch.target[1].weight)
                pm.connectAttr(follow_switch.outputMatrix, ctrl.offsetParentMatrix)

                    
            """Constrain joint position to control"""
            pm.pointConstraint(ctrl, obj, mo=True, weight=1)
            
            #pm.makeIdentity(grpNode, apply=True, t=1, r=1, s=1 )
            """Constrain selected object"""
            pm.orientConstraint(ctrl, obj, mo=True, weight=1).setAttr('interpType', util.DEFAULT_INTERPTYPE)



            """ Connect visibility attribute """
            if isMaster == False:
                pm.connectAttr(visctrl + '.Slave_Visibility', ctrl + '.visibility')
                conditionNode = pm.shadingNode('condition', asUtility=True)

                #connectAttr -f l_feather_01_01_RigJnt_VisCON.Slave_Visibility floatLogic1.floatA;
                #connectAttr -f floatLogic1.outBool l_feather_03_01_CON.visibility;

            parent = obj.getParent()
            
            inheritTranslation = False

            if (len(SpaceSwitcherJoints) > 0):
                perjointListpaceSwitcherJoints = list(SpaceSwitcherJoints)
                if (parent not in perjointListpaceSwitcherJoints):
                    perjointListpaceSwitcherJoints.insert(0, parent)
                elif(len(perjointListpaceSwitcherJoints) > 1 and perjointListpaceSwitcherJoints.index(parent) > 0):
                    k = perjointListpaceSwitcherJoints
                    a, b = k.index(parent), 0
                    k[b], k[a] = k[a], k[b]

                if (len(perjointListpaceSwitcherJoints) > 0):
                    if not inheritTranslation:
                        util.setupSpaceSwitch(pm.PyNode(ctrl), 
                                              perjointListpaceSwitcherJoints, 
                                              nameDetailLevel=3, 
                                              inheritParentLevel=2, 
                                              fk=True,
                                              spaceBlends=spaceBlends[i])
                    else:
                        util.setupSpaceSwitch(pm.PyNode(ctrl), 
                                              perjointListpaceSwitcherJoints, 
                                              nameDetailLevel=3, 
                                              inheritParentLevel=2,
                                              spaceBlends=spaceBlends[i])
            else:  #Constrain inherit to parent joint
                if (objparent is not None): 
                    pm.orientConstraint(objparent, inherit, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
                    pm.pointConstraint(objparent, inherit, mo=True, weight= 1)

            lockandhide(inherit, 0)
            util.lockAndHideAttributes(ctrl, hideScale=not affectScale) # ethanm - dont lock/hide scale if it needs to scale the joint

            
            pmctrl = pm.PyNode(ctrl)
            allControls.append(pmctrl)
            
            # ethanm - connect control scale to target joint scale if affectScale
            if affectScale:
                # ethanm - disconnecting first
                expObj = util.getExportJoint(obj)
                for a in ['s', 'sx', 'sy', 'sz']:
                    attr = '{}.{}'.format(expObj, a)
                    check = pm.connectionInfo(attr, sfd=True)
                    if check:
                        pm.disconnectAttr(check, attr)

                #print('Scale {}.scale -> {}.scale'.format(ctrl, expObj))
                pm.connectAttr('{}.scale'.format(ctrl), '{}.scale'.format(expObj))


             # ethanm - now only making simple fk controls for child joints below the end of master joints
            """Rig child joints as FK"""
            if rigChildJoints and (not masterChildren or not useMasterChildJoints):
                childJoints = obj.listRelatives( ad=True, type='joint' )
                fkGrps, fkControls = mb_MakeSimpleFKControl.mb_makeSimpleFKControl(joints=childJoints, 
                                                                                   conScale=conScale * 0.75,
                                                                                   SpaceSwitcherJoints=SpaceSwitcherJoints,
                                                                                   createSet=False,
                                                                                   spaceBlends=spaceBlends)
                allControls.extend(fkControls)
                pm.parent(fkGrps, mainGrp)


    grpNodes.append(mainGrp)
    allControls.append(visctrl)
    #Create Sets
    
    
    # ethanm - making sure set get masterlist side prefix
    # switching membrane for feather if membrane
    fcSet = pm.sets(allControls, 
                    name=matchPrefix(setName+'_{}_ctrl_set'.format('feather' if not membrane else 'membrane'), masterList))
    if group:
        util.addToSet(fcSet, group.name() + '_set')

    util.connectMessage(networkNode, 'controls', allControls)
    connect_chain = [x.name().split('_RigJnt')[0] for x in jointListTotal]
    util.connectMessage(networkNode, 'joints', connect_chain)

    
    return grpNodes, allControls, jointListTotal


# ethanm - making sure set get side prefix
def matchPrefix(setName, masterList):
    '''Force matching prefix name to masterlist, so it groups better in sets'''
    
    current_side = util.getPrefixSide(setName) or 0
    master_side_set = [x for x in set(map(util.getPrefixSide, masterList)) if x]
    master_side = 0
    if len(master_side_set) == 1:
        master_side = master_side_set[0]

    if current_side != master_side:
        sides_regex = {0:'^c_',1:'^l_',-1:'^r_',}
        setName = '{}{}'.format(sides_regex[master_side][1:], re.sub(sides_regex[current_side], '', setName, re.IGNORECASE))

    return util.getNiceControllerName(setName)



def makeVisControl(group, startctrl, rigModuleName, conScale):
    moduleName = rigModuleName.replace("_RigJnt", "")
    #namePrefix = util.getSidePrefixString(startctrl)

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
                       , n=moduleName + "_MainCON"
                       )

    spans = visctrl.getAttr("spans")
    cmds.select(visctrl.longName() + ".cv[0:" + str(spans) + "]", r=True)
    pm.scale(conScale * 0.6, conScale * 0.6, conScale * 0.6, r=True)

    a = startctrl.getAttr('worldMatrix')
    A = pymeldt.Vector(a[1][0:3])       #Get Y Vector
    if A.dot(pymeldt.Vector(0,1,0)) < 0.0:  #pointing downwards, so flip it
        cmds.rotate(180, 0, 0, os=True)

    #cmds.rotate(90, 0, 90, os=True)

    worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    if worldUpAxis == 'Z':
        pm.rotate(0, 90, 0, os=True)

    inherit = "VisCON_" + startctrl.name() + "INH"
    inherit = pm.group(em=True, name=str(inherit) )
    pm.parent(inherit, group, r=True)
    pm.orientConstraint(startctrl, inherit, mo=True, weight= 1).setAttr('interpType', util.DEFAULT_INTERPTYPE)
    pm.pointConstraint(startctrl, inherit, mo=True, weight= 1)
    lockandhide(inherit, 0)

    """Create VisCON Group node to zero transforms"""
    grpNode = pm.group(em=True, n=str(visctrl) + "Grp")
    pm.parent(grpNode, inherit, r=True)
    """Parent vis control to group"""
    pm.parent(visctrl, startctrl, r=True)
    pm.parent(visctrl, grpNode)
    lockandhide(visctrl, 0, 0)
    """Add visibility attributes"""
    pm.addAttr(visctrl, ln="Slave_Visibility", at="bool", min=0, max=1, defaultValue=1, k=0)
    visctrl.setAttr("visibility", keyable=False, cb=True)
    visctrl.setAttr("Slave_Visibility", keyable=False, cb=True)
    """ Add follow attribute"""
    pm.addAttr(visctrl, ln="Follow", at="float", min=0, max=1, defaultValue=1, k=True)

    return visctrl


#mb_makeSimpleFKControl()

