# Script for switching and baking animation from IK to FK and vice versa 

import pymel.core as pm
import maya.cmds as cmds
from wildcardUtils import mayaUtils

ATTR_LST = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']

def ikfk_switch_cmd():
    """
    Command to do the switch.

    """

    # Set a namespace to do things so we can easily purge the whole thing later to keep scene clean 
    namespace_name = 'TEMP_IKFK_SWITCH_NS'
    ATTR_LST = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
    selected_objs = pm.selected()

    if not selected_objs:
        pm.warning('Please select one control from each component to switch.')
        return
    control_list = [x for x in selected_objs if isinstance(x, pm.nt.Transform)]
    
    # Get namespace
    rig_name_pieces = control_list[0].name().split(':')
    if len(rig_name_pieces) == 1:
        rig_namespace = ''
    else:
        rig_namespace = control_list[0].name().split(':')[0]

    # Get time range from controls for baking 
    all_cons = pm.ls(f'{rig_namespace}:*CON', type=pm.nt.Transform)
    time_range = mayaUtils.get_time_range_from_node_list(all_cons)
    if time_range == (None, None):
        time_range = (0,0)
    start_frame = time_range[0]
    end_frame = time_range[1]
    
    # Remove auto key to do things but remember the state to set it back so we don't ruin animators day 
    autokey_state = cmds.autoKeyframe(query=True, state=True)
    pm.autoKeyframe(state=False)
    cur_time = pm.currentTime(q=True)
    pm.currentTime(-3000)

    for control in control_list:
        control_name = control.name()
        active_lyr = None
        lyrs = list(set(control.listConnections(type=pm.nt.AnimLayer)))
        for lyr in lyrs:
            if pm.animLayer(lyr, q=True, sel=True):
                active_lyr = lyr 
                break
        print_lyr = active_lyr if active_lyr else 'BaseAnimation'
        pm.warning(f'Selected animation layer for {control_name} is {print_lyr}')

        # Getting names to identify other parts of the rig. 
        control_parent = find_master_group(control_name)
       
        region_name = control_name.split('_CON')[0]
        region_name_clean = region_name.split(region_name[-3:])[0]
        side = region_name.split(':')[-1][0]
        
        # Get switch control
        switch_con = f'{region_name_clean}_ik_switch_CON'
        if pm.objExists(switch_con):
            switch_con = pm.PyNode(switch_con)
        else:
            pm.warning(f'switch con with expected name {switch_con} not found (try selecting wrist/foot control)')
            ikfk_switch_scene_cleanup(namespace_name, autokey_state)
            return
            
        switch_setting = switch_con.SwitchIkFk.get()
        
        # Janky way to identify controls 
        fk_masters = [x for x in cmds.listRelatives(control_parent, c=True) if 'fkMaster' in x]
        fk_controls = []
        for fk_master in fk_masters:
            fk_control = [x for x in cmds.listRelatives(fk_master, ad=True) if pm.objExists(f'{x}Shape')]
            if fk_control:
                fk_controls.append(fk_control[0])
        component_master = cmds.listRelatives(fk_masters[0], p=True)[0]
        first_jnt_type_name = component_master.split(f'{rig_namespace}:{side}_')[-1].split('MasterGrp')[0]
        expected_limbs = [x.split(':')[-1].split('_fk_CON')[0] for x in fk_controls]
    
        og_ikfk_con_list = []
        con_list = []

        # Flip the switch con
        pm.setKeyframe(switch_con, t=start_frame)
        is_ik = True if not switch_setting else False
        pm.cutKey(switch_con)
        switch_con.SwitchIkFk.set(not switch_setting)
        pm.setKeyframe(switch_con, t=end_frame)
    
        # Set our temp namespace
        if not pm.namespace(exists=namespace_name):
            pm.namespace(addNamespace=namespace_name)
        pm.namespace(set=namespace_name)

         
        # Con list are the new state controls. OG = original controls. Constrain controls to IK joints 
        if is_ik:
            con_list += fk_controls
            ik_joint_list = [pm.PyNode(f'{rig_namespace}:{x}_RigJnt_ik') for x in expected_limbs]
            for fk_con, ik_joint_node in list(zip(fk_controls, ik_joint_list)):
                pm.cutKey(fk_con)
                pm.parentConstraint(ik_joint_node, fk_con, mo=False)
            og_ikfk_con_list += [control_name, f'{region_name_clean}_PV_CON']
    
           
        else:
            pv_ctrls = cmds.ls(f'{rig_namespace}:*_PV_CON', type='transform')
            pv_con = None
            for node in cmds.listRelatives(component_master, ad=True):
                if node in pv_ctrls:
                    pv_con = node
                    break
            if not pv_con:
                pm.warning('Could not find PV control')
                ikfk_switch_scene_cleanup(namespace_name, autokey_state)
                return
            
            # Some leg setups should not have the second to last joint considered for PV placement
            skip_jnt_2 = True if pv_con != f'{region_name_clean}_PV_CON' else False 
            ik_con = pm.PyNode(f'{region_name_clean}_ik_CON')
            fk_joint_list = [pm.PyNode(f'{rig_namespace}:{x}_RigJnt_fk') for x in expected_limbs]

            og_ikfk_con_list += [pm.PyNode(f'{rig_namespace}:{x}_fk_CON') for x in expected_limbs]

            mid_jnts = []
            # Identify first fk using name of master group
            first_fk = None
            orient_ik = None
            orient_jnt = None

            last_fk = f'{region_name_clean}_RigJnt_fk'
            for fk_jnt in fk_joint_list:
                if pm.objExists(fk_jnt.name().replace('_RigJnt_fk', '_orient_CON')):
                    orient_jnt = fk_jnt
                    orient_ik = orient_jnt.replace('_RigJnt_fk', '_orient_CON')

            for jnt in [x.name() for x in fk_joint_list]:
                if first_jnt_type_name in jnt:
                    first_fk = jnt
                elif jnt != last_fk:
                    if jnt == orient_jnt:
                    # Human foot setup is a bit different and toe orient seems to be active all the time 
                    # Not sure if that is bug or intended but baking the out jnt anim onto a locator prevents cycle issue
                        substr = '' if not 'Human' in rig_namespace else '_JNT_SKL'
                        # Getting export or out joint to get anim for simplicity
                        export_toe = find_export_joint(orient_ik, substring=substr)
                        toe_loc = pm.spaceLocator()
                        toe_con = pm.parentConstraint(export_toe, toe_loc, mo=False)

                        # TODO iRichter: baking twice takes too long should really just disable the above constraint or something 
                        mayaUtils.bake_nodes([toe_loc], time_range)
                        pm.currentTime(-3000)
                        pm.delete(toe_con)
                        orient_jnt = toe_loc

                    else:
                        if not jnt == orient_jnt:
                            mid_jnts.append(jnt)

            con_list += [ik_con, pv_con, orient_ik]
            
            fk_jnt_list = [first_fk] + mid_jnts + [last_fk]
            xform_dict = {}
            
            # Set controls to 0 to be able to leash together accurately. Later set them back to current pose 
            for x in all_cons:
                xform_t = x.getTranslation()
                xform_r = x.getRotation()
                xform_dict[x] = {'t': xform_t, 'r':xform_r}
            for f in all_cons:
                for a in ATTR_LST:
                    try:
                        pm.setAttr(f'{f}.{a}', 0)
                    except Exception as e:
                        pass
            pm.parentConstraint(last_fk, ik_con, mo=True)
            if orient_ik:
                mo = True if not isinstance(orient_jnt, pm.nt.Transform) else False
                pm.orientConstraint(orient_jnt, orient_ik, mo=mo)
            
            for f, data in xform_dict.items():
              
                xform_vals = list(data.get('t')) + list(data.get('r'))
                for xform_val, xform_attr in list(zip(xform_vals, ATTR_LST)):
                    try:
                        pm.setAttr(f'{f}.{xform_attr}', xform_val)
                    except Exception as e:
                        pass
            # Need to use PyMEL to get handle because we sometimes have ik handles with the same name on a rig D: 
            ik_handle = [x for x in pm.listRelatives(component_master, c=True) if isinstance(x, pm.nt.IkHandle)]
            if not ik_handle:
                pm.warning(f'Could not find IK handle for {control}')
                ikfk_switch_scene_cleanup(namespace_name, autokey_state)
                return
            
            ik_handle = ik_handle[0]
            if skip_jnt_2:
                ik_affected_jnts = get_ik_affected_joints(ik_handle)
                if len(ik_affected_jnts) > 3:
                    ik_affected_jnts.pop(2)
            else:
                ik_affected_jnts = fk_jnt_list
            # Determine pole vector location
            pv_loc = mayaUtils.create_pole_vector_locator(ik_affected_jnts)
            pv_loc.setParent(fk_jnt_list[1])
            pm.parentConstraint(pv_loc, pv_con, mo=False)
            
            
            foot_controls = [control_name.replace('_fk_', '_'),
                            control_name.replace('_fk_', '_tip_'),
                            control_name.replace('_fk_', '_heel_'),
                            control_name.replace('_fk_', '_ball_'),
                            ik_con.replace('_ik_', ''),
                            ik_con.replace('_ik_', '_Pivot_')]
            # Just baking onto main controls instead of reverse foot for simplicity. 
            # Downside of this is that animators may prefer to use certain controls and this could potentially complicate their process.                 
            for foot_control in foot_controls:
                if cmds.objExists(foot_control):
                    pm.cutKey(foot_control)

                    for ATTR in ATTR_LST:
                        attr_node = pm.Attribute(f'{foot_control}.{ATTR}')
                        if not attr_node.isLocked() and attr_node.isKeyable():
                            attr_node.set(0)
        
        pm.namespace(set=':')    
        mayaUtils.bake_nodes(con_list, time_range=time_range, anim_lyr=active_lyr)
        print(f'baking con list {con_list} for range {time_range}')

        ikfk_switch_scene_cleanup(namespace_name, autokey_state)
        pm.currentTime(cur_time)
    
    
def find_master_group(control):
    """
    Gets master group for given control

    :param str control: Name of control to get master group of

    """
    # Start by getting the parent of the control
    parent = cmds.listRelatives(control, parent=True)
    
    # Traverse up the hierarchy
    while parent:
        if "MasterGrp" in parent[0]:
            return parent[0]
        # Move to the next parent up
        parent = cmds.listRelatives(parent[0], parent=True)
    
    # If no parent contains "MasterGrp", return None
    return None
    
    
def get_ik_affected_joints(ik_handle):
    """
    Gets joints affected by a given IK handle

    :param pm.nt.IkHandle ik_handle: IK handle node whose joints we want to query  
    
    """
    # Get the start joint of the IK handle
    start_joint = pm.ikHandle(ik_handle, query=True, startJoint=True)
    
    # Get the end effector of the IK handle, which is usually the last joint
    end_effector = pm.ikHandle(ik_handle, query=True, endEffector=True)
    end_joint = pm.listConnections(end_effector.tx, source=True, destination=False)[0]  # Get joint connected to the end effector
    
    # Traverse the joint chain from start to end
    joint_chain = []
    current_joint = start_joint
    
    while current_joint:
        joint_chain.append(current_joint)
        if current_joint == end_joint:
            break
        # Move to the next joint
        children = pm.listRelatives(current_joint, children=True, type="joint")
        if children:
            current_joint = children[0]
        else:
            break

    return joint_chain


def ikfk_switch_scene_cleanup(namespace_name, autokey_state):
    """
    Scene cleanup to set back namespace and autokey state + remove temp nodes from IKFK switch
    
    :param str namespace_name: Name of the namespace we want to purge
    :param bool autokey_state: Autokey state to set the scene back to

    """

    pm.namespace(set=':') 
    mayaUtils.purge_namespace(namespace_name)
    pm.autoKeyframe(state=autokey_state)
    return


def find_export_joint(control, substring="JNT_SKL"):
    """
    Traverses from a given control down its connections to find a joint
    whose name ends with the specified substring.
    
    Args:
        control (str): The name of the reverse foot control.
        substring (str): The substring that should be at the end of the joint name (default is "JNT_SKL").
        
    Returns:
        str: The name of the joint found, or None if no joint was found.
    """
    visited = set()  # To prevent infinite loops
    to_check = [control]  # Start with the control

    while to_check:
        current_node = to_check.pop(0)
        if current_node in visited:
            continue
        visited.add(current_node)
        
        # Check if the current node is a joint and if its name ends with the substring
        if cmds.nodeType(current_node) == "joint" and current_node.endswith(substring):
            return current_node
        
        # Get all connected nodes
        connected_nodes = cmds.listConnections(current_node, s=False, d=True) or []
        to_check.extend(connected_nodes)

    return None  # No joint found

def disconnect_anim_curves(control):
    """
    Disconnects all animation curves from the given control and returns a list of disconnected connections.
    
    Args:
        control (str): The name of the control from which to disconnect animation curves.
    
    Returns:
        list: A list of tuples containing the animation curve and the attribute it was connected to.
    """
    disconnected_connections = []
    
    # Get all outgoing connections from the control
    connections = cmds.listConnections(control, plugs=True, destination=True, source=False) or []
    
    
    for attr in ATTR_LST:
        # Get all outgoing connections from the control
        connections = cmds.listConnections(f'{control}.{attr}', plugs=True, destination=0, source=1) or []
        
        for connection in connections:
            # Check if the connected node is an animation curve
            connected_node = connection.split('.')[0]
            if isinstance(pm.PyNode(connected_node), pm.nt.AnimCurve):
                
                # Store the connected animation curve and the attribute
                disconnected_connections.append((connected_node, f'{control}.{attr}'))
                # Disconnect the animation curve from the control
                cmds.disconnectAttr(f'{connected_node}.output', f'{control}.{attr}')
    list(map(lambda x: pm.setAttr(f'{control}.{x}', 0), ATTR_LST))
    return disconnected_connections

def reconnect_anim_curves(disconnected_connections):
    """
    Reconnects animation curves to their original attributes.
    
    Args:
        disconnected_connections (list): A list of tuples containing the animation curve and the attribute to reconnect.
    """
    for anim_curve, attr in disconnected_connections:
    # Reconnect the animation curve to the original attribute
        cmds.connectAttr(f'{anim_curve}.output', attr)