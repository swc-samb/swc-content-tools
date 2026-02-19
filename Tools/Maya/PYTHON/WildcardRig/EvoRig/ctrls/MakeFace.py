#

import os
import sys
import json

import ast 
from math import *

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

from wildcardUtils.systemUtils import reload
import ctrl; reload(ctrl);
from wildcardRig.FaceRig import build_face; reload(build_face)
from EvoRig import mb_rig_utilities

__author__ = 'Isabelle Richter'
__version__ = '1.0.0'

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload 

if sys.version_info.major >= 3.12:    
    unicode = str

# -----------------------------------------------------------------------------#
# Face Ctrl Module
# -----------------------------------------------------------------------------#

class faceCtrl(ctrl.ctrlModule):
    '''Face ctrl class'''
    _isCtrl = True
    _label = 'Face'
    _color = (0.6, 0.4, 0.6)

    def __init__(self, *args, **kwargs):
        self._nodeAttributes = {}
        self._uv_data = None
        self.data_path = None
        self.mesh = None
        self.tongue_mesh = None
        self.right_eye_dict = None
        self.left_eye_dict = None
        self.jaw_dict = None
        self.gui_path = None
        type(self).__bases__[0].__init__(self, *args, **kwargs)

    def _on_dataTextField_text_changed(self, text):
        if text:
            self.data_path = os.path.normpath(text)
            if os.path.exists(self.data_path):
                with open(self.data_path, "r") as f:
                    self._uv_data = json.load(f)    

    def _on_headMeshTextField_text_changed(self, text):
        if text:
            self.mesh = text

    def _on_teethMeshTextField_text_changed(self, text):
        if text:
            self.tongue_mesh = text

    def _on_rEyeDictTextField_text_changed(self, text):
        if text:
            self.right_eye_dict = text
    def _on_lEyeDictTextField_text_changed(self, text):
        if text:
            self.left_eye_dict = text

    def _on_jawDictTextField_text_changed(self, text):
        if text:
            self.jaw_dict = text

    def _on_guiPathTextField_text_changed(self, text):
        if text:
            self.gui_path = os.path.normpath(text)

    def findAndCreate(self,
                      root,
                      moduleSpaceSwitchList=None,
                      group=None,
                      controlSize=1.0,
                      mainCtrl=None,
                      **kwargs):
        
        self.import_gui()
        rigNetwork = kwargs.get('rigNetwork')
        displayModuleName = mb_rig_utilities.getMayaSafeName(self._label)
        moduleNetworkName = f'{displayModuleName}_{self.keyword}_Network' if self.keyword else f'{displayModuleName}_{self.getTitle()}_Network'
        networkNode = self.getNetworkNode(rigNetwork, moduleNetworkName)
        self.moduleToNetwork(networkNode=networkNode)

        face_rig_ctrls = [x for x in pm.ls(type=pm.nt.Transform) if x.hasAttr('faceCtrl')]
        for face_ctrl in face_rig_ctrls:
            for attr_name in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
                attr = pm.PyNode(f'{face_ctrl}.{attr_name}')
                if attr.isKeyable() and not attr.isLocked() and not attr.isConnected():
                    attr.set(0)
        mb_rig_utilities.connectMessage(networkNode, 'controls', face_rig_ctrls)

        rivets = self.create_uv_pins()
        mb_rig_utilities.connectMessage(networkNode, 'rivets', rivets)
        mb_rig_utilities.connectMessage(networkNode, 'joints', [str(x) for x in self._uv_data.keys()])
       
        with open(r"T:\Tools\Maya\PYTHON\wildcardRig\FaceRig\MetaFaceEditor\face_pose_data.json", "r") as f:
            pose_data = json.load(f)
        self.connect_controls(pose_data, networkNode)

        head_bshape = f'{self.mesh}_blendShape'
        tongue_bshape = f'{self.tongue_mesh}_blendShape'
        build_face.connect_matching_blendshape_targets(pm.PyNode(f'{tongue_bshape}'), pm.PyNode('CTRL_expressions'))
        build_face.connect_matching_blendshape_targets(pm.PyNode(f'{head_bshape}'), pm.PyNode('CTRL_expressions'))
        build_face.connect_root(pose_data)

    def initDynamicLayoutParameters(self, moduleLayout, ignoreList = None, *args, **kwargs):
        super(type(self), self).initDynamicLayoutParameters(moduleLayout, ignoreList = [])

        self.dataButton = pm.button("databutton" + str(self._index), 
                                label='UV Data >',
                                command=self._on_dataButton_clicked,
                                parent=moduleLayout)
        if self.data_path:
            set_path = self.data_path[0] if not isinstance(self.data_path, str) else self.data_path
        else:
            set_path = ''

        self.dataTextField = pm.textField('dataTextField'+ str(self._index), 
                                    text=set_path, 
                                    editable=True, 
                                    textChangedCommand=self._on_dataTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        self.headMeshButton = pm.button("headMeshButton" + str(self._index), 
                                label='Head Mesh >',
                                command=self._on_headMeshButton_clicked,
                                parent=moduleLayout)
        self.headMeshTextField = pm.textField('headMeshTextField'+ str(self._index), 
                                    text=self.mesh, 
                                    editable=True, 
                                    textChangedCommand=self._on_headMeshTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        self.teethMeshButton = pm.button("teethMeshButton" + str(self._index), 
                                label='Teeth Mesh >',
                                command=self._on_teethMeshButton_clicked,
                                parent=moduleLayout)
        self.teethMeshTextField = pm.textField('teethMeshTextField'+ str(self._index), 
                                    text=self.tongue_mesh, 
                                    editable=True, 
                                    textChangedCommand=self._on_teethMeshTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        self.guiPathButton = pm.button("guiPathButton" + str(self._index), 
                                label='Face GUI >',
                                command=self._on_guiPathButton_clicked,
                                parent=moduleLayout)
        self.guiPathTextField = pm.textField('guiPathTextField'+ str(self._index), 
                                    text=self.gui_path, 
                                    editable=True, 
                                    textChangedCommand=self._on_guiPathTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        self.sdkDictButton = pm.button("sdkDictButton" + str(self._index), 
                                label='SDK Dicts >',
                                command=self._on_sdkDictButton_clicked,
                                parent=moduleLayout)
        pm.text(label='Get jaw and eye SDK values from MH', parent=moduleLayout)
        pm.text(label='Right Eye', parent=moduleLayout)
        self.rEyeDictTextField = pm.textField('rEyeDictTextField'+ str(self._index), 
                                    text=str(self.right_eye_dict), 
                                    editable=True, 
                                    textChangedCommand=self._on_rEyeDictTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        pm.text(label='Left Eye', parent=moduleLayout)
        self.lEyeDictTextField = pm.textField('lEyeDictTextField'+ str(self._index), 
                                    text=str(self.left_eye_dict), 
                                    editable=True, 
                                    textChangedCommand=self._on_lEyeDictTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        pm.text(label='Jaw', parent=moduleLayout)
        self.jawDictTextField = pm.textField('jawDictTextField'+ str(self._index), 
                                    text=str(self.jaw_dict), 
                                    editable=True, 
                                    textChangedCommand=self._on_jawDictTextField_text_changed, 
                                    annotation='',
                                    parent=moduleLayout)
        
        self._on_dataTextField_text_changed(set_path)
        self._on_lEyeDictTextField_text_changed(self.left_eye_dict)
        self._on_rEyeDictTextField_text_changed(self.right_eye_dict)

    def _on_headMeshButton_clicked(self, *args):
        """
        Sets head mesh line edit to currently selected mesh name

        """
        
        head_mesh = pm.selected()
        if head_mesh:
            mesh_name = head_mesh[0].name()
            pm.textField(self.headMeshTextField, e=True, text=mesh_name)
            self._on_headMeshTextField_text_changed(mesh_name)

    def _on_teethMeshButton_clicked(self, *args):
        """
        Sets teeth mesh line edit to currently selected mesh name

        """
        
        teeth_mesh = pm.selected()
        if teeth_mesh:
            mesh_name = teeth_mesh[0].name()
            pm.textField(self.teethMeshTextField, e=True, text=mesh_name)
            self._on_teethMeshTextField_text_changed(mesh_name)

    def _on_dataButton_clicked(self, *args):
        """
        Opens file dialog prompts user to select face UV data json file
        
        """
        
        file_path = cmds.fileDialog2(
        fileMode=1,                 
        caption="Select Rig Data File",
        fileFilter="JSON Files (*.json)")

        if file_path:
            selected_file = file_path[0]
            pm.textField(self.dataTextField, e=True, text=selected_file)
            self._on_dataTextField_text_changed(selected_file)
    
    def _on_guiPathButton_clicked(self, *args):
        """
        Opens file dialog prompts user to select face GUI maya scene
        
        """
        
        file_path = cmds.fileDialog2(
        fileMode=1,                 
        caption="Select Face GUI",
        fileFilter="Maya Files (*.ma *.mb)")

        if file_path:
            selected_file = file_path[0]
            pm.textField(self.guiPathTextField, e=True, text=selected_file)
            self._on_guiPathTextField_text_changed(selected_file)
    
    def _on_sdkDictButton_clicked(self, *args):
        """
        Sets joint movement SDK dicts for eyes and jaw based off MH rig in scene

        """
        
        if not pm.objExists('head_rl4Embedded'):
            pm.warning('You need to be in the scene with the original Metahuman rigged')
            return
        jnt_movement_dict = build_face.get_mh_jnt_movement()

        r_eye = jnt_movement_dict.get('r_eye')
        l_eye = jnt_movement_dict.get('l_eye')
        jaw = jnt_movement_dict.get('jaw')
        
        pm.textField(self.rEyeDictTextField, e=True, text=str(r_eye))
        pm.textField(self.lEyeDictTextField, e=True, text=str(l_eye))
        pm.textField(self.jawDictTextField, e=True, text=str(jaw))

        self._on_rEyeDictTextField_text_changed(str(r_eye))
        self._on_lEyeDictTextField_text_changed(str(l_eye))
        self._on_jawDictTextField_text_changed(str(jaw))

    def get_ctrls(self):
        """
        Selects face controls 

        """
        
        return([x for x in pm.ls(type=pm.nt.Transform) if x.hasAttr('faceCtrl')])
    

    def import_gui(self):
        """
        Imports face GUI

        """
        
        if self.gui_path:
            cmds.file(
                self.gui_path,
                i=True,
                namespace=":",
                mergeNamespacesOnClash=True)
    
    def create_uv_pins(self):
        """
        Creates the UV pins based off data from JSON file that drive facial joints

        """
        rivets = []
        for jnt, uv in self._uv_data.items():
            if pm.objExists(jnt):
                jnt = f'{jnt}_RigJnt'
                if 'tongue' in jnt.lower() or 'teeth' in jnt.lower():
                    rivet = list(build_face.connect_rivet(self.tongue_mesh, 
                                                          f'{jnt}_loc', 
                                                          uv, 
                                                          uv_pin_name=f'{jnt}_pin', 
                                                          locator_scale=0.2).keys())[0]
                    if 'upper' in jnt.lower():   
                        pm.pointConstraint(rivet, jnt, mo=True)
                    else:
                        pm.parentConstraint(rivet, jnt, mo=True)
                else:
                    rivet = list(build_face.connect_rivet(self.mesh, 
                                                          f'{jnt}_loc', 
                                                          uv, 
                                                          uv_pin_name=f'{jnt}_pin', 
                                                          locator_scale=0.2).keys())[0]
                    if 'Lip' in jnt:
                        pm.parentConstraint(rivet, jnt, mo=True)
                    else:        
                        pm.pointConstraint(rivet, jnt, mo=True)
                rivets.append(rivet)
        return rivets

    def connect_controls(self, pose_data, network_node):
        """
        Connects controls to shapes and sets up eye and jaw additive SDKs

        :param dict pose_data: Information about poses and controls 

        """
        math_nodes = []
        if not self.left_eye_dict:
            self.left_eye_dict = pm.textField(self.lEyeDictTextField, q=True, text=True)
        if not self.right_eye_dict:
            self.right_eye_dict = pm.textField(self.rEyeDictTextField, q=True, text=True)
        head_bshape = f'{self.mesh}_blendShape'
        tongue_bshape = f'{self.tongue_mesh}_blendShape'

        # Ensure we can make connections as needed to blendshape (might not need this)
        weights = cmds.listAttr(head_bshape + '.w', m=True)  
        if weights:
            for weight in weights:
                full_attr = f"{head_bshape}.{weight}"
                conns = cmds.listConnections(full_attr, s=True, d=False, p=True)
                if conns:
                    for conn in conns:
                        cmds.disconnectAttr(conn, full_attr)
                                        
        # Connect controls to blendshape
        issues = []
        for pose, data in pose_data.items():
            if 'jaw' in pose and 'Chin' not in pose and 'Clench' not in pose:
                bshapes = [head_bshape, tongue_bshape]
            elif 'tongue' in pose:
                bshapes = [tongue_bshape]
            elif 'teeth' in pose and 'lip' not in pose.lower():
                bshapes = [tongue_bshape]
            else:
                bshapes = [head_bshape]
            for bshape in bshapes:
                control = data.get("control")
                attr = data.get("attr")
                clamp = data.get('clamp')
                invert = True if data.get("val") < 1 else False
                do_con = True if 'eyeLook' not in pose else False
                w_attr_name = pose
                try:
                    if clamp:
                            clamp_node = build_face.connect_control_to_blendshape_clamped(control, attr, bshape, f'{w_attr_name}', invert=invert, do_con=do_con)
                            math_nodes.append(clamp_node)
                    else:
                        pm.connectAttr(f'{control}.{attr}', f'{bshape}.{w_attr_name}', force=True)
                except Exception as e:
                    issues.append(e)
        
        # Set up additive eye look direction SDKs/switching with eye aim
        center_eye_control = pm.PyNode('CTRL_C_eye')
        sides = ['L', 'R']
        for side in sides:
            if side == 'L':
                if isinstance(self.left_eye_dict, str):
                    eye_dict = ast.literal_eval(self.left_eye_dict)
                else:
                    eye_dict = self.left_eye_dict
            else:
                if isinstance(self.right_eye_dict, str):
                    eye_dict = ast.literal_eval(self.right_eye_dict)
                else:
                    eye_dict = self.right_eye_dict


            poses = [f'eyeLookRight{side}', f'eyeLookLeft{side}', f'eyeLookUp{side}', f'eyeLookDown{side}']
            control = pm.PyNode(f'CTRL_{side}_eye')
            joint = f'FACIAL_{side}_Eye_RigJnt'

            for pose in poses:
                pose_info = pose_data.get(pose)
                attr = pose_info.get("attr")
                clamp = pose_info.get('clamp')
                invert = True if pose_info.get("val") < 1 else False
                adl_node = pm.createNode('addDoubleLinear', name=f'adl_{pose}')
                math_nodes.append(adl_node)

                if not clamp:
                    pm.connectAttr(f'{control}.{attr}', adl_node.input1, force=True)
                    pm.connectAttr(f'{center_eye_control}.{attr}', adl_node.input2, force=True)
                else:
                    clamp_node = pm.PyNode(f"{control}_{pose}_clamp")
                    pm.connectAttr(clamp_node.outputR, adl_node.input1, force=True)
                    new_clamp = build_face.connect_control_to_blendshape_clamped(center_eye_control, 
                                                                                 attr, 
                                                                                 head_bshape, 
                                                                                 f'{pose}', invert=invert, do_con=False)

                    pm.connectAttr(f'{new_clamp}.outputR', adl_node.input2, force=True)
                    math_nodes.append(new_clamp)



                clamp_node = pm.createNode('clamp', name=f"{center_eye_control}_{pose}_final_clamp")
                math_nodes.append(clamp_node)
                clamp_node.minR.set(0)
                clamp_node.maxR.set(1)  
                pm.connectAttr(adl_node.output, clamp_node.inputR, force=True)  

                if 'Up' in pose or 'Down' in pose:
                    max_angle = eye_dict.get(f'{pose}Shape').get('rx')
                    attr = 'rx'
                else:
                    max_angle = eye_dict.get(f'{pose}Shape').get('ry')
                    attr = 'ry'

                remap = build_face.make_eye(pose, joint, max_angle=max_angle, attr=attr)    
                bc = pm.createNode('blendColors', name=f'{pose}_BC')
                math_nodes += [remap, bc]
                pm.connectAttr(f'{remap}.outValue', f'{bc}.color1.color1R', force=True)
                pm.connectAttr(clamp_node.outputR,f'{bc}.color2.color2R', force=True)
                pm.connectAttr(f'{bc}.output.outputR', f'{self.mesh}_blendShape.{pose}', force=True)
                pm.connectAttr(f'CTRL_lookAtSwitch.translate.translateY', f'{bc}.blender', force=True)
                
                build_face.setup_control_additive_sdk(
                    pose_map=pose_data,
                    pose_rotations=eye_dict,
                    driven_joint=pm.PyNode(f'LOC_{side}_eyeUIDriver'),
                    attrs=["rx", "ry"],
                    helper_node_name=f"{pose}_eye_sdkHelper"
                    ) 

            pm.orientConstraint(f'LOC_{side}_eyeDriver', f'FACIAL_{side}_Eye_RigJnt', mo=True)
            driver_con = pm.PyNode(f'LOC_{side}_eyeDriver_orientConstraint1')
            pm.connectAttr(f'CTRL_lookAtSwitch.ty', f'{driver_con}.target[0].targetWeight', force=True)

            sub_node = pm.createNode('subtract', name=f'{driver_con}_sub')
            sub_node.input1.set(1)
            pm.connectAttr('CTRL_lookAtSwitch.translateY', f'{sub_node}.input2', force=True)
            pm.connectAttr(f'{sub_node}.output',  f'{driver_con}.target[1].targetWeight', force=True)
            pm.connectAttr('CTRL_lookAtSwitch.translateY', f'GRP_C_eyesAim.v', force=True)

        #Turn off eyeball eye look dir when full blink on head shape but keep eyeball curves 
        eye_look_bcs = pm.ls(f'eyeLook*_BC')
        math_nodes += eye_look_bcs

        for elbc in eye_look_bcs:
            abs_node = pm.createNode('absolute', name=f'{elbc}_abs')
            sub_node = pm.createNode('subtract', name=f'{elbc}_sub')
            side = elbc.name().split('_BC')[0][-1]
            eye_ctrl = f'CTRL_{side}_eye_blink'
            remap = pm.createNode('remapValue', name=f'{elbc}_remap')
            math_nodes.append(remap)
            pm.connectAttr(f'{eye_ctrl}.translate.translateY',f'{abs_node}.input', force=True)
            pm.connectAttr(f'{abs_node}.output', f'{sub_node}.input2', force=True)
            pm.connectAttr(f'{elbc}.output.outputR', f'{sub_node}.input1', force=True)
            pm.connectAttr(f'{sub_node}.output', f'{remap}.inputValue', force=True)

            shape_name = f"{elbc.name().split('_BC')[0]}"
            pm.connectAttr(f'{remap}.outValue', f'{head_bshape}.{shape_name}', force=True)
            root_jnt = pm.PyNode('ROOT_JNT_SKL')
            eye_ball_attr = f'eyeball_{shape_name}'

            if not root_jnt.hasAttr(eye_ball_attr):
                root_jnt.addAttr(eye_ball_attr, attributeType='float', defaultValue=0.0, keyable=True)

            pm.connectAttr(f'{elbc}.output.outputR', f'{root_jnt.name()}.{eye_ball_attr}', force=True)

        # Set up jaw         
        build_face.build_jaw(driver_node=pm.PyNode(tongue_bshape),driven_node=pm.PyNode('FACIAL_C_Jaw'),
            pose_data=ast.literal_eval(self.jaw_dict),
            attrs=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
            helper_node_name='c_jaw_SDK_ctrl')
        mb_rig_utilities.connectMessage(network_node, 'faceNodes', math_nodes)

    def finish_face_assembly(self, rig_name):
        """
        Cleans up rig scene, sets up face/eye GUI follow head, makes GUI camera, ensures consistent vis of controls

        :param str rig_name: Name of the rig (used for parenting objects under rig group)

        """
        
        for ctrl in [pm.PyNode('CTRL_C_eyesAim'), pm.PyNode('CTRL_faceGUI')]:
            ctrl_grp = ctrl.getParent()
            con = pm.parentConstraint('Cnt_Head_JNT_SKL', ctrl_grp, mo=True)
            switch = pm.PyNode('CTRL_eyesAimFollowHead') if ctrl.name() == 'CTRL_C_eyesAim' else pm.PyNode('CTRL_faceGUIfollowHead')
            pm.connectAttr(f'{switch}.translate.translateY', f'{con}.Cnt_Head_JNT_SKLW2', force=True)
            sub_node = pm.createNode('subtract', n=f'{switch}_sub')
            sub_node.input1.set(1)
            pm.connectAttr(f'{switch}.translate.translateY', f'{sub_node}.input2', force=True)
            pm.connectAttr(f'{sub_node}.output', f'{con}.LOC_worldW1', force=True)    
        pm.parentConstraint('FACIAL_C_FacialRoot', 'LOC_C_eyeDriver', mo=True)
        main_face_grp = pm.PyNode('rig')
        if not main_face_grp.hasAttr('mainFaceGrp'):
            main_face_grp.addAttr('mainFaceGrp', attributeType='bool')
        helpers_grp = pm.PyNode('sdkHelpers')
        if not helpers_grp.hasAttr('helpersGrp'):
            helpers_grp.addAttr('helpersGrp', attributeType='bool')
        pin_grp = pm.PyNode('uvPins')
        if not helpers_grp.hasAttr('pinsGrp'):
            helpers_grp.addAttr('pinsGrp', attributeType='bool')
        for grp in [helpers_grp, pin_grp]:
            grp.setParent('rig')
            grp.v.set(0)
        pm.parent(main_face_grp, rig_name)

        cam = pm.camera(name=f'{rig_name}_GUI_cam')[0]
        cam.tx.set(24.795)
        cam.ty.set(172.232)
        cam.tz.set(50.24)
        cam.focalLength.set(50)
        con = pm.parentConstraint('CTRL_faceGUI', cam, mo=True)
        cam.setParent(rig_name)
        cam.v.set(0)
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            attr_node = pm.PyNode(f'{cam.name()}.{attr}')
            attr_node.setLocked(1)
            attr_node.setKeyable(0)
        
        members = self.get_ctrls()
        pm.editDisplayLayerMembers('Controls', members)

        