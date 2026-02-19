
import pymel.core as pm
from EvoRig import mb_rig_utilities
import ctrl

#-----------------------------------------------------------------------------#
# Simple Root Ctrl Module
#-----------------------------------------------------------------------------#


class rootCtrl(ctrl.ctrlModule):   
    '''Root Control Wrapper class''' 
    _isCtrl = True
    _label = 'Root'
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
        exportRoot = kwargs.get('exportRoot')
        self.keyword = exportRoot.name()
        hipJnt = kwargs.get('hipJnt')
        rigNetwork = kwargs.get('rigNetwork')
        
        moduleNetworkName = f'{self._label}_{self.keyword}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        ikGrp, rootControl = makeRootControl(root, exportRoot, moduleSpaceSwitchList, group, controlSize, hipJnt)
        
        mb_rig_utilities.connectMessage(networkNode, 'controls', rootControl)
        mb_rig_utilities.connectMessage(networkNode, 'joints', exportRoot)

        return ikGrp, rootControl



    
def makeRootControl(root, 
                    exportRoot, 
                    spaceSwitcherJoints, 
                    group, 
                    conScale, 
                    hipJnt):
    
        # Set up space switchers
        localSpaceSwitcherJoints = spaceSwitcherJoints[0:3]

        rootMotionJnt = pm.joint(root, name='rootmotion_RigJnt')
        translationconnections = pm.listConnections(exportRoot.name() + ".tx", d=False, s=True)
        for i in translationconnections:
            pm.delete(i)
        rotationconnnections = pm.listConnections(exportRoot.name() + ".rx", d=False, s=True)
        for i in rotationconnnections:
            pm.delete(i)

        pm.parentConstraint(rootMotionJnt, exportRoot, mo=True)

        groundPlaneControl = None
        jointXform = pm.xform(root, q=True, ws=True, rp=True)
        groundPlaneTarget = pm.createNode('transform', n=root.name() + '_groundPlane' + '_Target')
        pm.xform(groundPlaneTarget, ws=True, t=jointXform)
        pm.setAttr(groundPlaneTarget.name() + '.translate' + pm.upAxis(q=True, axis=True).upper(), 0)

        groundPlaneAdjustGrp = pm.group(groundPlaneTarget, name=mb_rig_utilities.getNiceControllerName(groundPlaneTarget.name()).replace("_Target", ""))
        if group:
            pm.parent(groundPlaneAdjustGrp, group)

        groundPlanePreProjection = pm.createNode('transform', n=root.name() + '_groundPlanePreProjection', parent=root)
        pm.parent(groundPlanePreProjection, groundPlaneAdjustGrp)

        groundPlaneControl = mb_rig_utilities.getGroundPlaneControl(root, group, conScale)

        pm.parentConstraint(groundPlaneControl, groundPlaneAdjustGrp, mo=True)

        # Parent constrain node to joint so it stays centered when rotating
        pm.pointConstraint(hipJnt, groundPlanePreProjection, mo=True)
        # Point constrain the groundPlaneTarget, which is located on the ground plane. Skip the up-Axis
        pm.pointConstraint(groundPlanePreProjection, groundPlaneTarget, mo=True, skip=pm.upAxis(q=True, axis=True).lower())

        rootControl, ikGrp = mb_rig_utilities.makeControl(rootMotionJnt, conScale, constrainObj=rootMotionJnt, worldOrient=True, shape=12,
                                              controlSuffix='_CON')  # parentObj=joint
        pm.parent(ikGrp, group)
        mb_rig_utilities.setRGBColor(rootControl, color=(1.0, 0.0, 0.5))

        mb_rig_utilities.setupSpaceSwitch(rootControl,
                              localSpaceSwitcherJoints,
                              nameDetailLevel=4,
                              nameDetailStart=0,
                              spaceBlends=None)
        rootControl.setAttr("space", 2)
        # scale constrraint to all the spaces so the control moves when using size attribute on c_Main_CON
        rootControl_inh = rootControl.getParent().getParent()
        rootControlScaleCns = pm.scaleConstraint(localSpaceSwitcherJoints, rootControl_inh, mo=True)
        rootControlScaleCns_weightAliases = rootControlScaleCns.getWeightAliasList()
        for i, jnt in enumerate(localSpaceSwitcherJoints):
            conditionNode = pm.shadingNode('condition', asUtility=True)
            conditionNode.setAttr("secondTerm", i)
            conditionNode.setAttr("colorIfTrueR", 1)
            conditionNode.setAttr("colorIfFalseR", 0)
            pm.connectAttr(rootControl.name() + ".space", conditionNode.name() + '.firstTerm')
            pm.connectAttr(conditionNode.name() + '.outColor.outColorR', rootControlScaleCns.name() + '.' + rootControlScaleCns_weightAliases[i].attrName(longName=True))


        ikControlParent = rootControl.getParent()
        groundPlaneSwitchGrp = pm.group(rootControl, n=rootControl.name() + '_GroundPlane_Grp')
        groundPlaneConstraint = pm.parentConstraint([ikControlParent, groundPlaneTarget], groundPlaneSwitchGrp, mo=True, skipRotate=["x", "y", "z"])
        groundPlaneConstraint.setAttr('interpType', mb_rig_utilities.DEFAULT_INTERPTYPE)

        pm.addAttr(rootControl, ln='autoPosition', at='double', min=0, max=1, hidden=False, k=True, defaultValue=True)
        weightAliases = groundPlaneConstraint.getWeightAliasList()
        oneMinusNode = pm.shadingNode("plusMinusAverage", asUtility=True)
        oneMinusNode.setAttr("operation", 2)
        pm.setAttr(oneMinusNode + ".input1D[0]", 1.0)  
        pm.connectAttr(rootControl.name() + ".autoPosition", oneMinusNode + ".input1D[1]")
        pm.connectAttr(oneMinusNode.name() + ".output1D", weightAliases[0])
        pm.connectAttr(rootControl.name() + ".autoPosition", weightAliases[1])
        pm.setAttr(rootControl + ".autoPosition", 0.0) # auto Position is disabled by default

        return ikGrp, rootControl

 
def createMoveDirectionControl(exportRoot, group, conScale):

    moveDirectionJoint = pm.joint(exportRoot, name="movedirection_ik")
    moveDirectionChildJoint = pm.joint(moveDirectionJoint, name="movedirection_child_ik")
    pm.xform(moveDirectionChildJoint, t=(0, 0, 4 * conScale))
    moveDirectionControl, moveDirectionControlGrp = mb_rig_utilities.makeControl(moveDirectionJoint,
                                                                        conScale * 2.0,
                                                                        constrainObj=moveDirectionJoint,
                                                                        pivotObj=group,
                                                                        worldOrient=True,
                                                                        shape=9,
                                                                        controlSuffix='_EngineIKCON',
                                                                        ctrlName='MoveDirection_EngineIKCON',
                                                                        forwardAxis=pm.upAxis(q=True, axis=True).upper())

    if group:
        pm.parent(moveDirectionControlGrp, group)

    pm.select(moveDirectionControl.name() + ".cv[1:2]", r=True)
    pm.scale([0.4, 1, 1], r=True)

    return moveDirectionControl
