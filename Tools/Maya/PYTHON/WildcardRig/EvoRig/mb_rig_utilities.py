import re
import sys, traceback
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
import copy

from collections import OrderedDict as od

DEFAULT_INTERPTYPE = 2  # shortest

if 2 < sys.version_info.major:
    basestring = str

debugging = False


# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
class errorOD(od):
    """ Ordered dictionary for storing and printing rig validation errors nicely """
    def __init__(self, *args, **kwargs):
        super(errorOD, self).__init__(*args)
        self.separator = kwargs.get("separator", "*")
        self.tab = kwargs.get("tab", 1)

    def __repr__(self, *args, **kwargs):
        return stringList(self.values(), separator=self.separator, tab=self.tab)

    def __str__(self, *args, **kwargs):
        return self.__repr__(*args, **kwargs)


# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Methods
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def printdebug(String):
    """Print message for debugging. Only displays if global variable 'debugging' is set to 'True'"""
    if (debugging):
        print(String)


def stringList(array, separator="*", tab=0):
    """ Generic formatting for iterables into a string recursively """
    print('=' * 80)
    print("THIS IS THE ARRAY: {}".format(array))
    print('=' * 80)
    separatorString = f"\n{'    ' * tab}{separator}"
    return "".join(stringList(x, separator, tab+1) if is_iterable(x) else separatorString + str(x) for x in array)

def deleteRigOld(rig):
    """
    This is the OLD delete rig function. We check the version number on rigs and if it is one
    which was built prior to the network node update to EvoRig, use this delete function. New rigs
    can utilize the safer deleteRig function which only removed nodes that are connected to the rig.
    
    :param pm.nt.Transform rig: Rig group for the rig being removed 

    """

    # Delete blendColor nodes and unused node
    blendColor_nodes = pm.ls(type="blendColors")
    for node in blendColor_nodes:
        pm.delete(node)
    curve_info_nodes = pm.ls(type='curveInfo')   # need to delete curveInfo node before deleting the rig to fix no valid NURBS curve bug when deleting rig/re-gen
    if curve_info_nodes:
        pm.delete(curve_info_nodes)
    clamp_nodes = pm.ls(type='clamp')
    pm.delete(clamp_nodes)

    # Zero out face controls
    face_rig_ctrls = [x for x in pm.ls(type=pm.nt.Transform) if x.hasAttr('faceCtrl')]
    for face_ctrl in face_rig_ctrls:
        for attr_name in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            attr = pm.PyNode(f'{face_ctrl}.{attr_name}')
            if attr.isKeyable() and not attr.isLocked() and not attr.isConnected():
                attr.set(0)
    
    # Delete rig grp and ensure joints are 1.0 scale
    pm.delete(rig)
    joints = pm.ls(type=pm.nt.Joint)
    for jnt in joints:
        for attr in ['sx', 'sy', 'sz']:
            pm.setAttr(f'{jnt}.{attr}', 1)

    # Clean up other rig nodes that may have hung around
    remap_nodes = pm.ls(type='remapValue')
    sub_nodes = pm.ls(type='subtract')
    pm.delete(remap_nodes+sub_nodes)

    pm.mel.MLdeleteUnused()


def deleteRig(rig):
    """
    This is the CURRENT delete rig function. It uses the rig network nodes to determine
    which nodes to remove. This should always be used over deleteRigOld unless the rig was built
    on EvoRig version prior to 1.15.0 because deleteRigOld can remove nodes not related to the rig
    
    :param pm.nt.Transform rig: Rig group for the rig being removed 
    
    """

    if isinstance(rig, list):
        rig = rig[0]

    check = pm.ls(rig)
    if not check:
        return
    
    rigVersion = pm.getAttr(f'{rig}.evoRigVersion')
    oldRig = False if tuple(map(int, rigVersion.split('.'))) >= (1, 15, 0) else True
    if oldRig:
        deleteRigOld(rig)
        return     

    rigJoints = []
    rigNetworkName = f'{rig}_Network'
    trashNodes = []
    if pm.objExists(rigNetworkName):
        rigNetwork = pm.PyNode(rigNetworkName)
        bc_nodes = getConnectedFromMulti(rigNetwork, 'blendColors')
        trashNodes += bc_nodes

        moduleNetworks = rigNetwork.modules.get()
        for moduleNetwork in moduleNetworks:
            connectedNodes = getConnectedFromMulti(moduleNetwork)
            trashNodes += [x for x in connectedNodes if not isinstance(x, pm.nt.Joint)]
            rigJoints += moduleNetwork.joints.get()

            if moduleNetwork.moduleClass.get() == 'MakeFace.faceCtrl':
                # Zero out face controls
                faceControls = moduleNetwork.controls.get()
                for faceControl in faceControls:
                    for attrName in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
                        attr = pm.PyNode(f'{faceControl}.{attrName}')
                        if attr.isKeyable() and not attr.isLocked() and not attr.isConnected():
                            attr.set(0)
            trashNodes.append(moduleNetwork)

    # Remove rig nodes 
    pm.delete(trashNodes)

                
    # Delete rig grp 
    pm.delete(rig)

    # Additional garbage cleanup 
    pm.mel.MLdeleteUnused()

    # Make sure joints are 1.0 scale (deleting some rig nodes that affect scale may set them to 0)
    for rigJoint in rigJoints:
        for attrName in ['sx', 'sz', 'sy']:
            attr = pm.PyNode(f'{rigJoint}.{attrName}')
            if attr.isKeyable() and not attr.isLocked() and not attr.isConnected():
                attr.set(1)   



def getExportJoint(node=None):
    '''Return pynode of appropriate export joint if it exists'''

    suffix = '_RigJnt'

    # if hasattr(node, '__iter__'):
    if is_iterable(node):
        return type(node)([getExportJoint(x) for x in node])

    if isinstance(node, basestring):
        if node:
            if len(pm.ls(node)) > 0:
                return pm.PyNode(node.replace(suffix, ''))

    if node:
        return pm.PyNode(node.name().replace(suffix, ''))

    return node


def getRigJoint(node=None):
    '''Return pynode of appropriate rig joint if it exists'''

    suffix = '_RigJnt'
    # if hasattr(node, '__iter__'):
    if is_iterable(node):
        return type(node)([getRigJoint(x) for x in node])

    if isinstance(node, basestring):
        if node and not re.findall(suffix + '$', node):
            if len(pm.ls(node)) > 0:
                return pm.PyNode(node + suffix)
            return None
        return None

    if node and not re.findall(suffix + '$', node.name()):
        return pm.PyNode(node.name() + suffix)

    return node

def selectJointsForRig_cmd():
    selectedRig = pm.selected()
    if not selectedRig or not selectedRig[0].hasAttr('mainNetwork'):
        rigGrps = [x for x in pm.ls(type=pm.nt.Transform) if x.hasAttr('mainNetwork')]
        if rigGrps:
            selectedRig = rigGrps[0]
        else:
            pm.warning('No rigs found in the scene')
            return
    else:
        selectedRig = selectedRig[0]
    networkNode = selectedRig.mainNetwork.get()
    rigJnts = getJointsForRig(networkNode)
    pm.select(rigJnts, r=True)


def getJointsForRig(networkNode):
    rigJnts = []
    for m in networkNode.modules.get():
        jnts = m.joints.get()
        rigJnts += jnts
    return rigJnts

def getConnectedFromMulti(node, attr=None):
    """
    Returns nodes connection to a multi attr on the given node 
    
    :param pm.PyNode node: Node whose connections we will check
    :param str attr: Multi attr to check for connections on 
    
    """

    node = pm.PyNode(node)
    out = []
    if attr:
        if not node.hasAttr(attr):
            return []

        plug = node.attr(attr)

        for i in sorted(plug.getArrayIndices()):
            con = plug[i].listConnections(s=0, d=1)
            if con:
                out.append(con[0])
    else:
        multiAttrs = [a for a in node.listAttr(multi=True, userDefined=True)]
        for multiAttr in multiAttrs:
            connectedNode = multiAttr.listConnections(s=0, d=1)
            if connectedNode:
                out.append(connectedNode[0])

    return out

def connectMessage(src, srcAttr, targets, dstAttr="parentComponent"):
    """
    Connects message attrs between nodes
    
    :param pm.PyNode src: Source node from which will come the connection
    :param str srcAttr: Source attribute from which will come the connection
    :param list(pm.PyNode) targets: List of target nodes to receive connection
    :param str dstAttr: Destination attribute to receive connection

    """

    src = pm.PyNode(src)
    if not src.hasAttr(srcAttr):
        src.addAttr(srcAttr, at="message", multi=True)

    plug = src.attr(srcAttr)

    if not isinstance(targets, (list, tuple, set)):
        targets = [targets]

    existing = set(plug.listConnections(s=True, d=False))

    for tgt in targets:
        tgt = pm.PyNode(tgt)

        if not tgt.hasAttr(dstAttr):
            tgt.addAttr(dstAttr, at="message")

        if tgt in existing:
            continue

        plug[plug.numElements()].connect(tgt.attr(dstAttr), force=True)
        existing.add(tgt)

def is_iterable(value):
    '''python 3 strings are iterables (for the love of all thats holy why?!) so old iterable checks no longer work *sigh*'''
    return hasattr(value, '__iter__') and not isinstance(value, str) and not issubclass(type(value), pm.general.PyNode)


def isPyNode(item, flatten=True, warning=False):
    '''Tests to see if an item or list of items is all pynodes
	   If flatten, return false if any in a list are not pynodes'''

    # if hasattr(item, '__iter__'):
    if is_iterable(item):
        if not flatten:
            if issubclass(type(item), dict):
                return type(item)(((x, isPyNode(x, flatten=flatten, warning=warning)) for x in item))
            return type(item)(isPyNode(x, flatten=flatten, warning=warning) for x in item)
        else:
            if issubclass(type(item), dict):
                for v in item.values():
                    if not isPyNode(v, flatten=flatten, warning=warning):
                        return False
            for x in item:
                if not isPyNode(x, flatten=flatten, warning=warning):
                    return False
            return True

    if warning:
        pm.warning(str(warning) + 'isPyNode Could not find "' + str(item))
    return issubclass(type(item), pm.general.PyNode)


def getPyNode(item, warning=False):
    if issubclass(type(item), dict):
        new = type(item)()
        for k, v in item.items():
            new[k] = getPyNode(v, warning=warning)
        return new

    # elif hasattr(item, '__iter__'):
    elif is_iterable(item):
        return type(item)(getPyNode(v, warning=warning) for v in item)

    # check if pynode and pointer is valid, else search for name
    if issubclass(type(item), pm.general.PyNode):
        try:
            item.exists()
            return item
        except:
            result = (pm.ls(item._name) or pm.ls(item._name.split('|')[-1].split(':')[-1]) or pm.ls(item._name, r=1) or pm.ls(item._name.split('|')[-1].split(':')[-1], r=1) or [item])[0]

    # check name
    else:
        result = (pm.ls(item) or pm.ls(item.split('|')[-1].split(':')[-1]) or pm.ls(item, r=1) or pm.ls(item.split('|')[-1].split(':')[-1], r=1) or [item])[0]

    if warning and not issubclass(type(result), pm.general.PyNode):
        pm.warning(str(warning) + 'getPyNode Could not find "' + str(item) + '"')
    return result


def node_to_string(item):
    # if hasattr(item, '__iter__'):
    if is_iterable(item):
        working = copy.deepcopy(item)
        if not issubclass(type(working), dict):
            working = type(working)(map(node_to_string, working))
        else:
            for k, v in working.items():
                change = False
                v = node_to_string(v)
                del working[k]
                working[k] = v
        return working
    if isPyNode(item):
        return item.longName()
    return item


def node_from_string(item):
    # if hasattr(item, '__iter__'):
    if is_iterable(item):
        working = copy.deepcopy(item)
        if not issubclass(type(working), dict):
            working = type(working)(map(node_from_string, working))
        else:
            for k, v in working.items():
                change = False
                v = node_from_string(v)
                del working[k]
                k = node_from_string(k)
                working[k] = v
        return working
    string = str(item)
    if '|' in string:
        check = (pm.ls(string) or [None])[0]
        if not check:
            check = (pm.ls(string.split('|')[-1].split(':')[-1]) or [None])[0]
        if check:
            return check
    return item


def getSwitchEnumNames(SpaceSwitcherJoints, nameDetailLevel, nameDetailStart=0):
    namelist = []
    for i, jnt in enumerate(SpaceSwitcherJoints):

        nametempsplit = jnt.name().split("_")
        if (len(nametempsplit) >= nameDetailLevel):
            nametemp = nametempsplit[nameDetailStart:nameDetailLevel]
            shortname = '_'.join(nametemp)
        else:
            shortname = jnt.name()
        shortname = shortname.replace("_RigJnt", "")
        shortname = shortname.replace("_CON", "")
        shortname = shortname.replace("_Target", "")
        namelist.append(shortname)
    return ':'.join(namelist)


def setupSpaceOffsets(ctrl):
    offsetGrp = pm.createNode('transform', n='%s_offset_GRP' % ctrl, parent=ctrl)
    ctrlParent = ctrl.getParent()
    pm.parent(offsetGrp, ctrlParent)
    pm.parent(ctrl, offsetGrp, r=True)
    offsets = ('translate', 'rotate')
    xformAxis = ('x', 'y', 'z')

    for offset in offsets:
        for axis in xformAxis:
            name = '%sOffset%s' % (offset, axis.upper())
            pm.addAttr(ctrl, ln=name, at='double', hidden=True, k=False)
            pm.setAttr('%s.%s' % (ctrl, name), keyable=False)
            pm.connectAttr('%s.%s' % (ctrl, name), '%s.%s%s' % (offsetGrp, offset, axis.upper()))


def setupSpaceBlending(ctrl,
                       localSpaceSwitcherJoints,
                       spaceBlends):
    if not issubclass(type(spaceBlends), dict):  # michaelb - Prevent AttributeError: 'list' object has no attribute 'keys'
        return

    localSpaceSwitcherJoints = list(map(getRigJoint, spaceBlends.keys()))

    parentCns = pm.parentConstraint(localSpaceSwitcherJoints, ctrl.getParent(), mo=True)
    parentCns.setAttr('interpType', DEFAULT_INTERPTYPE)

    print('spaceBlends:' + str(len(spaceBlends)))
    for a, b in zip(localSpaceSwitcherJoints, parentCns.getWeightAliasList()):
        print('{}  ->  {}'.format(a, b))

    for w, weight in enumerate(parentCns.getWeightAliasList()):
        weight_name = str(weight.attrName(longName=True)).split('|:')[-1][:-2].replace('_RigJnt', '')
        parentCns.setAttr(weight.attrName(longName=True), spaceBlends[weight_name])


def setupSpaceSwitch(ctrl,
                     SpaceSwitcherJoints,
                     nameDetailLevel=2,
                     inheritParentLevel=1,
                     nameDetailStart=0,
                     maintainOffset=True,
                     fk=False,
                     spaceBlends=None):
    localSpaceSwitcherJoints = SpaceSwitcherJoints[:]
    """for i, jnt in enumerate(localSpaceSwitcherJoints):
		if (jnt.name().find('_prop_') > -1):
			con = pm.PyNode(getNiceControllerName(jnt.name(), "_CON"))
			if con:
				localSpaceSwitcherJoints[i] = con   #Replace prop joint with control of the same name
	"""
    if spaceBlends:
        setupSpaceBlending(ctrl, localSpaceSwitcherJoints, spaceBlends)
        setupSpaceOffsets(ctrl)
        return
    switchEnumNames = getSwitchEnumNames(localSpaceSwitcherJoints, nameDetailLevel, nameDetailStart)
    inh = ctrl
    while inheritParentLevel > 0:
        inh = inh.getParent()
        inheritParentLevel -= 1

    if fk:
        parentCns = pm.parentConstraint(localSpaceSwitcherJoints, inh.getParent(), mo=True, skipTranslate=["x", "y", "z"])
        parentTranslateCns = pm.parentConstraint(localSpaceSwitcherJoints[0], inh, mo=True, skipRotate=["x", "y", "z"])
        parentTranslateCns.setAttr('interpType', DEFAULT_INTERPTYPE)
    else:
        parentCns = pm.parentConstraint(localSpaceSwitcherJoints, inh, mo=maintainOffset)

    parentCns.setAttr('interpType', DEFAULT_INTERPTYPE)
    weightAliases = parentCns.getWeightAliasList()

    # standard switch setup
    pm.addAttr(ctrl, at="enum", ln="space", enumName=switchEnumNames, k=True)
    for i, jnt in enumerate(localSpaceSwitcherJoints):
        conditionNode = pm.shadingNode('condition', asUtility=True)
        conditionNode.setAttr("secondTerm", i)
        conditionNode.setAttr("colorIfTrueR", 1)
        conditionNode.setAttr("colorIfFalseR", 0)
        pm.connectAttr(ctrl.name() + ".space", conditionNode.name() + '.firstTerm')
        pm.connectAttr(conditionNode.name() + '.outColor.outColorR', parentCns.name() + '.' + weightAliases[i].attrName(longName=True))

    setupSpaceOffsets(ctrl)


""" DEPRECATED - setupSpaceSwitchFK"""


def setupSpaceSwitchFK(ctrl, SpaceSwitcherJoints, nameDetailLevel=2, inheritParentLevel=1):
    localSpaceSwitcherJoints = SpaceSwitcherJoints[:]
    """for i, jnt in enumerate(localSpaceSwitcherJoints):
		if (jnt.name().find('_prop_') > -1):
			con = pm.PyNode(getNiceControllerName(jnt.name(), "_CON"))
			if con:
				localSpaceSwitcherJoints[i] = con   #Replace prop joint with control of the same name
	"""

    switchEnumNames = getSwitchEnumNames(localSpaceSwitcherJoints, nameDetailLevel)
    inh = ctrl
    while inheritParentLevel > 0:
        inh = inh.getParent()
        inheritParentLevel -= 1
    # Make 2 constraints, the first is rotation and allows space switching, the second is translation and always locks the FK control to the parent
    parentCns = pm.parentConstraint(localSpaceSwitcherJoints, inh.getParent(), mo=True, skipTranslate=["x", "y", "z"])
    parentCns.setAttr('interpType', DEFAULT_INTERPTYPE)
    parentTranslateCns = pm.parentConstraint(localSpaceSwitcherJoints[0], inh, mo=True, skipRotate=["x", "y", "z"])
    parentTranslateCns.setAttr('interpType', DEFAULT_INTERPTYPE)

    pm.addAttr(ctrl, at="enum", ln="space", enumName=switchEnumNames, k=True)
    weightAliases = parentCns.getWeightAliasList()
    for i, jnt in enumerate(localSpaceSwitcherJoints):
        conditionNode = pm.shadingNode('condition', asUtility=True)
        conditionNode.setAttr("secondTerm", i)
        conditionNode.setAttr("colorIfTrueR", 1)
        conditionNode.setAttr("colorIfFalseR", 0)
        pm.connectAttr(ctrl.name() + ".space", conditionNode.name() + '.firstTerm')
        pm.connectAttr(conditionNode.name() + '.outColor.outColorR', parentCns.name() + '.' + weightAliases[i].attrName(longName=True))
    # pm.addAttr(ctrl, at="double", ln="orient", k=True)

    setupSpaceOffsets(ctrl)


# ethanm - Python 3 compatable version
def findInChain(parentjnt, findname, chain=None):
    if isPyNode(findname):
        searchname = findname.name().split('|')[-1]
    else:
        searchname = findname

    if chain == None:
        chain = parentjnt.listRelatives(ad=True, type='joint')
        chain.append(parentjnt)

    if (searchname.find('_CON') > -1):  # Allow using control as a space
        con = pm.PyNode(searchname.replace('_RigJnt', ''))
        if con:
            return con

    for i, jnt in enumerate(chain):
        # really should be using basenames for these,
        # rather that full path names on duplicates
        # however name changing this will break animation links to preexisting rigs.

        aName = jnt.name().replace('|', '_')
        if (aName.find(searchname) >= 0):
            return jnt

    print('Joint not found in hierarchy: ' + findname + "  joint chain: " + str(chain))
    return None


def findInChainOld(parentjnt, findname, chain=None):
    if isPyNode(findname):
        searchname = findname.name()
    else:
        searchname = findname

    if chain == None:
        chain = parentjnt.listRelatives(ad=True, type='joint')
        chain.append(parentjnt)

    if (searchname.find('_CON') > -1):  # Allow using control as a space
        con = pm.PyNode(searchname.replace('_RigJnt', ''))
        if con:
            return con

    for i, jnt in enumerate(chain):

        aName = jnt.name()
        aName = aName.decode("utf-8").replace(u"\u007C", "_")  # replace vertical line character with "_"
        # if re.search(searchname + '$', aName):  <- TODO: Exact match! Need to thoroughly test before using this
        if (aName.find(searchname) >= 0):
            return jnt
    # splitname = aName.split("_")[1]
    # if (splitname.find(searchname) == 0) or (aName.find(searchname) == 0):
    #    return jnt

    print('Joint not found in hierarchy: ' + findname + "  joint chain: " + str(chain))
    return None


def findAllInChain(parentjnt, findname, allDescendents=True, disableWarning=False):
    '''find all joints matching findname checks ls syntax first then regular expression if that fails'''
    if isinstance(parentjnt, str):
        parentjnt = pm.PyNode(parentjnt)
    if pm.objExists(parentjnt):
        chain = (parentjnt.listRelatives(ad=allDescendents, type='joint') or []) + [parentjnt]

        # check ls
        jnts = list(set([x for x in pm.ls(findname, '*' + findname, findname + '*', '*' + findname + '*', type='joint') if x in chain]))
        if jnts:
            hisort = lambda x:len(x.longName().split('|'))
            return sorted(jnts, key=hisort)

        # check regex
        jnts = [x for x in reversed(chain) if re.findall(findname, str(x.name()).split('|')[-1], re.IGNORECASE)]
        if jnts:
            return jnts

        if not disableWarning:
            pm.warning('Joint not found in hierarchy: ' + findname + "  joint chain: " + str(chain))


# ethanm - old version of function had odd behavior, would return parent objects if duplicate named objects existed.
def findAllInChainOld(parentjnt, findname, allDescendents=True, disableWarning=False):
    findname = findname.lower()
    chain = parentjnt.listRelatives(ad=allDescendents, type='joint')
    chain.append(parentjnt)
    jnts = []
    for i, jnt in enumerate(chain):

        aName = str(jnt.name())
        aName = aName.decode("utf-8").replace(u"\u007C", "_")  # replace vertical line character with "_"
        aName = aName.lower()
        splitnames = aName.split("_")
        splitname = aName
        if (len(splitnames) > 1):
            splitname = splitnames[1]
        if (splitname.find(findname) == 0) or (aName.find(findname) >= 0):
            if (jnt not in jnts):
                jnts.append(jnt)

    if (len(jnts) > 0):
        return jnts

    if not disableWarning:
        pm.warning('Joint not found in hierarchy: ' + findname + "  joint chain: " + str(chain))

    return None


def findExactInChain(parentjnt, findname, chain=None, suffix=''):
    if not isPyNode(parentjnt):
        parentjnt = getPyNode(parentjnt)
    # print("findname is {}".format(findname))
    searchname = findname
    if chain == None:
        chain = parentjnt.listRelatives(ad=True, type='joint')
        chain.append(parentjnt)
    # print("Chain is: {}".format(chain))

    splitnames = searchname.split(u"\u007C")
    if (len(splitnames) > 0):
        searchname = splitnames[-1]

    # print("Searchname is {}".format(searchname))
    for i, jnt in enumerate(chain):
        aName = jnt.name()
        splitnames = aName.split(u"\u007C")
        if (len(splitnames) > 1):
            aName = splitnames[-1]

        # print("Search for {}".format(searchname + suffix + '$'))
        if (re.search(searchname + suffix + '$', aName)):
            # print("Found {}".format(jnt.name()))
            return jnt

    print('Joint not found in hierarchy: ' + findname + " \n joint chain: " + str(chain) + "\n suffix: " + suffix + " parentjnt:" + parentjnt)
    print('-' * 60)
    traceback.print_exc()  # file=sys.stdout
    print('-' * 60)
    return None


def getParents(a):
    rel = a[-1].listRelatives(p=True)

    if (len(rel) > 0):
        # print(rel)
        a.append(rel[0])
        return getParents(a)
    else:
        return a


# Returns all parents
def allParents(x, includeInput=False):
    y = getParents([x])
    if includeInput == False:
        y.pop(0)
    return y


def getChainFromStartToEnd(startJoint, endJoint, raiseError=True):
    parents = allParents(endJoint, includeInput=True)
    if (startJoint not in parents):
        if raiseError:
            raise ValueError('startJoint {} was not found in hierarchy of endJoint {}'.format(startJoint, endJoint))
        #return 'startJoint {} was not found in hierarchy of endJoint {}'.format(startJoint, endJoint)
        return "{0}:{1}".format(startJoint, endJoint) # I need the original joints back - MM

    startIndex = parents.index(startJoint)
    chain = parents[:startIndex + 1]
    chain.reverse()
    return chain


def makeNurbsShape(shapeIndex, name, scale=1.0, forwardAxis='Y'):  # , worldUpAxis='Y'

    ctrl = None
    if (shapeIndex == 0):  # Cube
        ctrl = pm.curve(d=1, p=[(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
                                (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
                                (-1, -1, 1), (1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1),
                                (-1, 1, 1), (-1, 1, -1)], name=name)
    elif (shapeIndex == 1):  # 4 Large Arrows
        ctrl = pm.curve(d=1, p=[(0.0, 0.0, -11.025),
                                (-3.3003, 0.0, -6.075), (-1.6501, 0.0, -6.075),
                                (-1.6501, 0.0, -1.6501), (-6.075, 0.0, -1.6501),
                                (-6.075, 0.0, -3.3003), (-11.025, 0.0, 0.0),
                                (-6.075, 0.0, 3.3003), (-6.075, 0.0, 1.6501),
                                (-1.6501, 0.0, 1.6501), (-1.6501, 0.0, 6.075),
                                (-3.3003, 0.0, 6.075), (0.0, 0.0, 11.025),
                                (3.3003, 0.0, 6.075), (1.6501, 0.0, 6.075),
                                (1.6501, 0.0, 1.6501), (6.075, 0.0, 1.6501),
                                (6.075, 0.0, 3.3003), (11.025, 0.0, 0.0),
                                (6.075, 0.0, -3.3003), (6.075, 0.0, -1.6501),
                                (1.6501, 0.0, -1.6501), (1.6501, 0.0, -6.075), (3.3003, 0.0, -6.075),
                                (0.0, 0.0, -11.025)], name=name)

    elif (shapeIndex == 2):  # 4 Arrow on Ball
        ctrl = pm.curve(d=1, p=[
            (0.0, 0.35, -1.001567), (-0.336638, 0.677886, -0.751175), (-0.0959835, 0.677886, -0.751175),
            (-0.0959835, 0.850458, -0.500783), (-0.0959835, 0.954001, -0.0987656), (-0.500783, 0.850458, -0.0987656),
            (-0.751175, 0.677886, -0.0987656), (-0.751175, 0.677886, -0.336638), (-1.001567, 0.35, 0.0),
            (-0.751175, 0.677886, 0.336638), (-0.751175, 0.677886, 0.0987656), (-0.500783, 0.850458, 0.0987656),
            (-0.0959835, 0.954001, 0.0987656), (-0.0959835, 0.850458, 0.500783), (-0.0959835, 0.677886, 0.751175),
            (-0.336638, 0.677886, 0.751175), (0.0, 0.35, 1.001567), (0.336638, 0.677886, 0.751175),
            (0.0959835, 0.677886, 0.751175), (0.0959835, 0.850458, 0.500783), (0.0959835, 0.954001, 0.0987656),
            (0.500783, 0.850458, 0.0987656), (0.751175, 0.677886, 0.0987656), (0.751175, 0.677886, 0.336638),
            (1.001567, 0.35, 0.0), (0.751175, 0.677886, -0.336638), (0.751175, 0.677886, -0.0987656),
            (0.500783, 0.850458, -0.0987656), (0.0959835, 0.954001, -0.0987656), (0.0959835, 0.850458, -0.500783),
            (0.0959835, 0.677886, -0.751175), (0.336638, 0.677886, -0.751175), (0.0, 0.35, -1.001567)], name=name)

    # if forwardAxis == 'X':
    # spans = pm.getAttr(ctrl.name() + ".spans")
    # pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True )
    # pm.rotate([0,0,90], os=True, pivot=[0,0,0])
    # pm.rotate([0,-90,0], os=True, pivot=[0,0,0])
    elif (shapeIndex == 3):  # IK FK Switch Arrow
        ctrl = pm.curve(d=1, p=[
            (0.0, -1.0918784085699965e-22, 0.5071575215512235), (-0.4, -1.0918784085699965e-22, 0.1071575215512224),
            (-0.2, -1.0918784085699965e-22, 0.1071575215512224), (-0.2, -1.0918784085699965e-22, -0.49284247844877727),
            (0.2, -1.0918784085699965e-22, -0.49284247844877727), (0.2, -1.0918784085699965e-22, 0.1071575215512224),
            (0.4, -1.0918784085699965e-22, 0.1071575215512224), (0.0, -1.0918784085699965e-22, 0.5071575215512235),
            (0.0, 0.4, 0.1071575215512224), (0.0, 0.2, 0.1071575215512224), (0.0, 0.2, -0.49284247844877727), (0.0, -0.2, -0.49284247844877727),
            (0.0, -0.2, 0.1071575215512224), (0.0, -0.4, 0.1071575215512224), (0.0, -1.0918784085699965e-22, 0.5071575215512235)], name=name)
    elif (shapeIndex == 4):  # Single Arrow
        ctrl = pm.curve(d=1, p=[
            (0.4, 0.0, -0.825), (0.3, 0.0, -0.165), (0.825, 0.0, -0.165),
            (0.0, 0.0, 0.825), (-0.825, 0.0, -0.165),
            (-0.3, 0.0, -0.165), (-0.4, 0.0, -0.825),
            (0.4, 0.0, -0.825)], name=name)
    # (-0.66,0.0,-0.33),(0.0,0.0,-0.33),(0.0,0.0,-0.66),(0.99,0.0,0.0),(0.0,0.0,0.66),(0.0,0.0,0.33),(-0.66,0.0,0.33),(-0.66,0.0,-0.33)], name=name)
    elif (shapeIndex == 5):  # 4 Pins
        ctrl = pm.curve(d=1, p=[
            (-0.6119941715212495, 0.0, 0.0), (-0.6509542304754357, 0.11990699803587271, 0.0), (-0.7529532590623104, 0.19401388226052368, 0.0),
            (-0.879031198327688, 0.19401388226052368, 0.0), (-0.9810302269145628, 0.11990699803587271, 0.0), (-1.0199902858687497, 0.0, 0.0),
            (-0.9810302269145628, -0.11990699803587271, 0.0), (-0.879031198327688, -0.19401388226052368, 0.0), (-0.7529532590623104, -0.19401388226052368, 0.0),
            (-0.6509542304754357, -0.11990699803587271, 0.0), (-0.6119941715212495, 0.0, 0.0), (0.0, 0.0, 0.0), (0.6119941715212495, 0.0, 0.0),
            (0.6509542304754357, 0.11990699803587271, 0.0), (0.7529532590623104, 0.19401388226052368, 0.0), (0.879031198327688, 0.19401388226052368, 0.0),
            (0.9810302269145628, 0.11990699803587271, 0.0), (1.0199902858687497, 0.0, 0.0), (0.9810302269145628, -0.11990699803587271, 0.0),
            (0.879031198327688, -0.19401388226052368, 0.0), (0.7529532590623104, -0.19401388226052368, 0.0), (0.6509542304754357, -0.11990699803587271, 0.0),
            (0.6119941715212495, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, -0.6119941715212495, 0.0), (-0.11990699803587271, -0.6509542304754357, 0.0),
            (-0.19401388226052368, -0.7529532590623104, 0.0), (-0.19401388226052368, -0.879031198327688, 0.0), (-0.11990699803587271, -0.9810302269145628, 0.0),
            (0.0, -1.0199902858687497, 0.0), (0.11990699803587271, -0.9810302269145628, 0.0), (0.19401388226052368, -0.879031198327688, 0.0),
            (0.19401388226052368, -0.7529532590623104, 0.0), (0.11990699803587271, -0.6509542304754357, 0.0), (0.0, -0.6119941715212495, 0.0), (0.0, 0.0, 0.0),
            (0.0, 0.6119941715212495, 0.0), (-0.11990699803587271, 0.6509542304754357, 0.0), (-0.19401388226052368, 0.7529532590623104, 0.0),
            (-0.19401388226052368, 0.879031198327688, 0.0), (-0.11990699803587271, 0.9810302269145628, 0.0), (0.0, 1.0199902858687497, 0.0),
            (0.11990699803587271, 0.9810302269145628, 0.0), (0.19401388226052368, 0.879031198327688, 0.0), (0.19401388226052368, 0.7529532590623104, 0.0),
            (0.11990699803587271, 0.6509542304754357, 0.0), (0.0, 0.6119941715212495, 0.0)], name=name)

        if forwardAxis == 'X':
            spans = pm.getAttr(ctrl.name() + ".spans")
            pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True)
            pm.rotate([90, 0, 0], os=True)
    elif (shapeIndex == 6):  # Squashed circle
        ctrl = pm.circle(ch=0, o=1, r=1, nr=(0, 1, 0), name=name)[0]
        pm.select(ctrl + ".cv[1]", r=True)
        pm.select(ctrl + ".cv[3]", add=True)
        pm.select(ctrl + ".cv[5]", add=True)
        pm.select(ctrl + ".cv[7]", add=True)
        pm.scale(0.8, 0.8, 0.8, r=True)
    elif (shapeIndex == 7):  # Plus sign
        ctrl = pm.curve(d=1, p=[
            [-0.33213198489894546, -5.952891105961085e-15, -0.33127051842907845], [-0.33213198489894546, -5.952891105961085e-15, -0.9955303268473533],
            [0.3321278235193313, -5.952891105961085e-15, -0.9955303268473533], [0.3321278235193313, -5.952891105961085e-15, -0.33127051842907845],
            [0.996387631937606, -5.952891105961085e-15, -0.33127051842907845], [0.996387631937606, -5.952891105961085e-15, 0.332989289989196],
            [0.3321278235193313, -5.952891105961085e-15, 0.332989289989196], [0.3321278235193313, -5.952891105961085e-15, 0.9972490984074726],
            [-0.33213198489894546, -5.952891105961085e-15, 0.9972490984074726], [-0.33213198489894546, -5.952891105961085e-15, 0.332989289989196],
            [-0.9963917933172187, -5.952891105961085e-15, 0.332989289989196], [-0.9963917933172187, -5.952891105961085e-15, -0.33127051842907845],
            [-0.33213198489894546, -5.952891105961085e-15, -0.33127051842907845]], name=name)

    elif (shapeIndex == 8):  # Circle
        circleNormal = (1, 0, 0)
        if forwardAxis == 'Y':
            circleNormal = (0, 1, 0)
        elif forwardAxis == 'Z':
            circleNormal = (0, 0, 1)

        ctrl = pm.circle(ch=0, o=1, r=1, nr=circleNormal, name=name)[0]
        """if forwardAxis == 'Z':
			spans = pm.getAttr(ctrl.name() + ".spans")
			pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True )
			pm.rotate([0,0,90], os=True)
		elif forwardAxis == 'X':
			#print '_________________________________ X FORWARD ______________'
			spans = pm.getAttr(ctrl.name() + ".spans")
			pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True )
			pm.rotate([90,0,0], os=True)"""
    elif (shapeIndex == 9):  # Square
        ctrl = pm.curve(d=1, p=[(1, 0, -1), (1, 0, 1),
                                (-1, 0, 1), (-1, 0, -1), (1, 0, -1)], name=name)
        if forwardAxis == 'X':
            spans = pm.getAttr(ctrl.name() + ".spans")
            pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True)
            pm.rotate([0, 0, 90], os=True)
    elif (shapeIndex == 10):  # Sphere
        ctrl = pm.curve(d=1, p=[[0.0, 0.9985206109894071, 0.0],
                                [-0.3821168629752589, 0.9225132220808937, 0.0],
                                [-0.7060609136748877, 0.7060609136748877, 0.0],
                                [-0.9225132220808937, 0.3821168629752589, 0.0],
                                [-0.9985206109894071, 0.0, 0.0],
                                [-0.9225132220808937, -0.3821168629752589, 0.0],
                                [-0.7060609136748877, -0.7060609136748877, 0.0],
                                [-0.3821168629752589, -0.9225132220808937, 0.0],
                                [0.0, -0.9985206109894071, 0.0],
                                [0.3821168629752589, -0.9225132220808937, 0.0],
                                [0.7060609136748877, -0.7060609136748877, 0.0],
                                [0.9225132220808937, -0.3821168629752589, 0.0],
                                [0.9985206109894071, 0.0, 0.0],
                                [0.9225132220808937, 0.3821168629752589, 0.0],
                                [0.7060609136748877, 0.7060609136748877, 0.0],
                                [0.3821168629752589, 0.9225132220808937, 0.0],
                                [0.0, 0.9985206109894071, 0.0],
                                [0.0, 0.9225132220808937, 0.3821168629752589],
                                [0.0, 0.7060609136748877, 0.7060609136748877],
                                [0.0, 0.3821168629752589, 0.9225132220808937],
                                [0.0, 0.0, 0.9985206109894071],
                                [0.0, -0.3821168629752589, 0.9225132220808937],
                                [0.0, -0.7060609136748877, 0.7060609136748877],
                                [0.0, -0.9225132220808937, 0.3821168629752589],
                                [0.0, -0.9985206109894071, 0.0],
                                [0.0, -0.9225132220808937, -0.3821168629752589],
                                [0.0, -0.7060609136748877, -0.7060609136748877],
                                [0.0, -0.3821168629752589, -0.9225132220808937],
                                [0.0, 0.0, -0.9985206109894071],
                                [0.0, 0.3821168629752589, -0.9225132220808937],
                                [0.0, 0.7060609136748877, -0.7060609136748877],
                                [0.0, 0.9225132220808937, -0.3821168629752589],
                                [0.0, 0.9985206109894071, 0.0],
                                [-0.3821168629752589, 0.9225132220808937, 0.0],
                                [-0.7060609136748877, 0.7060609136748877, 0.0],
                                [-0.9225132220808937, 0.3821168629752589, 0.0],
                                [-0.9985206109894071, 0.0, 0.0],
                                [-0.9225132220808937, 0.0, 0.3821168629752589],
                                [-0.7060609136748877, 0.0, 0.7060609136748877],
                                [-0.3821168629752589, 0.0, 0.9225132220808937],
                                [0.0, 0.0, 0.9985206109894071],
                                [0.3821168629752589, 0.0, 0.9225132220808937],
                                [0.7060609136748877, 0.0, 0.7060609136748877],
                                [0.9225132220808937, 0.0, 0.3821168629752589],
                                [0.9985206109894071, 0.0, 0.0],
                                [0.9225132220808937, 0.0, -0.3821168629752589],
                                [0.7060609136748877, 0.0, -0.7060609136748877],
                                [0.3821168629752589, 0.0, -0.9225132220808937],
                                [0.0, 0.0, -0.9985206109894071],
                                [-0.3821168629752589, 0.0, -0.9225132220808937],
                                [-0.7060609136748877, 0.0, -0.7060609136748877],
                                [-0.9225132220808937, 0.0, -0.3821168629752589],
                                [-0.9985206109894071, 0.0, 0.0]], name=name)
    elif (shapeIndex == 11):  # Pin
        ctrl = pm.curve(d=1, p=[[2.1684043449705158e-19, -1.3945691170673763e-15, 0.003005327217121356],
                                [9.860761315262648e-32, -2.004693105784353e-15, 4.686786465999242], [4.440892098500628e-16, -2.0918536756010666e-15, 5.207206592530582],
                                [2.498001805406602e-16, -0.35131670380256175, 5.2835838845370775], [-1.942890293094024e-16, -0.6169354685036135, 5.507262844285326],
                                [0.0, -0.7497448508541406, 5.779871576478512], [6.38378239159465e-16, -0.7708328493508398, 6.045490341179567],
                                [9.43689570931383e-16, -0.7078050459013434, 6.318099073372754], [-2.498001805406602e-16, -0.5400458260901518, 6.569737903089546],
                                [1.942890293094024e-16, -0.3093768988497638, 6.716527220424334], [-2.218277644905342e-16, 0.0051716382962194215, 6.767764685734359],
                                [4.440892098500626e-16, 0.30574024045793685, 6.70731440402724], [2.7755575615628914e-16, 0.57135900515899, 6.534788065628881],
                                [-2.7755575615628914e-16, 0.7273070851812956, 6.283149235912098], [0.0, 0.7799347596737146, 5.96860069876611],
                                [-3.0531133177191805e-16, 0.7181483224937807, 5.66803209660439], [1.942890293094024e-16, 0.543399135190457, 5.416393266887606],
                                [1.3877787807814457e-17, 0.2917603054736712, 5.255624014568546], [-2.2188197459915848e-16, -0.001818329195913728, 5.206694242123616]],
                        name=name)
        """ctrl = pm.curve(d=1, p=[[1.7763568394002505e-15,0.0038280881825316637,0.0],[2.55351295663786e-15,5.969876352341488,0.0],
			[2.6645352591003757e-15,6.632770603914706,0.0],[0.44749580494623975,6.730057517392256,0.0],
			[0.7858323589221183,7.014972510214049,0.0],[0.9550006359100588,7.362212657715609,0.0],[0.9818618433614663,7.700549211691488,0.0],
			[0.9015790747559724,8.047789359193048,0.0],[0.6878928301396279,8.368318726117565,0.0],[0.3940742437921534,8.555294190156866,0.0],
			[-0.006587464863492877,8.620558809043885,0.0],[-0.3894419864677772,8.543559203904236,0.0],[-0.7277785404436563,8.32380075848916,0.0],
			[-0.9264201388762267,8.003271391564644,0.0],[-0.9934555610594796,7.602609682908996,0.0],[-0.9147540044829576,7.219755161304713,0.0],
			[-0.6921641663409318,6.899225794380197,0.0],[-0.3716347994164152,6.694443143289533,0.0],[0.0023161286621883885,6.632117988609765,0.0]],
			name=name)"""
    elif (shapeIndex == 12):  # Pyramid
        ctrl = pm.curve(d=1, k=[0, 4, 8, 12, 16, 24.485281, 32.970563, 36.970563, 45.455844, 53.941125, 57.941125, 66.426407, 74.911688],
                        p=[(1, 0, 1), (-1, 0, 1), (-1, 0, -1), (1, 0, -1), (1, 0, 1), (0, 2, 0), (-1, 0, 1), (-1, 0, -1), (0, 2, 0), (1, 0, -1), (1, 0, 1), (0, 2, 0),
                           (-1, 0, 1)], name=name)
    elif (shapeIndex == 13):  # Rhombus
        ctrl = pm.curve(d=1, p=[(1, 0, -1), (1, 0, 1),
                                (-1, 0, 1), (-1, 0, -1), (1, 0, -1)], name=name)
        spans = pm.getAttr(ctrl.name() + ".spans")
        pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True)
        pm.rotate([0, 45, 0], os=True)
        if forwardAxis == 'X':
            pm.rotate([0, 0, 90], os=True)

        pm.scale(0.9, 1.0, 1.1, r=True)
    elif (shapeIndex == 14):  # Eye
        ctrl = pm.curve(d=1, p=[[6.071532165918825e-18, 0.5272216477742069, 0.025428715370585504], [4.163336342344337e-17, 0.48847664917049466, 0.2066473287833691],
                                [1.3877787807814457e-16, 0.3948815959907002, 0.42004405003329703],
                                [6.938893903907228e-17, 0.29626436922565097, 0.5624911553606023], [5.551115123125783e-17, 0.2232145716219084, 0.6464984226048973],
                                [1.942890293094024e-16, 0.10998738533610847, 0.8072079773331294], [2.7755575615628914e-17, 0.022327628211618704, 0.9423501029000505],
                                [2.220446049250313e-16, -0.014197270590251955, 0.9715700219415487], [5.551115123125783e-17, -0.03611220987137452, 0.9313926332594898],
                                [1.3877787807814457e-16, -0.13107694675623857, 0.7852930380520059], [1.249000902703301e-16, -0.2516091128024125, 0.6318884630841491],
                                [8.326672684688674e-17, -0.37944625860895953, 0.4638739285955432], [4.163336342344337e-17, -0.47075850561363736, 0.2849019244663771],
                                [-3.2526065174565133e-19, -0.5255458538164428, -0.0036447760684022034],
                                [-6.245004513516506e-17, -0.4744109954938239, -0.26297155756168455], [-6.938893903907228e-17, -0.3429213598070892, -0.4967309098936578],
                                [-9.71445146547012e-17, -0.18221180507885812, -0.7122278128246949],
                                [-1.942890293094024e-16, -0.07263710867324534, -0.8656323877925531],
                                [-1.6653345369377348e-16, -0.017849760470439072, -0.9423346752764813],
                                [-5.551115123125783e-17, -0.0032398009496909666, -0.9679021044377915],
                                [-1.3877787807814457e-16, 0.018675138331431567, -0.9386821853962938], [-1.1102230246251565e-16, 0.09902991569554737, -0.7962350800689972],
                                [-1.1102230246251565e-16, 0.22686706150209798, -0.6501354848615135],
                                [-4.163336342344337e-17, 0.36566167694920454, -0.4930784200134712], [-7.632783294297951e-17, 0.4817195428921483, -0.24598747961881473],
                                [-4.336808689942018e-18, 0.5278340459289496, -0.03315486717607726],
                                [6.071532165918825e-18, 0.5272216477742069, 0.025428715370585504], [4.163336342344337e-17, 0.48847664917049466, 0.2066473287833691],
                                [1.3877787807814457e-16, 0.3948815959907002, 0.42004405003329703]],
                        name=name)
    elif (shapeIndex == 15):  # Diamond
        size = 3 * scale
        ctrl = pm.curve(d=1, name=name, p=[(size, 0, -size), (size, 0, size), (-size, 0, size),
                                           (-size, 0, -size), (size, 0, -size), (0, size, 0),
                                           (-size, 0, size), (0, -size, 0), (size, 0, -size),
                                           (size, 0, size), (0, size, 0), (-size, 0, -size),
                                           (0, -size, 0), (size, 0, size)])

    # if hasattr(scale, '__iter__'):
    """if is_iterable(scale):
		spans = pm.getAttr(ctrl + ".spans")
		pm.select(ctrl + ".cv[0:" + str(spans) + "]", r=True )
		pm.scale(scale[0], scale[1], scale[2], r=True)
	else:
		if scale != 1.0:
			spans = pm.getAttr(ctrl + ".spans")
			pm.select(ctrl + ".cv[0:" + str(spans) + "]", r=True )
			pm.scale(scale , scale , scale, r=True)
	"""
    worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    if worldUpAxis == 'Z':
        spans = pm.getAttr(ctrl.name() + ".spans")
        pm.select(ctrl.name() + ".cv[0:" + str(spans) + "]", r=True)
        pm.rotate([90, 0, 0], os=True)

    ctrl.setAttr("visibility", cb=True)

    return ctrl


def setRGBColor(ctrl, color=(1, 1, 1)):
    shape = pm.listRelatives(ctrl, shapes=True)[0]
    rgb = ("R", "G", "B")
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideRGBColors", 1)
    for channel, color in zip(rgb, color):
        cmds.setAttr(shape + ".overrideColor%s" % channel, color)


def colorControls(ctrls, positionBased=True):
    for actrl in ctrls:
        shapes = pm.listRelatives(str(actrl), shapes=True)
        if shapes:
            if positionBased:
                worldUpAxis = pm.upAxis(q=True, axis=True).upper()
                if worldUpAxis == 'Z':
                    ctrlPosX = pm.xform(actrl, q=True, ws=True, rp=True)[1]
                else:
                    ctrlPosX = pm.xform(actrl, q=True, ws=True, rp=True)[0]

                if ctrlPosX > 0.1:
                    if (actrl.lower().find('microcon') > 0):
                        setRGBColor(actrl, (0.3, 0.0, 0.8))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (0.4, 0.4, 1.0))
                    else:
                        setRGBColor(actrl, (0.0, 0.0, 1.0))
                elif ctrlPosX < -0.1:
                    if (actrl.lower().find('microcon') > 0):
                        setRGBColor(actrl, (0.8, 0.2, 0.0))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (1.0, 0.4, 0.0))
                    else:
                        setRGBColor(actrl, (1.0, 0.0, 0.0))
                else:
                    if (actrl.lower().find('micro_con') > 0):
                        setRGBColor(actrl, (0.4, 0.2, 0.0))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (0.3, 1.0, 0.0))
                    else:
                        setRGBColor(actrl, (1.0, 1.0, 0.0))
            else:

                if (actrl.find('l_') == 0):
                    if (actrl.lower().find('microcon') > 0):
                        setRGBColor(actrl, (0.3, 0.0, 0.8))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (0.4, 0.4, 1.0))
                    else:
                        setRGBColor(actrl, (0.0, 0.0, 1.0))
                elif (actrl.find('r_') == 0):
                    if (actrl.lower().find('microcon') > 0):
                        setRGBColor(actrl, (0.8, 0.2, 0.0))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (1.0, 0.4, 0.0))
                    else:
                        setRGBColor(actrl, (1.0, 0.0, 0.0))
                elif (actrl.find('c_') == 0):
                    if (actrl.lower().find('micro_con') > 0):
                        setRGBColor(actrl, (0.4, 0.2, 0.0))
                    elif (actrl.lower().find('fkcon') > 0):
                        setRGBColor(actrl, (0.3, 1.0, 0.0))
                    else:
                        setRGBColor(actrl, (1.0, 1.0, 0.0))


def makeControl(sobj, newscale, constrainObj=None, parentObj=None, pivotObj=None, worldOrient=False, shape=0, rotateShape=[0, 0, 0], translateShape=[0, 0, 0],
                ctrlName=False, hideAttributes=[0, 0, 1], separateRotateOrient=False, controlSuffix='_CON',
                forwardAxis='X'):
    if isinstance(newscale, int):
        newscale = float(newscale)

    if isinstance(newscale, float):
        tscale = (newscale, newscale, newscale)
    else:
        tscale = newscale

    if ctrlName == False:
        ctrlName = getNiceControllerName(sobj.name(), controlSuffix)

    # print("     ctrl Namne is: "+ctrlName)
    posctrl = makeNurbsShape(shape, name=ctrlName, forwardAxis=forwardAxis).name()

    spans = pm.getAttr(posctrl + ".spans")
    pm.select(posctrl + ".cv[0:" + str(spans) + "]", r=True)
    pm.move(translateShape, os=True, r=True)
    pm.scale(tscale[0], tscale[1], tscale[2], r=True)
    # worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    # if worldUpAxis == 'Z':
    #    rotateShape = [rotateShape[2], rotateShape[1], rotateShape[0]]
    pm.rotate(rotateShape, os=True, pivot=pm.xform(posctrl, q=1, ws=1, t=1))  # 90 0 0

    if (pivotObj is None):
        pivotObj = sobj
    pmposctrl = pm.PyNode(posctrl)

    pm.parent(pmposctrl, pivotObj, r=True)
    pm.parent(pmposctrl, w=True)
    if (worldOrient is True):
        pm.rotate(pmposctrl, (0, 0, 0), a=True)

    if separateRotateOrient:
        pmposctrl.rename(pmposctrl.name() + '_t_')
        ctrlJoint = pm.joint(pmposctrl, name=ctrlName)
        pm.parent(ctrlJoint, w=True)
        shape = pm.listRelatives(pmposctrl, shapes=True)[0]
        pm.parent(shape, ctrlJoint, r=True, s=True)  # Move shape to joint
        pm.delete(pmposctrl)
        jointTransform = pm.xform(pivotObj, q=True, ws=True, rotation=True)
        # print ('*'*20)
        # print ('************************************************* joint Transform : ' + str(jointTransform))
        pm.setAttr(ctrlJoint.name() + '.jointOrient', jointTransform)
        pm.setAttr(ctrlJoint.name() + '.drawStyle', 2)  # hide joint
        pmposctrl = ctrlJoint

    """Create Group node to zero CTRL transforms"""
    InhGrp = pm.group(em=True, n=str(pmposctrl.name()) + "_Grp")

    pm.parent(InhGrp, pivotObj, r=True)
    pm.parent(InhGrp, w=True)
    if (worldOrient is True):
        pm.rotate(InhGrp, (0, 0, 0), a=True)

    CtrlINH = pm.group(em=True, n=str(pmposctrl.name()) + "_INH")
    pm.parent(CtrlINH, InhGrp, r=True)
    pm.parent(pmposctrl, CtrlINH)

    if (parentObj is not None):
        pm.parentConstraint(parentObj, CtrlINH, mo=True, weight=1).setAttr('interpType', DEFAULT_INTERPTYPE)
    if (constrainObj is not None):
        pm.parentConstraint(pmposctrl, constrainObj, mo=True, weight=1).setAttr('interpType', DEFAULT_INTERPTYPE)

    lockAndHideAttributes(pmposctrl, hideTranslation=hideAttributes[0], hideRotation=hideAttributes[1], hideScale=hideAttributes[2])

    return pmposctrl, InhGrp

def getMayaSafeName(moduleName):
    """
    Removes bad characters from module labels to create a display name that can be used in Maya
    
    :param str moduleName: Name of the module to create a display version for

    """

    niceName = re.sub(r"[^\w]", "_", moduleName)
    return niceName

def getNiceControllerName(jointName="joint", suffix=""):
    # printdebug("  getNiceControllerName jointName: "+ str(jointName) + '  ' + suffix)
    ctrlName = jointName.replace("_RigJnt", "")
    ctrlName = ctrlName.replace("_rigjnt", "")
    ctrlName = ctrlName.replace("_CON", "")
    ctrlName = ctrlName.replace("_transform", "")
    ctrlName = ctrlName + suffix
    # print("new name: " + ctrlName)
    return ctrlName


def mirrorName(name, leftPrefix='l_', rightPrefix='r_'):
    # print("Mirror name: {}".format(name))
    src = name
    bSrcWasCenter = False

    namespacesplit = ['']
    if (src.find(':') > -1):
        namespacesplit = name.split(':')
        src = namespacesplit[-1]

    splitnames = ['']
    splitnames = src.split(u"\u007C")  # split |
    # print("splitnames: {}".format(splitnames))
    # if (len(splitnames) > 1):
    #    src = splitnames[-1]
    if not splitnames:
        splitnames = [src]

    for i, dest in enumerate(splitnames):
        src = dest
        if src.find(leftPrefix) == 0:
            dest = src.replace(leftPrefix, rightPrefix, 1)
        elif (src.find('_' + leftPrefix) > 0):
            dest = src.replace('_' + leftPrefix, '_' + rightPrefix, 1)
        elif src.find(rightPrefix) == 0:
            dest = src.replace(rightPrefix, leftPrefix, 1)
        # bSrcWasRight = True
        elif (src.find('_' + rightPrefix) > 0):
            dest = src.replace('_' + rightPrefix, '_' + leftPrefix, 1)
        # bSrcWasRight = True
        else:
            continue

        splitnames[i] = dest
    # dest = ''
    # bSrcWasCenter = True

    # splitnames[-1] = dest
    joinedName = u"\u007C".join(splitnames)
    namespacesplit[-1] = joinedName
    jointsNamespaceName = ':'.join(namespacesplit)

    printdebug("Mirroring name src: " + name + " dest: " + dest)

    if not bSrcWasCenter:
        return jointsNamespaceName  # dest
    else:
        return name


""" 
	Find the side of a name by looking at the prefix 
	Returns:
	-1 : Right
	0 : Center
	1 : Left
"""


def getPrefixSide(name, leftPrefix='l_', rightPrefix='r_'):
    src = name

    print("getPrefixSide")
    print(f"left: {leftPrefix} right: {rightPrefix}")
    

    if (src.find(':') > -1):
        src = name.split(':')[1]

    if src.find(leftPrefix) == 0:
        return 1
    elif (src.find('_' + leftPrefix) > 0):
        return 1
    elif src.find(rightPrefix) == 0:
        return -1
    elif (src.find('_' + rightPrefix) > 0):
        return -1
    else:
        return 0


def getSidePrefixString(ctrlName):
    sideName = ctrlName[0:2]
    isLeft = sideName.lower().find("l_")
    isRight = sideName.lower().find("r_")
    namePrefix = ""
    if isLeft >= 0:
        namePrefix = "l_"
    elif isRight >= 0:
        namePrefix = "r_"

    return namePrefix


def lockAndHideAttributes(obj, hideTranslation=False, hideRotation=False, hideScale=True):
    if isinstance(obj, basestring):
        objName = obj
    else:
        objName = obj.name()

    if hideTranslation:
        cmds.setAttr(objName + ".tx", lock=True, keyable=False)
        cmds.setAttr(objName + ".ty", lock=True, keyable=False)
        cmds.setAttr(objName + ".tz", lock=True, keyable=False)
    if hideRotation:
        cmds.setAttr(objName + ".rx", lock=True, keyable=False)
        cmds.setAttr(objName + ".ry", lock=True, keyable=False)
        cmds.setAttr(objName + ".rz", lock=True, keyable=False)
    if hideScale:
        cmds.setAttr(objName + ".sx", lock=True, keyable=False)
        cmds.setAttr(objName + ".sy", lock=True, keyable=False)
        cmds.setAttr(objName + ".sz", lock=True, keyable=False)

    cmds.setAttr(objName + ".visibility", keyable=False, cb=True)


def addToSet(node, setName):
    parentSet = pm.ls(setName)
    if not parentSet:
        pm.sets(node, name=setName)
    else:
        pm.sets(setName, include=node)


def getShortName(node):
    a = node.name()
    # print(a)
    if (a.find(':') > -1):
        split = a.split(u":")
        a = split[-1]
    # print("new a: {}".format(a))

    if (re.match(u"\u007C", a)):
        split = a.split(u"\u007C")
        a = split[-1]  # split[0] + "(...)" +
    return a


def getShortNames(nodes):
    shortened = []
    for a in nodes:
        a = getShortName(a)
        shortened.append(a)

    return (shortened)


def createConstrainedIdentityChain(startJnt=None, suffix=''):
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\ncreateConstrainedIdentityChain: {}".format(startJnt))
    startJnt.setAttr('visibility', True)  # Set visible
    pm.currentTime(0, u=True)

    chain = startJnt.listRelatives(ad=True, type='joint')
    chain.reverse()
    chain.insert(0, startJnt)

    ctrls = []
    for i, jnt in enumerate(chain):
        # Duplicate one joint at a time
        dup = jnt.duplicate(parentOnly=True)[0]

        # Freeze Rotation
        j = dup
        pm.makeIdentity(j, apply=True, t=1, r=1, s=1, n=0, pn=1)
        '''
		x = pm.xform(j, q=True, ro=True)
		attrs = ['X', 'Y', 'Z']
		for i, attr in enumerate(attrs):
			j.setAttr("jointOrient" + attr, x[i])
			offset = x[i] * -1.0
			keyTimes = pm.keyframe(j, query=True ,tc=True)
			if len(keyTimes) > 0:
				pm.keyframe(j, at="rotate" + attr, edit=True, time=timestartend, relative=True, valueChange=offset)
			else:
				j.setAttr("rotate" + attr, 0)'''

        ctrls.append(dup)

        # Constrain the original to the new duplicate
        pm.parentConstraint(jnt, dup).setAttr('interpType', DEFAULT_INTERPTYPE).setAttr('interpType', DEFAULT_INTERPTYPE)
        pm.scaleConstraint(jnt, dup)
        # pm.orientConstraint( dup, jnt ).setAttr('interpType', DEFAULT_INTERPTYPE)

        # If the parent is in the chain, it has already been duplicated
        if jnt.getParent() in chain:
            # We find the joint's parent's index in the chain
            jntIndex = chain.index(jnt.getParent())
            # And set the parent of the duplicate joint to the corresponding duplicate
            dup.setParent(ctrls[jntIndex])
        else:
            # Otherwise, it is the start of the joint chain,
            # so we parent the first control to the world
            dup.setParent(world=True)

        if len(suffix) > 0:  # i == 0 and
            dup.rename(getShortNames([jnt])[0] + '_' + suffix)
        else:
            dup.rename(getShortNames([jnt])[0])  # +'_frozenDriver' )
    # Add suffix to duplicated root joint

    return ctrls[0]


def getGroundPlaneControl(joint, group, conScale):
    groundPlaneControl = (pm.ls('GroundPlane_EngineIKCON') or [None])[0]
    if not groundPlaneControl:
        groundPlaneControl, groundPlaneControlGrp = makeControl(joint,
                                                                conScale * 2.0,
                                                                constrainObj=None,
                                                                pivotObj=group,
                                                                worldOrient=True,
                                                                shape=9,
                                                                controlSuffix='_EngineIKCON',
                                                                ctrlName='GroundPlane_EngineIKCON',
                                                                forwardAxis=pm.upAxis(q=True, axis=True).upper())
        # cmds.setAttr(groundPlaneControl.name() + ".ry", lock=True, keyable=False)
        if group:
            pm.parent(groundPlaneControlGrp, group)

    return groundPlaneControl


def setParent(child, parent):
    '''Removes transform if one is created between the parent'''
    if not isPyNode(parent):
        parent = getPyNode(parent)

    matrix = pm.xform(child, q=True, ws=True, matrix=True)
    child.setParent(parent)
    check = child.getParent()
    if check and check != parent:
        print('"{}" != "{}"'.format(check, parent))
        pm.ungroup(check)
        pm.xform(child, a=True, ws=True, matrix=matrix)


def jointChainNotPlanar(joints, tolerance=0.001):
    """Returns an ordered dictionary of joint chains that are not planar"""
    badJoints = errorOD(separator="*", tab=1)
    jointSTR = "(" + " - ".join(str(joint) for joint in joints[::len(joints) - 1]) + ")"

    print('=' * 80)
    print(f"THE JOINTS: {joints}")
    print('=' * 80)

    print('=' * 80)
    print(f"THIS IS THE JOINT STRING: {jointSTR}")
    print('=' * 80)

    points = [x.worldMatrix.get().translate for x in joints]

    if len(points) < 4:
        printdebug('Chains less than 4 are always planar')
        return badJoints

    aim = (points[-1] - points[0]).normal()
    deltas = [x - points[0] for x in points[1:-1]]
    crosses = [aim.cross((x - points[0]).normal()) for x in points[1:-1]]
    normal = sum(crosses).normal()
    maxDistance = 0

    planar = True
    for delta in deltas:
        planeDistance = delta * normal
        maxDistance = max(maxDistance, abs(planeDistance))

        if abs(planeDistance) > tolerance:
            planar = False
            printdebug(f'Ideal plane distance {maxDistance} is outside tolerance {tolerance}')

    print('=' * 80)
    print(f"IS THIS CHAIN PLANAR: {planar}")
    print('=' * 80)

    if not planar:
        if not badJoints.get(jointSTR):
            badJoints[jointSTR] = f" {jointSTR}:"
        badJoints[jointSTR] += f" Out of tolerance"

    return badJoints


def jointChainNotAimed(joints, attributes=None, tolerance=0.0005):
    """Returns an ordered dictionary of bad joints that have more than one tx, ty, or tz values greater than tolerance"""
    badJoints = errorOD(separator="*", tab=1)

    if not attributes:
        attributes = ["tx", "ty", "tz"]

    print('=' * 80)
    print(f"THESE ARE THE JOINTS: {joints[1:]}")
    print('=' * 80)

    for joint in joints[1:]:
        sign = [int(abs(joint.getAttr(attr)) >= tolerance) for attr in attributes]

        if sum(sign) > 1:
            print('=' * 80)
            print(f"AXIS WITH A VALUE: {sign}")
            print('=' * 80)

            if not badJoints.get(joint):
                badJoints[joint] = f" {joint}: Use only one transform -"

            count = 0
            for attr in sign:
                if attr != 0:
                    badJoints[joint] += f" {attributes[count]}"
                count += 1

    return badJoints


def jointsAreTwisted(joints, tolerance=0.00000000003):
    """Returns an ordered dictionary of bad joints not aligned with the side axis"""
    badJoints = errorOD(separator="*", tab=1)

    points = [x.worldMatrix.get().translate for x in joints]
    aim = (points[-1] - points[0]).normal()
    crosses = [aim.cross((x - points[0]).normal()) for x in points[1:-1]]
    normal = sum(crosses).normal()

    startMatrix = joints[0].worldMatrix.get()
    axes = [pm.datatypes.Vector(x[:3]).normal() for x in startMatrix[:3]]

    sideIndex = 0
    maxDot = abs(normal.dot(axes[0]))

    for i, vec in enumerate(axes):
        if not i:
            continue
        check = abs(normal.dot(vec))

        if check > maxDot:
            sideIndex = i
            maxDot = check

    if maxDot < (1.0 - tolerance):
        printdebug(f'Parent joint {joints[0]} side axis is not within tolerance of ideal plane normal. MaxDot:{maxDot}')
        if not badJoints.get(joints[0]):
            badJoints[joints[0]] = f" {joints[0]}:"
        badJoints[joints[0]] += f" Parent side axis off by - {round(maxDot, 4)}"

    flexAxis = pm.datatypes.Vector(joints[0].worldMatrix.get()[sideIndex][:3]).normal()

    for joint in joints[1:-1]:
        vec = pm.datatypes.Vector(joint.worldMatrix.get()[sideIndex][:3]).normal()
        check = abs(flexAxis.dot(vec))
        if check < (1.0 - tolerance):
            printdebug(f'Child joint {joint} side axis is not within tolerance of ideal plane normal. Check:{check}')
            if not badJoints.get(joint):
                badJoints[joint] = f" {joint}:"
            badJoints[joint] += f" Child side axis off by - {round(check, 4)}"

    return badJoints


def jointChainIdealPlaneNormalAxisIndex(joints):
    points = [x.worldMatrix.get().translate for x in joints]
    aim = (points[-1] - points[0]).normal()
    crosses = [aim.cross((x - points[0]).normal()) for x in points[1:-1]]
    normal = sum(crosses).normal()

    startMatrix = joints[0].worldMatrix.get()
    axes = [pm.datatypes.Vector(x[:3]).normal() for x in startMatrix[:3]]

    sideIndex = 0
    maxDot = abs(normal.dot(axes[0]))

    for i, vec in enumerate(axes):
        if not i:
            continue
        check = abs(normal.dot(vec))

        if check > maxDot:
            sideIndex = i
            maxDot = check

    return sideIndex


def jointChainFlexAxisMatchesSideAxis(joints, flexAxis):
    badJoints = errorOD(separator="*", tab=1)

    flexAxisStr = str(flexAxis)
    flexAxisInd = 0
    if re.findall("y", flexAxisStr, re.IGNORECASE):
        flexAxisInd = 1
    elif re.findall("z", flexAxisStr, re.IGNORECASE):
        flexAxisInd = 2

    sideIndex = jointChainIdealPlaneNormalAxisIndex(joints)
    idealAxis = ["X", "Y", "Z"]
    jointSTR = "(" + " - ".join(str(joint) for joint in joints[::len(joints) - 1]) + ")"

    print('=' * 80)
    print(f"THIS IS THE JOINT CHAIN: {jointSTR}")
    print('=' * 80)
    print(f"THIS IS SIDE INDEX: {sideIndex}")
    print('=' * 80)
    print(f"THIS IS FLEX AXIS INDEX: {flexAxisInd}")
    print('=' * 80)

    if sideIndex != flexAxisInd:
        if not badJoints.get(jointSTR):
            badJoints[jointSTR] = f" {jointSTR}:"
        badJoints[jointSTR] += f" Ideal plane axis is '{idealAxis[sideIndex]}'"

    return badJoints


def jointsWithNonZeroAttributes(joints, attributes=None, tolerance=0.0005):
    """Returns an ordered dictionary of bad joints with transforms in their rotate or jointOrient"""
    badJoints = errorOD(separator="*", tab=1)

    if not attributes:
        attributes = ["rotate", "jointOrient"]

    for joint in joints:
        for attr in attributes:
            if any(1 for i in map(abs, getattr(joint, attr).get()) if i >= tolerance):
                if not badJoints.get(joint):
                    badJoints[joint] = f" {joint}:"
                badJoints[joint] += f" {attr}"

    return badJoints


def emptyModuleField(self, keys=None):
    """Returns an ordered dictionary of module values that are missing"""
    missingValues = errorOD(separator="*", tab=1)

    if not keys:
        keys = list(vars(self).keys())

    dataMembers = vars(self)

    deleteKey = "_nodeAttributes"
    if deleteKey in dataMembers:
        del dataMembers[deleteKey]

    print('=' * 80)
    print(f"THESE ARE THE KEYS: {keys}")
    print('=' * 80)
    print(f"THESE ARE THE MISSING VALUES:")

    for key in keys:
        if key in dataMembers and not dataMembers[key]:
            print(f"{key}")
            if not missingValues.get(key):
                missingValues[key] = f" The '{key}' field is empty"
            missingValues[key] += f" "

    print('=' * 80)

    return missingValues
