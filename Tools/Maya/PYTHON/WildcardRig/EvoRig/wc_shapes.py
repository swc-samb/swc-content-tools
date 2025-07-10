import os, sys, stat
import math
import pickle
import json
import traceback

from functools import partial
from inspect import getsourcefile

import maya.mel as ml
import maya.cmds as mc
import pymel.core as pm

# handle reload from different python version
if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
    izip = zip
    xrange = range
elif sys.version_info.major > 3.4:
    reload = __import__('importlib').reload
    izip = zip
    xrange = range
else:
    from itertools import izip


import mb_rig_utilities as util


__author__ = 'Ethan McCaughey'
__version__ = '0.1.1'



# Current Script path, using more robust method than __file__ which is sometimes missing
script_path = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
folderShapes = os.path.join(script_path, 'shapes')

epsilon = sys.float_info.epsilon

validPickleTypes = {x:True for x in ['float', 'bool', 'enum', 'short', 'long', 'byte', 'doubleLinear', 'doubleAngle']}



#-----------------------------------------------------------------------------#
# Utility Functions
#-----------------------------------------------------------------------------#


def unit(vec):
    '''Return vector resized to length 1'''

    preLength = sum((x*x for x in vec))
    if abs(preLength) > epsilon:
        imag = 1.0 / math.sqrt(preLength)
        return type(vec)((x * imag for x in vec))
    else:
        return vec[:]      


def length(vec):
    '''Return vector length'''

    preLength = sum((x*x for x in vec))
    if abs(preLength) > epsilon:
        return math.sqrt(preLength)
    else:
        return 0     


def dot(vecA, vecB):
    '''Return the dot product of two vectors'''
    return sum((a*b for a,b in izip(vecA, vecB)))


def cross(vecA, vecB):
    '''Return the cross product of two vectors'''
    return  type(vecA)([vecA[1] * vecB[2] - vecB[1] * vecA[2],
                        vecB[0] * vecA[2] - vecA[0] * vecB[2],
                        vecA[0] * vecB[1] - vecB[0] * vecA[1]])


def delta(vecA, vecB):
    '''Delta from a to b'''
    return [b-a for a,b in izip(vecA, vecB)]


def bounds(vecList):
    '''Returns min and max bounds vectors'''
    if not vecList:
        return None

    maxVec, minVec = vecList[0], vecList[0]
    lx = len(minVec)
    for vec in vecList:
        maxVec = [max(vec[n], maxVec[n]) for n in xrange(lx)]
        minVec = [min(vec[n], minVec[n]) for n in xrange(lx)]
    
    return minVec, maxVec


def boundSize(vecList):
    '''Returns delta from min to max bounds vectors'''
    return [b-a for a,b in izip(*bounds(vecList))]


def boundCenter(vecList):
    return average(list(bounds(*vecList)))


def average(vecList, weights = None):
    '''Returns simple average of a list'''
    
    #skip invlaid inputs
    if not vecList or not hasattr(vecList, '__iter__'):
        return vecList

    #skip unessecessary averaging    
    if len(vecList) == 1:
        return vecList[0]

    # handle list of floats
    if not hasattr(vecList[0], '__iter__'):
        if not weights or not hasattr(weights, '__iter__'):
            return type(vecList[0])(sum(vecList) * (1.0/len(vecList)))

        # Handle weighting if any
        total = 0
        totalWeight = 0
        for v,w in izip(vecList, weights):
            total += v * w
            totalWeight += w
        if totalWeight > epsilon:
            total *= (1.0 / totalWeight)
        else:
            return 0
        return total

    # otherwise assume a list of vectors
    point = vecList[0]
    if not weights or not hasattr(weights, '__iter__'):
        for v in xrange(1,len(vecList)):
            point = [a+b for a,b in izip(vecList[v],point)]
        vx = 1.0 / float(len(vecList))
        return type(vecList[0])((x * vx for x in point))  

    # Handle weighting if any
    totalWeight = weights[0]
    for v in xrange(1,len(vecList)):
        w = weights[v]
        point = [b + (a * w) for a,b in izip(vecList[v],point)]
        totalWeight += abs(w)
    if totalWeight > epsilon:
        vx = 1.0/totalWeight
        return type(vecList[0])((x * vx for x in point))
    else:
        return type(vecList[0])([0,0,0])


def getImplicitAimMatrix(item):
    '''Deterimine aim and up vectors based on parent and child hierarchy then return matrix'''

    aim = [1,0,0]
    upS = [0,1,0]
    zUp = mc.upAxis(q = True, axis = True).lower() == 'z'
    if zUp:
        upS = [0,0,1]
    up = upS
    
    radius = 1.0
    aimTest = item.getAttr('t')
    
    itemType = mc.nodeType(item.longName())
    children = pm.listRelatives(item, c = True, type = itemType)
    if children:
        aimTest = average([x.getAttr('t') for x in children],
                             weights = [len(pm.listRelatives(x, ad = True, type = itemType)) for x in children])
        if length(aimTest) > epsilon:
            aim = unit(aimTest)
            
    if not children or length(aimTest) < epsilon:
        current = (pm.listRelatives(item, p = True) or [None])[0]
        while current and length(aimTest) < epsilon:
            aimTest = current.getAttr('t')
            current = (pm.listRelatives(current, p = True) or [None])[0]
        if length(aimTest) > epsilon:
            aim = unit((current.getAttr('worldInverseMatrix') * item.getAttr('worldMatrix')) * aimTest)
        

    #cross interperite side vector and normalize
    if zUp:        
        side = unit(cross(aim, up))
        up = unit(cross(side, aim))
    else:
        side = unit(cross(up, aim))
        up = unit(cross(aim, side))

    # nearest up to scene up
    upS = item.getAttr('worldMatrix') * pm.datatypes.Vector(upS)
    dotSort = lambda x: dot(upS, x[0]) + 1
    upN, sideN = [-x for x in up], [-x for x in side]   
    up, side = sorted([[side, upN], [sideN, up]], key = dotSort)[-1]
    
    #debug 
    debug = False
    if debug:
        point = pm.xform(item, q = True, ws = True, sp = True)
        mat = item.getAttr('worldInverseMatrix')
        for vec in (up, side, aim):
            pm.curve(d = 1, point = [point, [b + (a * 600) for a,b in zip(mat * pm.datatypes.Vector(vec), point)]])

    if zUp:
        return pm.datatypes.Matrix([aim, side, up])
    else:
        return pm.datatypes.Matrix([aim, up, side])


def getJsonDict(item, ignore = None):
    if not ignore:
        ignore = []
    ignore += ['shapes', 'aimMatrix']
    result = {k:v for k,v in item.__dict__.items() if '_' != str(k)[0] and str(k) not in ignore}
    return result


def getPoint(item):
    if hasattr(item, '__iter__'):
        return list(map(getPoint, item))

    if '.' in str(item):
        point = pm.xform(item, q = True, ws = True, t = True)
        if len(point) > 3:
            point = average([point[n:n+3] for n in xrange(0, len(point), 3)])
    else:
        point = pm.xform(item, q = True, ws = True, sp = True)
    return point


def nearest(item, items = None, types = None):
    if types:
        if not hasattr(type, '__iter__'):
            types = [types]
    else:
        types = ['transform']
    
    point = getPoint(item)
    
    if items == None:
        if types:
            items = pm.ls(typ = types)
    elif types:
        items = pm.ls(items, typ = types)
    

    nearDist = -1
    nearest = None
    for obj in items:
        curDist = length(delta(point, getPoint(obj)))
        if curDist < nearDist or nearDist < 0:
            nearDist = curDist
            nearest = obj
    
    return nearest
    



#-----------------------------------------------------------------------------#
# Utility Classes
#-----------------------------------------------------------------------------#


class shapeObject(object):
    '''Picklable shape object to easily preserve a shapes adjustments.'''
    
    def __init__(self, node = None, aimMatrix = None):
        self._shapeAttributes = ['points', 'degrees', 'form']

        if node:
            self.getData(node, aimMatrix = aimMatrix)


    def getData(self, node, aimMatrix = None):
        '''Update shape data'''

        self.nodeType = mc.nodeType(node.longName())

        if self.nodeType == 'nurbsCurve': 
            attributes = pm.listAttr(node, se = True, m = False, r = True)
            for item in attributes:
                if not mc.objExists(node.longName() + "." + item):
                    continue
                try:
                    if validPickleTypes.get(str(node.getAttr(item, typ = True))):
                        val = node.getAttr(item)
                        self.__dict__[item] = val
                except :
                    continue
            
            if not aimMatrix:
                self.points = [list(node.getAttr('controlPoints[{}]'.format(n))) for n in xrange(node.numCVs())]
            else:
                inverse = aimMatrix
                self.points = [list(inverse * pm.datatypes.Vector(node.getAttr('controlPoints[{}]'.format(n)))) for n in xrange(node.numCVs())]
            
            self.degree = max(1, min(self.degree, len(self.points) - 1))
            

    def setData(self, parent, aimMatrix = None):
        '''Create shapes with stored shape data'''

        OS = pm.ls(sl = True)

        #handle nurbsCurves - should be able to support other types later
        if self.nodeType == 'nurbsCurve':
            if aimMatrix:
                inverse = aimMatrix.transpose() 
                points = [list(inverse * pm.datatypes.Vector(x)) for x in self.points]
            else:              
                points = self.points           
            
            self.degree = max(1, min(self.degree, len(points) - 1))

            transform = pm.curve(name = 'tempCurve', 
                                 p = points, 
                                 degree = self.degree)
            node = pm.listRelatives(transform, c = True)[0]
            if self.form != 0 and len(self.points) > 2:
                pm.closeCurve(node, ch = 0, ps = 0, rpo = 1, bb = 0.5, bki = 0, p = 0.1)
    
            node.rename(parent.longName().split('|')[-1] + "Shape")
            pm.parent(node, parent, r = True, s = True)
            pm.delete(transform)          
                   
            attributes = pm.listAttr(node, se = True, m = False, r = True)
            for item in attributes:
                if not mc.objExists(node.longName() + "." + item):
                    continue
                try:
                    if validPickleTypes.get(str(node.getAttr(item, typ = True))):
                        node.setAttr(item, self.__dict__[item])
                except:
                    continue
            
        pm.select(OS, r = True)


class gizmoObject(object):
    '''Picklable Multishape node storage for easy access to common ctrl shapes'''

    def __init__(self, 
                 node = None, 
                 create = True, 
                 name = 'circle'):

        self.node = node
        if self.node:
            self.node = str(node)
        self.name = name
        self.size = [1,1,1]
        self.shapes = []

        self._shapeAttributes = ['points', 'degrees', 'form']


        if create:
            if not node:
                self.nodeCheck(pm.createNode('transform', ss = True, name = str(name) + '_ctrl'))
            if self.name:
                self.load()

        elif node:
            self.node = str(node)
            self.getData(node)

        
    def nodeCheck(self, 
                  node = None, 
                  update = True, 
                  debug = None):
        '''verify given node or self.node'''

        node = util.getPyNode(node or self.node)
        self.node = str(node)
        if not util.isPyNode(node):
            mc.warning('gizmoObject.' + debug + ' Error: Invalid Node "' + str(node) + '"')
        elif update:
            self.getData(node)

        return node


    def getData(self, 
                node = None, 
                aimMatrix = None):
        '''Update local data from objects'''
        
        #use given node or self.node, bail if neither exists
        node = self.nodeCheck(node, update = False, debug = 'getData')
        if not util.isPyNode(node):
            return 

        #get transform attributes for color and display overrides
        for item in pm.listAttr(node, se = True, m = False, r = True):
            if not mc.objExists(node.longName() + "." + item):
                continue
            try:
                check = str(item).lower()
                if ('override' in check or 'color' in check) and validPickleTypes.get(str(node.getAttr(item, typ = True))):
                    val = node.getAttr(item)
                    self.__dict__[item] = val
            except :
                continue
        
        #get shape data
        self.shapes = []
        for shape in pm.listRelatives(node, c = True, shapes = True):
            self.shapes.append(shapeObject(shape, aimMatrix = aimMatrix))

        if self.shapes:
            self.size = boundSize([p for px in (x.points for x in self.shapes) for p in px])


    def setData(self, 
                node = None, 
                aimMatrix = None):  
        '''Set objects from local data'''

        #use given node or self.node, bail if neither exists
        node = self.nodeCheck(node, update = False, debug = 'setData')
        if not util.isPyNode(node):
            return

        
        #set transform attributes
        for item in pm.listAttr(node, se = True, m = False):
            if not mc.objExists(node.longName() + "." + item):
                continue
            try:
                check = str(item).lower()
                if ('override' in check or 'color' in check) and validPickleTypes.get(str(node.getAttr(item, typ = True))):
                    node.setAttr(item, self.__dict__[item])
            except :
                continue
            
        #delete any existing shapes and replace them with current data
        shapeCheck = pm.listRelatives(node, c = True, shapes = True)
        if shapeCheck:
            pm.delete(shapeCheck)
            
        for shape in self.shapes:
            shape.setData(node, aimMatrix = aimMatrix)


    def save(self, 
             node = None, 
             name = None, 
             aimMatrix = None, 
             update = True):
        '''Save Data to json dict file'''
        


        #use given node or self.node, bail if neither exists
        node = self.nodeCheck(node, update = update, debug = 'save')
        if not util.isPyNode(node):
            return 

        if aimMatrix != None:
            self.getData(aimMatrix = aimMatrix)

        #save to json file in shapes folder
        name = str(name or self.name or node).lower()
        path = os.path.join(folderShapes, name + '.json')
        
        print('path {}'.format(path))
        print('name {}'.format(name))
        print('self.name {}'.format(self.name))
        print('node {}'.format(node))


        data = [getJsonDict(self, ignore = ['shapes'])] + list(map(getJsonDict, self.shapes))
        try:
            if os.path.exists(path):
                os.chmod(path, stat.S_IWRITE)
            with open(path, 'w') as f:
                try:
                    json.dump(data, f)
                except:
                    mc.warning('gizmoObject.save Error: "' + path + '"')
                    traceback.print_exc()
                finally:
                    f.close()
        except:
            mc.warning('gizmoObject.save Error: "' + path + '"')
            traceback.print_exc()

        print('Saved Shape Template: "' + path + '"')
        return path

    
    def load(self, 
             node = None, 
             name = None, 
             aimMatrix = None): 
        '''Load Data from json dict file'''

        #use given node or self.node, bail if neither exists
        node = self.nodeCheck(node, update = False, debug = 'load')
        if not util.isPyNode(node):
            return 


        #load from json file in shapes folder
        name = str(name or self.name or node).lower()        
        path = os.path.join(folderShapes, name + '.json')

        try:
            with open(path, 'r') as f:
                try:
                    data = json.load(f)
                    self.__dict__.update(data[0])
                    self.shapes = [shapeObject() for x in data[1:]]
                    for shape, values in izip(self.shapes, data[1:]):
                        shape.__dict__.update(values)               
                    self.setData(node, aimMatrix = aimMatrix)
                except:
                    mc.warning('gizmoObject.load Error: "' + path + '"')
                    traceback.print_exc()
                finally:
                    f.close()
        except:
            mc.warning('gizmoObject.load Error: "' + path + '"')
            traceback.print_exc()

        self.setData(node)
        print('Loaded Shape Template: "' + path + '"')
        return self


    def unitize(self, update = True):
        '''Scale point data to bounds size 1,1,1'''

        if update:
            self.getData()

        points = [p for px in (x.points for x in self.shapes) for p in px]
        
        if not points:
            return

        minVec, maxVec = bounds(points)
        center = average([minVec, maxVec])
        size = delta(minVec, maxVec)
        scalar = [1.0/n if abs(n) > epsilon else 0.0 for n in size]
        for shape in self.shapes:
            shape.points = [type(x)((x[n] * scalar[n] for n in xrange(3))) for x in shape.points]

        if update:
            self.setData()


    def resize(self, size, update = True):
        '''resize points to give bounds size'''

        if update:
            self.getData()

        if not hasattr(size, '__iter__'):
            size = [size, size, size]

        points = [p for px in (x.points for x in self.shapes) for p in px]
        if not points:
            return
        minVec, maxVec = bounds(points)
        current = delta(minVec, maxVec)
        scalar = [a/b if abs(a * b) > epsilon else 0.0 for a,b in izip(size, current)]
        for shape in self.shapes:
            shape.points = [type(x)((x[n] * scalar[n] for n in xrange(3))) for x in shape.points]

        if update:
            self.setData()


    def copyNonShapeData(self, other):
        self.__dict__.update(getJsonDict(other, ignore = self._shapeAttributes))

        dataList = other.shapes
        if not dataList:
            return
        if len(dataList) != len(self.shapes):
            dataList = [dataList[0] for x in xrange(len(self.shapes))]
        for data, shape in izip(dataList, self.shapes):
            shape.__dict__.update(getJsonDict(data, ignore = self._shapeAttributes))

        self.setData()




#-----------------------------------------------------------------------------#
# UI
#-----------------------------------------------------------------------------#



def removeWindows(windowName):    
    if (mc.window(windowName, exists=True)):
        mc.deleteUI(windowName)
    if (mc.window(windowName + str(0) , exists=True)):
        mc.deleteUI(windowName + str(0))
        

class shapeTemplateUI(object):
    def __init__(self):
        self.template = None
        self.shapeOnly = True
        self.matchBounds = True
        self.matchRadius = False
        self.useAimMatrix = False
        self.makeWindow()
    
    def show(self):
        mc.showWindow(self.window)
    
    
    def makeWindow(self):   
        windowSize = (400, 200)
        windowName = "Shape_Templates"
        removeWindows(windowName)

        if not (pm.window(windowName, exists=True)):
            self.window = pm.window( windowName, 
                                     title = windowName.replace('_', ' '), 
                                     resizeToFitChildren = True,
                                     w = windowSize[0],
                                     h = windowSize[1])
        else:
            return

        pm.window(self.window, e = True, width = windowSize[0], height = windowSize[1])


        mainColumn = pm.columnLayout("mainColumn", adjustableColumn = True , w = windowSize[0])
        moduleLayout = pm.rowColumnLayout(nc = 2, cw = [(1,windowSize[0]/3), (2, 2 * windowSize[0]/3)], parent = mainColumn)

        pm.separator(h=5, w = windowSize[0]/2, style="none", parent = moduleLayout)
        pm.separator(h=5, w = windowSize[0]/2, style="none", parent = moduleLayout)

        # Template Menu        
        
        templateCmd = partial(self.setTemplate)

        templateTypes = [''] + [x.split('.')[0] for x in os.listdir(folderShapes) if '.json' in x]
        UIName = 'Template_Type'
        pm.text(UIName, 
                label = 'Template :', 
                parent = moduleLayout)
        
        menuname = UIName + 'Menu'
        self._templateMenu = pm.optionMenu(menuname, 
                                           cc = templateCmd,
                                           parent=moduleLayout)
        for label in templateTypes:
            pm.menuItem(label = label)        

        
        # Template Name
        UIName = 'Template_Name'
        pm.text(UIName, 
                label='Name :',
                parent=moduleLayout)
                
        self._textTemplate = pm.textField(UIName + 'TextField', 
                                          text = self.template,
                                          annotation ='Template Name',
                                          tcc = templateCmd,
                                          parent = moduleLayout)

        self.setTemplate(self.template)


        #save load and delete
        
        moduleLayout = pm.rowColumnLayout(nc = 2, cw = [(1,windowSize[0]/2), (2,windowSize[0]/2)], parent = mainColumn)

        pm.separator(h=5, w = windowSize[0]/2, style="none", parent = moduleLayout)
        pm.separator(h=5, w = windowSize[0]/2, style="none", parent = moduleLayout)

        pm.button(label = "Save Template", 
                  command = self.save, 
                  annotation='Save Template', 
                  parent = moduleLayout)
        pm.button(label = "Load Template", 
                  command = self.load, 
                  annotation='Load Template', 
                  parent = moduleLayout)

        #point, degree, and form data only
        pm.checkBox('shapeOnly',
                    value=self.shapeOnly,
                    label = 'Shape Data Only ',
                    changeCommand=partial(setattr, self, 'shapeOnly'),
                    parent = moduleLayout)
        
        #Match Bounding Box Size
        self._matchBounds = pm.checkBox('MatchBounds',
                                      value=self.matchBounds,
                                      label = 'Match Bounding Box Size',
                                      changeCommand=partial(self.setMatch, 'matchBounds', 'matchRadius'))

        
        #Use Nearest Joint Aim Matrix
        new = pm.checkBox('UseAimMatrix',
                          value=self.useAimMatrix,
                          label = 'Use Nearest Joint Aim Matrix',
                          changeCommand=partial(setattr, self, 'useAimMatrix'))
                          
        
        #Match Bounding Box Radius
        self._matchRadius = pm.checkBox('MatchRadius',
                                        value=self.matchRadius,
                                        label = 'Match Bounding Box Radius',
                                        changeCommand=partial(self.setMatch, 'matchRadius', 'matchBounds'))
        
        
        #WireFrame Color Editor
        pm.button(label = "Edit Color", 
                  command = self.colorPallette, 
                  annotation='Edit Color', 
                  parent = moduleLayout)       
        pm.separator(h=20, style="none", parent = moduleLayout)  


        pm.separator(h=60, style="none", parent = moduleLayout)   
        pm.separator(h=60, style="none", parent = moduleLayout) 
        pm.separator(h=20, style="none", parent = moduleLayout)         
        pm.button(label = "Delete Template", 
                  command = self.delete, 
                  annotation='Delete Template', 
                  parent = moduleLayout)


        self.show()
        return self.window


    def colorPallette(self, _):
        ml.eval('objectColorPalette();')


    def setTemplate(self, name):
        '''Set Current Template'''

        templateTypes = [''] + [x.split('.')[0] for x in os.listdir(folderShapes) if '.json' in x]
        for item in self._templateMenu.getItemArray():
            pm.deleteUI(item)
        for label in templateTypes:
            pm.menuItem(label = label, parent = self._templateMenu)

        self.template = name

        pm.textField(self._textTemplate, e = True, text = self.template)

        menuIndex = 1
        if self.template and templateTypes and self.template in templateTypes:
            menuIndex = templateTypes.index(self.template)+1  

        pm.optionMenu(self._templateMenu, 
                      e = True, 
                      sl = menuIndex)
        

    def setMatch(self, current, other, value):
        '''Set bounds Matching values'''

        setattr(self, current, value)
        if value:
            setattr(self, other, False)
        
        pm.checkBox(getattr(self, '_' + current), e = True, value = getattr(self, current))
        pm.checkBox(getattr(self, '_' + other), e = True, value = getattr(self, other))
        

    def save(self, _):
        '''Save shape data to shapes folder'''

        print('save {}'.format(self.template))
        if not self.template:
            pm.warning('shapeTemplateUI.save: Error:  No Template Name Given')
            return
        nodes = [x if mc.nodeType(str(x)) not in ['nurbsCurve', 'mesh', 'nurbsSurface', 'subdiv'] else pm.listRelatives(x, p = True)[0] for x in pm.ls(sl = True)]
        if not nodes:
            pm.warning('shapeTemplateUI.save: Error:  No Control Nodes Given')
            return

        filepath = os.path.join(folderShapes, self.template + '.json')        
        if os.path.exists(filepath):
            os.chmod(filepath, stat.S_IWRITE)
            confirm = mc.confirmDialog(title='Confirm Overwrite', 
                                       message='Overwrite "' + filepath + '"',
                                       button=['Yes','No'],
                                       defaultButton='Yes',
                                       cancelButton='No',
                                       dismissString='No')
            if confirm == 'No':
                pm.warning('shapeTemplateUI.save: Cancelled by User')
                return
        
        aimMatrix = None
        if self.useAimMatrix:
            aimMatrix = getImplicitAimMatrix(nearest(nodes[0], types = 'joint'))
        
        print('self.template {}'.format(self.template))
        gizmoObject(nodes[0], 
                    create = False, 
                    name = self.template).save(aimMatrix = aimMatrix)
        
        self.setTemplate(self.template)
        

    def load(self, _):
        '''Load shape data from shapes folder'''

        if not self.template:
            pm.warning('shapeTemplateUI.saveload: Error:  No Template Name Given')
            return
        nodes = [x if mc.nodeType(str(x)) not in ['nurbsCurve', 'mesh', 'nurbsSurface', 'subdiv'] else pm.listRelatives(x, p = True)[0] for x in pm.ls(sl = True)]
        if not nodes:
            pm.warning('shapeTemplateUI.load: Error:  No Control Nodes Given')
            return


        for node in nodes:         
            aimMatrix = None
            if self.useAimMatrix:
                aimMatrix = getImplicitAimMatrix(nearest(node, types = 'joint'))

            current = gizmoObject(node, create = False)

            if (self.matchBounds or self.matchRadius):
                if current.shapes:
                    size = current.size
                else:
                    bounds = pm.xform(node, q = True, ws = True, bb = True)
                    size = delta(bounds[3:], bounds[:3])
                if self.matchRadius:
                    size = [max(*size), max(*size), max(*size)]
            
            new = gizmoObject(node, 
                              name = self.template,
                              create = True)

            new.setData(aimMatrix = aimMatrix)

            if self.shapeOnly:
                new.copyNonShapeData(current)

            if (self.matchBounds or self.matchRadius):
                new.resize(size = size)
                


    def delete(self, _):
        filepath = os.path.join(folderShapes, self.template + '.json')
        
            
        if os.path.exists(filepath):
            os.chmod(filepath, stat.S_IWRITE)
            confirm = mc.confirmDialog(title='Confirm Delete', 
                                       message='Delete "' + filepath + '" ?',
                                       button=['Yes','No'],
                                       defaultButton='Yes',
                                       cancelButton='No',
                                       dismissString='No')
            if confirm == 'Yes':
                os.remove(filepath)
                
                if len(self._templateMenu.getItemArray()) > 0:
                    pm.optionMenu(self._templateMenu, 
                                e = True, 
                                sl = 1)
                self.setTemplate(self.template)
            