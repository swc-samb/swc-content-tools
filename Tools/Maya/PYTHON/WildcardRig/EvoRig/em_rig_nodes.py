# Wrapping some maya utlity nodes for use in common vector operations via rigging nodes
# Cleaned up inconsistent input and output naming.
# Arnold has convenient vector operations nodes, but may not be supported in the future.


import sys, os
import re
from collections import OrderedDict as od
import maya.cmds as mc
import pymel.core as pm

from EvoRig import mb_rig_utilities as util

DEBUG = False

def is_iterable(value):
	'''python 3 strings are iterables (for the love of all thats holy why?!) so old iterable checks no longer work *sigh*'''
	return hasattr(value, '__iter__') and not isinstance(value, str) and not issubclass(type(value), pm.general.PyNode)


# returns valid maya name to cut down on invalid character spam
VALID_NAME = lambda x: '_'.join(od((a,a) for a in (re.findall('[A-Z0-9]+', str(x).split('|')[-1], re.IGNORECASE))))

# returns number of descendants
HISORT = lambda x: -len(pm.listRelatives(x, ad=True))

# input lookups to unify referring to inputs by "input"
INPUTS = {pm.nodetypes.PointMatrixMult:['inMatrix', 'inPoint'],
          pm.nodetypes.DistanceBetween:['point1', 'point2'],
          pm.nodetypes.PlusMinusAverage:['input1','input2'],
          pm.nodetypes.MultiplyDivide:['input1','input2'],
          pm.nodetypes.BlendColors:['color1','color2'],
          pm.nodetypes.VectorProduct:['input1','input2'],
          pm.nodetypes.FourByFourMatrix:[x for xl in [['{}{}'.format(x,y) for y in range(4)] for x in range(4)] for x in xl],
          pm.nodetypes.MultMatrix:['matrixIn[0]', 'matrixIn[1]'],
          }
          
def getInputAttributes(item):
    '''Return the Pynode attributes for inputs'''
    if isinstance(item, pm.general.Attribute):
        return item
    if INPUTS.get(type(item)):
        return [getattr(item,n) for n in INPUTS[type(item)]] 

def getInputs(item, nodeType=None):
    '''Return nodes connected to input attributes'''
    nodes = pm.ls(pm.connectionInfo(x,sfd=True) for x in getInputAttributes(item))
    return [x.node() for x in nodes if not nodeType or isinstance(x.node(),nodeType)]


# output lookups to unify referring to outputs by "output"
OUTPUT = {pm.nodetypes.PointMatrixMult:'output',
          pm.nodetypes.DistanceBetween:'distance',
          pm.nodetypes.PlusMinusAverage:'output3D',
          pm.nodetypes.MultiplyDivide:'output',
          pm.nodetypes.BlendColors:'output',
          pm.nodetypes.VectorProduct:'output',
          pm.nodetypes.FourByFourMatrix:'output',
          pm.nodetypes.MultMatrix:'matrixSum',
          pm.nodetypes.Transform:'worldMatrix[0]',
          pm.nodetypes.Joint:'worldMatrix[0]',
          }

def getOutputAttribute(item):
    '''Return output attribute'''
    if isinstance(item, pm.general.Attribute):
        return item
    if OUTPUT.get(type(item)):
        return getattr(item,OUTPUT[type(item)]) 

def getOutputs(item, nodeType=None):
    '''Return nodes connected to output attribute'''
    nodes = pm.ls(pm.connectionInfo(getOutputAttribute(item),dfs=True))
    return [x.node() for x in nodes if isinstance(x.node(),nodeType) or not nodeType]


def getWorldPointNode(item, normalize=True):
    '''Create Node that outputs world position if necessary'''

    # skip non transform nodes 
    if not isinstance(item, pm.nodetypes.Transform) and not isinstance(item, pm.nodetypes.Joint):
        return item
    
    node = (getOutputs(item,pm.nodetypes.PointMatrixMult) or [None])[0]
    if not node:
        node = pm.createNode('pointMatrixMult', ss=True, name='{}_WorldPoint'.format(VALID_NAME(item)))
        pm.connectAttr(getOutputAttribute(item), getInputAttributes(node)[0])
    return node

    
def getDistanceNode(start_node,end_node):
    '''Create node if necessary that return distance between two nodes or points'''

    name = VALID_NAME('_'.join(str(x) for x in (start_node,end_node)))

    start,end = list(map(getWorldPointNode, (start_node,end_node)))
    start_checks = getOutputs(start, pm.nodetypes.DistanceBetween)
    end_checks = getOutputs(end, pm.nodetypes.DistanceBetween)

    node = ([x for x in start_checks if x in end_checks] or [None])[0]
    if not node:
        node = pm.createNode('distanceBetween', ss=True, name='{}_Distance'.format(name))
        node_inputs = getInputAttributes(node)
        pm.connectAttr(getOutputAttribute(start), node_inputs[0], f=True)
        pm.connectAttr(getOutputAttribute(end), node_inputs[1], f=True)
        
    return node


def getLengthNode(vector):
    '''Create node if necessary that returns the length of a vector'''

    vector_checks =  getOutputs(vector, pm.nodetypes.DistanceBetween)
    node = ([x for x in vector_checks if len(getInputs(x))<2] or [None])[0]
    if not node:
        node = pm.createNode('distanceBetween', ss=True, name='{}_Length'.format(VALID_NAME(vector)))
        pm.connectAttr(getOutputAttribute(vector), getInputAttributes(node)[1], f=True)
        
    return node


def getNormalizeNode(item, attribute='output'):
    '''Create node if necessary that returns normalized vector'''
    
    length = getLengthNode(item)
    
    item_checks = getOutputs(item, pm.nodetypes.MultiplyDivide)
    length_checks = getOutputs(length, pm.nodetypes.MultiplyDivide)
    divide = ([x for x in item_checks if x in length_checks] or [None])[0]

    if not divide:
        divide = pm.createNode('multiplyDivide', ss=True, name='{}_Normalize'.format(VALID_NAME(item)))
        divide_inputs = getInputAttributes(divide)
        pm.connectAttr(getOutputAttribute(item), divide_inputs[0], f=True)
        length_out = getOutputAttribute(length)
        for attr in divide_inputs[1].children():
            pm.connectAttr(length_out, attr, f=True)

    if divide.operation.get() != 2:
        divide.setAttr('operation',2)
    
    return divide


def getWorldDeltaNode(start_node, end_node, normalize=True):
    '''Create node if necessary that returns delta vector of two points or nodes world positions'''
    
    name = VALID_NAME('_'.join(str(x) for x in (start_node, end_node)))
    
    start,end = list(map(getWorldPointNode, (start_node,end_node)))
    start_checks = getOutputs(start, pm.nodetypes.PlusMinusAverage)
    end_checks = getOutputs(end, pm.nodetypes.PlusMinusAverage)

    subtract = ([x for x in start_checks if x in end_checks] or [None])[0]
    if not subtract:
        subtract = pm.createNode('plusMinusAverage', ss=True, name='{}_Delta'.format(name)) 
        pm.connectAttr(getOutputAttribute(end), subtract.input3D[0], f=True)
        pm.connectAttr(getOutputAttribute(start), subtract.input3D[1], f=True)

    if subtract.operation.get() != 2:
        subtract.setAttr('operation',2)
        
    if normalize:
        return getNormalizeNode(subtract)
    else:
        return subtract


def getLerpPositionNode(start_node,end_node, blend=0.5):
    '''Create node if necessary that returns linear interpolation of two points or node world positions at given blend'''

    if not 0<=blend<=1:
        pm.warning('getLerpPositionNode blend {} outside 0-1 for "{}"->"{}"'.format(blend,start_node,end_node))

    blend = max(0,min(1,blend))

    name = VALID_NAME('_'.join(str(x) for x in (start_node,end_node)) + '_{}'.format(blend))
    
    start,end = list(map(getWorldPointNode, (start_node,end_node)))
    start_checks = getOutputs(start, pm.nodetypes.BlendColors)
    end_checks = getOutputs(end, pm.nodetypes.BlendColors)

    blend_node = ([x for x in start_checks if x in end_checks] or [None])[0]
    if DEBUG:
        print('blends found', blend_node,)
        if blend_node:
            print(abs(blend_node.blender.get() - blend) > 0.001, blend_node.blender.get(), blend)
            
    if not blend_node or abs(blend_node.blender.get() - blend) > 0.001:
        if blend_node and DEBUG:
            print('new blend')
        blend_node = pm.createNode('blendColors', ss=True, name=name)
        blend_inputs = getInputAttributes(blend_node)
        pm.connectAttr(getOutputAttribute(start), blend_inputs[1], f=True)
        pm.connectAttr(getOutputAttribute(end), blend_inputs[0], f=True)
        blend_node.setAttr('blender',blend)
        
    return  blend_node    


def getCrossNode(vector1, vector2, normalize=True):
    '''Create node if necessary that returns cross product of two vectors'''
    vector1_checks = getOutputs(vector1, pm.nodetypes.BlendColors)
    vector2_checks = getOutputs(vector2, pm.nodetypes.BlendColors)

    cross_node = ([x for x in vector1_checks if x in vector2_checks] or [None])[0]
    if not cross_node:
        name = VALID_NAME('_'.join(str(x) for x in (vector1,vector2)))
        cross_node = pm.createNode('vectorProduct', ss=True, name='{}_Cross'.format(name))
        cross_inputs = getInputAttributes(cross_node)
        pm.connectAttr(getOutputAttribute(vector1), cross_inputs[0], f=True)
        pm.connectAttr(getOutputAttribute(vector2), cross_inputs[1], f=True)

    if cross_node.operation.get() != 2:        
        cross_node.setAttr('operation',2)

    if bool(cross_node.normalizeOutput.get()) != bool(normalize):        
        cross_node.setAttr('normalizeOutput',normalize)

    return cross_node
        
    
def getAimMatrixNode(aim_node, up_node, side_node, offset_node):
    '''Create node if necessary that returns matrix constructed of given aim, up, side, and offset nodes vector outputs'''
    
    name = VALID_NAME('_'.join(str(x) for x in (aim_node,up_node,offset_node)))

    aim_checks = getOutputs(aim_node, pm.nodetypes.FourByFourMatrix)
    up_checks = getOutputs(up_node, pm.nodetypes.FourByFourMatrix)
    side_checks = getOutputs(side_node, pm.nodetypes.FourByFourMatrix)
    offset_checks = getOutputs(offset_node, pm.nodetypes.FourByFourMatrix)
    up_node = getCrossNode(aim_node,side_node)

    matrix_node = ([x for x in aim_checks if x in up_checks and x in side_checks and x in offset_checks] or [None])[0]

    if not matrix_node:
        matrix_node = pm.createNode('fourByFourMatrix', ss=True, name='{}_AimMatrix'.format(name))
        for x, node in enumerate([aim_node,side_node,up_node,offset_node]):
            node_out = getOutputAttribute(node)
            for y,n in enumerate(node_out.children()):
                pm.connectAttr(n, '{}.in{}{}'.format(matrix_node,x,y), f=True)
    
    return matrix_node


def deltaDot(target, sources, clamp=False):
    '''Find the dot product of given targets world position relative to sources[0] and sources world position delta vector'''

    source_points = [pm.datatypes.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in sources]
    target_point = pm.datatypes.Vector(pm.xform(target,q=True,ws=True,sp=True))
    s_delta = (source_points[-1] - source_points[0])
    t_delta = target_point - source_points[0]
    if clamp:
        if DEBUG:
            print(s_delta.normal().dot(t_delta) / s_delta.length())
        s_length = s_delta.length()
        if s_length<sys.float_info.epsilon:
            return 0
        return max(0,min(1,s_delta.normal().dot(t_delta) * (1.0/s_delta.length())))
    else:
        return s_delta.normal().dot(t_delta)


def linesInteresection(pointA1, pointA2, pointB1, pointB2):
    '''Returns nearest points between two lines given their points. 
       Parallel and coincindent lines return None
       Returns [lineA near point, lineB near point]'''

    #get deltas
    deltaBA = pointA1-pointB1
    deltaA = pointA2-pointA1
    deltaB = pointB2-pointB1

    #lineBA or lineB is zero length
    if max(deltaBA.dot(deltaBA), deltaB.dot(deltaB)) < sys.float_info.epsilon:
        return None
    
    dotAA = deltaA.dot(deltaA)
    dotBB = deltaB.dot(deltaB)
    dotAB = deltaA.dot(deltaB)

    denominator = dotAA * dotBB - dotAB * dotAB    
    # parallel
    if abs(denominator) < sys.float_info.epsilon:
        return None

    dotBAA = deltaBA.dot(deltaA)
    dotBAB = deltaBA.dot(deltaB)
    numerator = dotAB * dotBAB - dotBB * dotBAA
    mu_a = numerator / denominator
    mu_b = (dotBAB + dotAB * mu_a) / dotBB
    
    return (pointA1 + deltaA * mu_a, pointB1 + deltaB * mu_b)


def getAimBlendValue(target, sources, parent=None):
    '''To find blend value for linear interpolation for a joint
       Firs try line intersection of joints aim again source position delta. 
       If that fails, return dotproduct of source position delta and target position.'''

    points = []
    A1,A2 = [pm.datatypes.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in sources]
    B1,B2 = [pm.datatypes.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in [target,getAimEndNode(target,parent=parent)]]
    i_points = linesInteresection(A1,A2,B1,B2)
    if not i_points:
        return deltaDot(target,sources,clamp=True)
    else:
        return (i_points[0] - A1).length() / (A2-A1).length()


def getNearestType(target, nodetype=pm.nodetypes.Joint, min_distance = 0.001):
    point = pm.datatypes.Vector(pm.xform(target,q=True,ws=True,sp=True))
    closest_distance = -1
    for item in pm.ls(type=nodetype):
        current_distance = (pm.datatypes.Vector(pm.xform(item,q=True,ws=True,sp=True)) - point).length()
        if current_distance > min_distance and (closest_distance<0 or current_distance<closest_distance):
            closest_distance = current_distance
    return closest_distance



def getAimEndNode(target,parent=None,):
    '''Get primary child for aim vector (has most descendants) must be seperated from parent joint by at least 1 unit'''
    
    aim_start = pm.datatypes.Vector(pm.xform(target,q=True,ws=True,sp=True))
    aim_end = aim_start
    aim_end_node = None

    # try primary child (with most descendants) first
    transform_types = (pm.nodetypes.Transform, pm.nodetypes.Joint)
    get_joint_children = lambda x: sorted((x for x in pm.listRelatives(x,c=True) if type(x) in transform_types),key=HISORT)
    target_children = get_joint_children(target)
    if target_children:
        aim_end_node = target_children[0]
        aim_end = pm.datatypes.Vector(pm.xform(aim_end_node,q=True,ws=True,sp=True))

        # if theres no distance between joints, keep moving down hierarchy
        while (aim_start-aim_end).length()<(1-sys.float_info.epsilon) and target_children:
            aim_end_node = target_children[0]
            aim_end = pm.datatypes.Vector(pm.xform(aim_end_node,q=True,ws=True,sp=True))
            target_children = get_joint_children(aim_end_node)
            

    # if theres no children with distance from parent, use x axis instead
    if (aim_start-aim_end).length()<(1-sys.float_info.epsilon) :
        near_distance = getNearestType(target)
        aim = pm.datatypes.Vector(pm.xform(target,q=True,ws=True,matrix=True)[:3])

        #check node parent direction to guess axis sign
        node_parent = target.getParent()
        parent_delta = aim_start - aim_start
        while node_parent and parent_delta.length() < sys.float_info.epsilon:
            parent_delta = aim_start - pm.datatypes.Vector(pm.xform(node_parent,q=True,ws=True,sp=True))
            node_parent = node_parent.getParent()
        
        # if its more than 90 degrees away from the parent child direction flip it 180
        if parent_delta.length() > sys.float_info.epsilon:
            if parent_delta.dot(aim) < 0:
                aim *= -1

        aim_end = aim_start + aim * near_distance
        
        aim_end_node = (pm.ls('{}_End'.format(VALID_NAME(target))) or [None])[0]
        if not aim_end_node:
            aim_end_node = pm.createNode('transform',ss=True,name='{}_End'.format(VALID_NAME(target)),parent=parent)

        pm.move(aim_end[0],  aim_end[1], aim_end[2], aim_end_node,a=True,ws=True)

        if not pm.listConnections(aim_end_node,type='parentConstraint'):
            pm.parentConstraint(target,aim_end_node,mo=True).setAttr('interpType',util.DEFAULT_INTERPTYPE)

        aim_end_node.setAttr('displayHandle',DEBUG)

    #print('aim_end_node "{}" -> "{}"'.format(target, aim_end_node))
    return aim_end_node



def membraneAimConstraint(target, sources, parent=None):
    '''Constrain target to aim at line between source children while up axis is cross of aim and source delta'''

    # get source ends for aiming
    source_ends  = [getAimEndNode(x,parent=parent) for x in sources]

    # if source aims are > 90 degrees flip them
    target_points = [pm.datatypes.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in [target, getAimEndNode(target,parent=parent)]]
    target_aim = target_points[1] - target_points[0]
    for n in range(len(sources)):
        source_points = [pm.datatypes.Vector(pm.xform(x,q=True,ws=True,sp=True)) for x in [sources[n],source_ends[n]]]
        source_aim = source_points[1] - source_points[0]
        if source_aim.dot(target_aim)<0:
            sources[n], source_ends[n] = source_ends[n], sources[n]
    
    if DEBUG :
        debugCurve(name = '{}_source_start'.format(target), points=(pm.xform(x,q=True,ws=True,sp=True) for x in sources))
        debugCurve(name = '{}_source_end'.format(target), points=(pm.xform(x,q=True,ws=True,sp=True) for x in source_ends))
        print('source start {} = {} -> {}'.format(target,sources[0], sources[1]))
        print('source end   {} = {} -> {}'.format(target,source_ends[0], source_ends[1]))


    blend1 = getAimBlendValue(target, sources, parent=parent)
    blend2 = getAimBlendValue(getAimEndNode(target,parent=parent), source_ends, parent=parent)

    if DEBUG:
        print('Blend1',blend1)
        print('Blend1',blend2)

    aim_start = getLerpPositionNode(*sources, blend1)
    aim_end = getLerpPositionNode(*source_ends, blend2)
    aim = getWorldDeltaNode(aim_start, aim_end)    

    aim_end_node = pm.createNode('transform',
                                 ss=True,
                                 parent=parent,
                                 name='{}_Target_End'.format(VALID_NAME(target)))                                 
    aim_end_node.setAttr('inheritsTransform', 0)

    if DEBUG:
        debugPosition(aim_start)
        debugPosition(aim_end)
        debugCurve(name = '{}_aim'.format(target), points=(getOutputAttribute(aim_start).get(), getOutputAttribute(aim_end).get()))

    
    pm.connectAttr(getOutputAttribute(aim_end), aim_end_node.translate)
    side = getWorldDeltaNode(*sources)
    up = getCrossNode(aim,side)
    
    aim_off_node = target
    aim_vector = target.worldInverseMatrix.get() * pm.datatypes.Vector(getOutputAttribute(aim).get())
    aim_con = pm.aimConstraint(aim_end_node, aim_off_node, 
                               mo=False,
                               wut='vector', 
                               aimVector=aim_vector.normal(), 
                               worldUpVector=getOutputAttribute(up).get())
    aim_con.setAttr('worldUpType',3)
    pm.connectAttr(getOutputAttribute(up), aim_con.worldUpVector)

    target.setAttr('displayLocalAxis',DEBUG )

    

def membraneConstraintMatrix(target, sources, parent=None):
    '''constrain target to aim at line between source children
       Replaced by more slightly more performant membraneAimConstraint function, but leaving in for reference'''

    source_ends  = [getAimEndNode(x,parent=parent) for x in sources]
    
    stay = pm.createNode('transform', ss=True, parent=parent, name='{}_membrane_stay'.format(VALID_NAME(target)))
    pm.xform(stay,a=True,ws=True,matrix=pm.xform(target,q=True,ws=True,matrix=True))
    pm.parentConstraint(target.getParent(),stay,mo=True)

    blend = deltaDot(target, sources)
    side = getWorldDeltaNode(*sources)
    aim_start = getWorldPointNode(stay)
    aim_end = getLerpPositionNode(*source_ends, blend)
    aim = getWorldDeltaNode(aim_start, aim_end)
    up = getCrossNode(aim,side)
    side = getCrossNode(aim,up)

    aim_matrix = getAimMatrixNode(aim,up,side,aim_start)
    

    offset = pm.createNode('transform',ss=True,name='{}_membrane_offset'.format(VALID_NAME(target)))
    decompose = pm.createNode('decomposeMatrix',ss=True,name='{}_DecomposeMatrix'.format(VALID_NAME(target)))
    pm.connectAttr(aim_matrix.output, decompose.inputMatrix)
    pm.connectAttr(target.rotateOrder, decompose.inputRotateOrder)
    pm.connectAttr(decompose.outputTranslate, offset.translate)
    pm.connectAttr(decompose.outputRotate, offset.rotate)
    pm.connectAttr(decompose.outputScale, offset.scale)
    pm.connectAttr(decompose.outputShear, offset.shear)
    offset.setAttr('inheritsTransform',0)

    pm.parentConstraint(offset,target,mo=True)
    pm.parent(offset,stay)
    target.setAttr('displayLocalAxis',DEBUG)


def debugPosition(node):
    '''Create transform with handle and local access displayed position in world at nodes output vector'''
    debug_node = pm.createNode('transform', ss=True, name='debug_{}'.format(VALID_NAME(node)))
    pm.connectAttr(getOutputAttribute(node), debug_node.translate)
    debug_node.setAttr('displayHandle', DEBUG)
    debug_node.setAttr('displayLocalAxis', DEBUG)
    debug_node.setAttr('inheritsTransform', 0)
    return debug_node

def debugCurve(points=None,name='debugCurve'):
    OS = pm.ls(sl=True)
    curve = pm.curve(d=1,p=points,name=name)
    curve.setAttr('inheritsTransform', 0)

    pm.select(cl=True)
    if OS:
        pm.select(OS,r=True)