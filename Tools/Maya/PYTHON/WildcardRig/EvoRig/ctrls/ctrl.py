# coding=utf-8

import re
import os
import sys
import time
import json
import importlib
from functools import partial
from collections import OrderedDict as od

#python 3 compatability
if sys.version_info.major < 3:
    from itertools import izip
else:
    izip = zip

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major >= 3.4:
    reload = __import__('importlib').reload

if sys.version_info.major >= 3.0:    
    unicode = str


from EvoRetarget import retargets; reload(retargets);

from EvoRig import mb_rig_utilities as util; reload(util);
pm = util.pm
cmds = util.cmds
is_iterable =  util.is_iterable

util.debugging = True

#sort based on object hierarchy
hisort = lambda x: len(x.longName().split('|'))

def timestamp(): return "_" + str(time.time()).replace('.', '') + '_' + str(len((cmds.lsUI(type = ["window", "menu", "control", "controlLayout"]) or [])))

#-----------------------------------------------------------------------------#
# Base Ctrl Class
#-----------------------------------------------------------------------------#


class ctrlModule(object):
    """Class for creating ctrl modules, storing their data,
       creating their UI within the autorig tool"""
    _attrList = []
    _isCtrl = False
    _index = -1
    _moduleCW = [(1,100), (2,240)]
    _separatorHeight = 15
    _color = (0.5,0.5,0.5)
    _label = ''
    _nodeAttributes = {}
    _rigNetworkNodeName = None
    _moduleNetworkNodeName = None

    def __init__(self, *args, **kwargs):
        object.__init__(self)

        self._uiInputs = {}
        if not hasattr(self, 'keyword'):
            self.keyword = ''

        if not hasattr(self, 'applyShapes'):
            self.applyShapes = True

        self._attrList.remove('applyShapes')
        self._attrList.insert(2, 'applyShapes')

        if not hasattr(self, 'spaces'):
            self.spaces = []

        if not hasattr(self, 'useSpaceBlending'):
            self.useSpaceBlending = False

        if not hasattr(self, '_spaceBlendDict'):
            self._spaceBlendDict = {}

        if not hasattr(self, 'moduleSize'):
            self.moduleSize = 1.0

        if not hasattr(self, 'controlLayer'):
            self.controlLayer = 0

        # Attributes that pair with maya nodes
        if not hasattr(self, '_nodeAttributes'):
            self._nodeAttributes = {}            
        self._nodeAttributes['spaces'] = True
        
        # Attributes not handled with default ui setup
        if not hasattr(self, '_ignoreList'):
            self._ignoreList = ['']    

        ignored = ['spaces', 'useSpaceBlending', '_spaceBlendDict', 'moduleSize', 'controlLayer']
        self._ignoreList.extend([x for x in ignored if x not in self._ignoreList])

        if args:
            self._args = list(args)
        if kwargs:
            self.__dict__.update(kwargs)

        
        if not hasattr(self, '_expanded'):
            self._expanded = True

    def _findExistingNetwork(self, nodeName=None):
        """
        Finds existing network node for module in scene, returns None if not found
        
        """

        if not nodeName:
            displayModuleName = util.getMayaSafeName(self._label)
            nodeName = f'{displayModuleName}_{self.keyword}_Network'
        if pm.objExists(nodeName):
            return pm.PyNode(nodeName)
        else:
            return None

    def _createNetworkNode(self, nodeName=None):
        """
        Creates the network node and names it
        
        """
        if not nodeName:
            nodeName = f'{type(self).__name__}_{self.keyword}_Network'
        networkNode = pm.createNode('network', n=nodeName)
        return networkNode

    def _registerNetworkLinks(self, moduleNetwork, rigNetwork):
        """
        Creates the connections between the parent rig and this modules network 
        
        :param pm.nt.Network moduleNetwork: The network node for this module
        :param pm.nt.Network rigNetwork: The main network node for the rig, parent to this module

        """

        if isinstance(rigNetwork, str):
            if pm.objExists(rigNetwork):
                rigNetwork = pm.PyNode(rigNetwork)
            else:
                pm.warning(f'No rig network provided, not registering links for {self._label}_Network')
        if not rigNetwork.hasAttr('modules'):
            rigNetwork.addAttr('modules', at="message", multi=True)
        if not moduleNetwork.hasAttr('parent'):
            moduleNetwork.addAttr('parent', at='message')
        if not moduleNetwork.attr('parent').isConnected():
            rigNetwork.attr('modules')[rigNetwork.attr('modules').numElements()].connect(moduleNetwork.attr('parent'))

    def getNetworkNode(self, rigNetwork=None, nodeName=None, registerLinks=True):  
        """
        Checks if network node exists for this module, creates it if not, registers links with parent network if possible and requested
        
        :param pm.nt.Network rigNetwork: The main network node for the rig, parent to this module
        :param str nodeName: Name of node to search for, if none is provided we look for self.keyword + _Network

        """ 
        # If we already have a network node, use that and return
        if self._moduleNetworkNodeName and pm.objExists(self._moduleNetworkNodeName):
            networkNode = pm.PyNode(self._moduleNetworkNodeName)
            return networkNode

        # If we don't have one cached, check by node name if it exists
        networkNode = self._findExistingNetwork(nodeName=nodeName)
        if not networkNode:
            # If it definitely doesn't exist, make it
            networkNode = self._createNetworkNode(nodeName=nodeName)
        
        # For new rigs we will want to provide the parent network node so links can be created
        if registerLinks:
            if rigNetwork:
                self._registerNetworkLinks(networkNode, rigNetwork)
                self._rigNetworkNodeName = rigNetwork.name()
            else:
                pm.warning(f'No main rig network not provided for {networkNode.name()}, skipping links.')

        self._moduleNetworkNodeName = networkNode.name()

        return networkNode


    def deleteUI(self):
        #for item in [x for xl in [n if hasattr(n, '__iter__') else [n] for n in self._uiInputs.values()] for x in xl]:
        for item in [x for xl in [n if is_iterable(n) else [n] for n in self._uiInputs.values()] for x in xl]:
            if item:
                try:
                    pm.deleteUI(item)
                except:
                    continue

    def getName(self):
        return str(self._index) + ' ' + type(self).__name__ 


    def getTitle(self):
        """Return highest joint in self._nodeAttributes except the "spaces" attribute.
           Intended to give modules that dont use keyword a reasonable label."""

        if not self.keyword and self._nodeAttributes:
            nodes = []
            for attr in self._nodeAttributes:
                if attr == 'spaces':
                    continue
                check_node = (getattr(self, attr) or[])
                #if check_node and not hasattr(check_node, '__iter__'):
                if check_node and not is_iterable(check_node):
                    check_node = [check_node]
                if issubclass(type(check_node),pm.general.PyNode):
                    nodes.extend(check_node)
            if nodes:
                try:
                    return str(sorted(nodes, key=hisort)[0])
                except:
                    return "None"
                    
        return self.keyword

    def moduleToNetwork(self, networkNode, keys=None):
        """
        Write module data to network node
        
        :param pm.nt.Network networkNode: Network node to write on
        :param list keys: Attr names to check for-- optional

        """

        net = pm.PyNode(networkNode)
        data = self.__dict__
        cls_path = f'{self.__class__.__module__}.{self.__class__.__name__}'
        if not net.hasAttr("moduleClass"):
            net.addAttr("moduleClass", dt="string")
        net.attr("moduleClass").set(cls_path)

        if keys is None:
            items = ((k, v) for k, v in data.items() if not k.startswith("_"))
        else:
            keys = set(keys)
            items = ((k, v) for k, v in data.items() if k in keys)

        for k, v in items:
            # primitives get real attrs
            if isinstance(v, bool):
                if not net.hasAttr(k):
                    net.addAttr(k, at="bool")
                net.attr(k).set(v)

            elif isinstance(v, int) and not isinstance(v, bool):
                if not net.hasAttr(k):
                    net.addAttr(k, at="long")
                net.attr(k).set(v)

            elif isinstance(v, float):
                if not net.hasAttr(k):
                    net.addAttr(k, at="double")
                net.attr(k).set(v)

            elif isinstance(v, str):
                if not net.hasAttr(k):
                    net.addAttr(k, dt="string")
                net.attr(k).set(v)

            else:
                # everything else goes into JSON string
                if not net.hasAttr(k):
                    net.addAttr(k, dt="string")
                net.attr(k).set(json.dumps(v, default=str))

    def getControls(self):
        """ Returns the modules controls """
        networkNode = self.getNetworkNode()
        if networkNode:
            return networkNode.controls.get()
        else:
            return []

    def getJoints(self):
        """ Get joints for module """
        networkNode = self.getNetworkNode()
        if networkNode:
            return networkNode.joints.get()
        else:
            return []

    def __setattr__(self, attr, value):
        """Dynamically overriding setattr to control data storage"""

        if '_' != str(attr)[0] and issubclass(type(value), dict):
            super(type(self).__bases__[0], self).__setattr__('_dm_' + attr, value)
            if len(value):
                value = list(value.values())[0]
            else:
                value = None

        if not attr in self._attrList:
            self._attrList.append(attr)    

        super(type(self).__bases__[0], self).__setattr__(attr, value)
    

    def __setattribute__(self, attr, value):
        """Dynamically overriding setattr to control data storage"""
        self.__setattr__(attr, value)

    
    def __getattribute__(self, attr):
        """Dynamically overriding getattr to control data storage"""
        value = object.__getattribute__(self, attr)
        if value == None or attr == '_nodeAttributes' or not self._nodeAttributes.get(attr):
            return value
            
        err = False
        if value:
            err = 'Nodes Not Found for Module ' + self.getName() + '.' + attr  + ': '
        return util.getPyNode(value, warning = err)
            

    def __getattr__(self, attr):
        """Dynamically overriding getattr to control data storage"""
        return self.__getattribute__(attr)


    def __delattr__(self, attr):
        """Dynamically overriding delattr to control data storage"""

        if attr in self._attrList:
            del self._attrList[self._attrList.index(attr)]
        if hasattr(self, '_dm_' + attr):
            super(type(self).__bases__[0], self).__delattr__('_dm_' + attr)
        super(type(self).__bases__[0], self).__delattr__(attr)
    
    def __deleteattribute__(self, attr):
        self.__delattr__(attr)


    def setUI(self, name, UI):
        """Store UI by attribute name"""
        #if not hasattr(UI, '__iter__'):
        if not is_iterable(UI):
            UI = [UI]
        self._uiInputs[name] = UI


    def getUI(self, name):
        """Retrieve stored ui by attribute name"""
        return self._uiInputs.get(name)



    def initDynamicLayout(self, AutoRig, index = 0):
        """Default Module Layout Name and Keyword
           Shouldnt need to be overwritten"""

        self._index = index
        
        frameLayout = pm.frameLayout ("ModuleFrameLayout" + str(index), 
                                      label = 'Module ' + str(self._index+1) + '  -  ' + self._label + '  -  ' + self.getTitle(), 
                                      bgc=self._color,
                                      collapsable = True, 
                                      collapse = False, 
                                      cc = partial(setattr, self, '_expanded', False),
                                      ec = partial(setattr, self, '_expanded', True),
                                      parent=AutoRig.dynamicLayout)
        pm.frameLayout(frameLayout, e = True, collapse = not self._expanded)                        
        self.setUI('frameLayout', frameLayout)
                                      
        moduleLayout = pm.rowColumnLayout(nc=2, 
                                          cw=self._moduleCW, 
                                          parent=frameLayout) 
        self.setUI('moduleLayout', moduleLayout)        

        # Keyword 
        pm.text('keywordText'+ str(self._index), 
                label='Key Word :',
                parent=moduleLayout)
                
        keyword = pm.textField('keywordTextField'+ str(index), 
                                text = self.keyword,
                                changeCommand=partial(setattr, self, 'keyword'),
                                annotation='keyword to look for in the joint names',
                                parent=moduleLayout)
        self.setUI('keyword', keyword)

        # Type Menu
        pm.text('controlText'+ str(self._index), 
                label='Type :', 
                parent=moduleLayout)
        
        menuname = 'controlStyle_Menu' + str(self._index)
        menu = pm.optionMenu(menuname, 
                             cc=partial(AutoRig.moduleMenuChanged, 
                             self._index), parent=moduleLayout)
        for label in AutoRig.moduleTypes.keys():
            pm.menuItem(label=label)
        
        pm.optionMenu(menu, 
                      e=True, 
                      sl = list(AutoRig.moduleTypes.keys()).index(self._label)+1, 
                      parent=moduleLayout)

        self.setUI('typeMenu', menu)

        # Iterate through per module key,values and generate default style controls
        self.initDynamicLayoutParameters(moduleLayout)

        # Handle some global attributes so theyre always at the end
        self.initDynamicLayoutSpaces(moduleLayout)
        self.initDynamicLayoutParameter('moduleSize',moduleLayout)
        self.initDynamicLayoutParameter('controlLayer',moduleLayout)
        

        # Add reorder buttons
        colLayout = pm.rowColumnLayout(nc=4, 
                           cw=[(1,235), (2,35), (3,35), (4,35)],
                           parent=AutoRig.dynamicLayout,
                           bgc=self._color)
        pm.separator(height=self._separatorHeight, 
                     style="none",
                      parent=colLayout)
        

        if (self._index == 0):
            pm.separator(height=self._separatorHeight, 
                         style="none", 
                         parent=colLayout)
        else:
            pm.button('reorderUpButton'+ str(self._index), 
                      label=u'▲', 
                      command=partial(AutoRig.reorderUpButton,self._index))
        
        if (self._index >= (len(AutoRig.modules)-1)):
            pm.separator(height=self._separatorHeight, 
                         style="none", 
                         parent=colLayout)
        else:
            pm.button('reorderDownButton'+ str(self._index), 
                      label=u'▼', 
                      command=partial(AutoRig.reorderDownButton,self._index))
        
        # Remove button
        if self._index > 0:            
            pm.button('Delete'+ str(self._index), 
                      label=u'X', 
                      command=partial(AutoRig.removeModuleCommand,self._index))
        else:
            pm.separator(height=self._separatorHeight, 
                         style="none", 
                         parent=colLayout)



    def initDynamicLayoutParameters(self, 
                                    moduleLayout,
                                    ignoreList=None):
        """Create parameter UI - Works for most attributes, override if necessary
           Please make sure UI sets and gets a class attribute
           Please store created UI with self.setUI(attributename, newUI)"""

        # Handle an ignore list so that so some attributes
        # Can be handled with custom behavior
        attrList = self._attrList
        #if ignoreList != None and not hasattr(ignoreList, '__iter__'):
        if ignoreList != None and not is_iterable(ignoreList):
            ignoreList = [ignoreList]

        ignoreList = (ignoreList or []) + self._ignoreList
        if ignoreList:
            attrList = [x for x in attrList if x not in ignoreList]

        for attribute in attrList:
            self.initDynamicLayoutParameter(attribute, moduleLayout)
            
            
    def initDynamicLayoutParameter(self, attribute, moduleLayout):
        """Creates Default UI based on attribute type"""
        v = self.__dict__.get(attribute)
        key = str(attribute)
        if '_' == key[0]:
            return
        
        # format attribute to be more readable
        displayLabel = re.sub("([a-z])([A-Z])","\g<1> \g<2>",key)
        displayLabel = displayLabel[0].upper() + displayLabel[1:]
        vType = type(v)

        new = None
        # handle pyNode attributes
        if hasattr(self, '_dm_' + key):
            attrDict = getattr(self, '_dm_' + key)
            # Dict Menu
            pm.text('MenuText_'+ key + str(self._index), 
                    label=displayLabel, 
                    parent=moduleLayout)
            
            menuname = key + '_Menu' + str(self._index)
            new = pm.optionMenu(menuname, 
                                cc=partial(self.setDictMenu, attribute), 
                                parent=moduleLayout)

            for label in attrDict.keys():
                pm.menuItem(label=label)
            
            #index = [i for i, kv in enumerate(attrDict.items()) if kv[1] == getattr(self, k)][0]

            valueMatches = [i for i, kv in enumerate(attrDict.items()) if kv[1] == getattr(self, attribute)]
            if not valueMatches:
                valueMatches = [i for i, kv in enumerate(attrDict.items()) if kv[0] == getattr(self, attribute)]

            if not valueMatches:   
                print("Warning: Save Value doesn't match the options:")
                print("Saved:", v)
                print("Options: {}".format(str(attrDict.items() )))
                index = 0
            else:
                index = valueMatches[0]

            pm.optionMenu(new, 
                            e=True, 
                            sl=index+1, 
                            parent=moduleLayout)   

        elif self._nodeAttributes.get(attribute):
            #if not hasattr(v, '__iter__'):
            if not is_iterable(v):
                v = [v]
            v = util.getPyNode(v)    
    

            newButton = pm.button(key + "button" + str(self._index), 
                                    label=displayLabel + ' >', 
                                    command=partial(self.setNodeAttrSelected, attribute),
                                    parent=moduleLayout)
            newTextField = pm.textField(key + 'TextField'+ str(self._index), 
                                        text=','.join((str(x) for x in v)), 
                                        editable=True, 
                                        changeCommand=partial(self.setNodeAttrSelected, attribute, add = False), 
                                        annotation='',
                                        parent=moduleLayout)
            new = [newButton, newTextField]

        # handle ints and floats
        elif issubclass(vType, float) or (issubclass(vType, int) and not issubclass(vType, bool)):              
            pm.separator(height=self._separatorHeight, style="none", parent=moduleLayout)
            cmd = pm.floatSliderGrp
            if issubclass(vType, int):
                cmd = pm.intSliderGrp
            
            new = cmd(key + "_slider_" + str(self._index), 
                      l=displayLabel, 
                      value=v, 
                      step=0.001, 
                      field=1, 
                      min=-1000, 
                      max=1000,
                      changeCommand=partial(setattr, self, attribute),
                      parent=moduleLayout)

        # handle bools
        elif issubclass(vType, bool):  
            pm.text(key + 'Text'+ str(self._index), 
                    label=displayLabel,
                    parent=moduleLayout)      
            new = pm.checkBox(key + '_checkbox_' + str(self._index),
                                value=v,
                                label = '',
                                changeCommand=partial(setattr, self, attribute),
                                parent=moduleLayout)
                                
        # store for later                            
        if new:
            self.setUI(attribute, new)



    def setDictMenu(self, attr, *args):
        dictAttr = '_dm_' + str(attr)
        setattr(self, attr, getattr(self, dictAttr)[args[0]])


    def setNodeAttrSelected(self, attr, selected = None, add = True):
        """UI Change Command to Handle attributes that point to specific py nodes"""

        # figure out what the input is anc convert to a list of pymel nodes
        

        if selected in [None, False]:
            selected = [x.name() for x in pm.ls(sl=True)]
        else:             
            sType = type(selected)     
            textTypes = [str, unicode]          
            #if hasattr(selected, '__iter__'):
            if is_iterable(selected):
                selected = [x.name() if util.isPyNode(x) else x for x in selected]
            elif sType in textTypes:
                selected = [x for x in re.findall("[a-zA-Z0-9\_]+", str(selected))]
            elif util.isPyNode(selected):
                selected = selected.name()

        #if add and hasattr(self.__dict__.get(attr), '__iter__'):
        if add and is_iterable(self.__dict__.get(attr)):
            current = [x.name() if util.isPyNode(x) else x for x in (getattr(self, attr) or [])]
            selected = current + [x for x in selected if x not in current]


        # set attribute appropriately

        string = ''
        button, textField = self._uiInputs[attr]
        #if hasattr(self.__dict__.get(attr), '__iter__'):
        if is_iterable(self.__dict__.get(attr)):
            if not selected:
                selected = type(self.__dict__.get(attr))()
            else:
                string = ','.join(selected)
        else:
            #if hasattr(selected, '__iter__'):
            if is_iterable(selected):
                if selected:
                    selected = selected[0]
                else:
                    selected = ''
            string = selected


        setattr(self, attr, selected)
        
        if not selected:
            pm.warning('No Valid Items for Module ' + str(self._index) + ' ' + type(self).__name__ + '.' + attr)
        else:
            util.printdebug('Module ' + str(self._index) + ' ' + type(self).__name__ + '.' + attr + '<-' + string)

        # set text with appropriate string
        if self._uiInputs.get(attr):
            pm.textField(self._uiInputs[attr][1], edit=True, text=string)


    def initDynamicLayoutSpaces(self, moduleLayout):
        """Custom layout for parent spaces input"""

        # get space objects
        v = self.spaces
        #if not hasattr(v, '__iter__'):
        if not is_iterable(v):
            v = [v]
        v = util.getPyNode(v)    

        # space objects button and field
        newButton = pm.button("spacesbutton" + str(self._index), 
                                label='Spaces >',
                                command=partial(self.updateSpaces, selected=True, add=True),
                                parent=moduleLayout)
        newTextField = pm.textField('spacesTextField'+ str(self._index), 
                                    text=','.join(map(str,v)), 
                                    editable=True, 
                                    changeCommand=partial(self.updateSpaces, selected=False), 
                                    annotation='',
                                    parent=moduleLayout)

        pm.text('useSpaceBlendingText'+ str(self._index), 
                label='Use Space Blending',
                parent=moduleLayout)      
        newBool = pm.checkBox('useSpaceBlending_checkbox_' + str(self._index),
                              value=self.useSpaceBlending ,
                              label='',
                              changeCommand=partial(self.updateSpaces),
                              parent=moduleLayout)

        # space blending check box and layout
        pm.separator(height=self._separatorHeight, style="none", parent=moduleLayout)
        width = [(1, self._moduleCW[1][1])]
        moduleLayout1 = pm.rowColumnLayout(nc=1, cw=width, columnAlign = (1,'left'), parent=moduleLayout) 
        frameLayout = pm.frameLayout("_spaceBlendDictFrameLayout" + str(self._index), 
                                     label='Spaces', 
                                     bgc=self._color,
                                     collapsable=True, 
                                     collapse=False, 
                                     parent=moduleLayout1)
        moduleLayout2 = pm.rowColumnLayout(nc=1, cw=width, columnAlign = (1,'left'), parent=frameLayout)


        # store relevant ui for later use
        self.setUI('spaces', [newButton, newTextField])       
        self.setUI('_spaceBlendDict', [newBool, moduleLayout1, frameLayout, moduleLayout2]) 

        # create space weight list if space blending else treat normally
        self.updateSpaces()



    def updateSpaces(self, *args, **kwargs):
        """If spaces names are changed update the weight list accordingly"""

        # update spaces
        add = kwargs.get('add', False)
        selected= kwargs.get('selected', None)
        if selected != None:
            if selected:
                selected = pm.ls(sl = True, type='transform')
            else:
                selected = pm.textField(self.getUI('spaces')[-1],q=True,text=True)

            print('setNodeAttrSelected', selected, add)
            self.setNodeAttrSelected('spaces', selected=selected, add=add)

        # clear the weight controls
        check = self.getUI('_spaceBlendDict')
        self.useSpaceBlending = pm.checkBox(check[0], q=True, value=True)
        for ui in self.getUI('_spaceBlendDict')[4:]:
            pm.deleteUI(ui)
        check = check[:4]
        self.setUI('_spaceBlendDict', check)
        
        pm.frameLayout(check[2], e=True, collapse=not self.useSpaceBlending)

        # if not spaceblending skip
        if not self.useSpaceBlending:
            return
        
        get_name = lambda x: str(x).split('|:')[-1]

        # update the weight dictionary
        for item in self.spaces:
            tag = get_name(item)
            if self._spaceBlendDict.get(tag) == None:
                self._spaceBlendDict[tag] = 0.0

        check_names = [get_name(x) for x in self.spaces]
        for k in list(self._spaceBlendDict.keys()):
            if k not in check_names:
                del self._spaceBlendDict[k]

        # ensure at least some weight
        if self.spaces and not sum(self._spaceBlendDict.values()):
            self._spaceBlendDict[get_name(self.spaces[0])] = 1.0

        # remake the weight controls
        blends = []
        i=0
        for i,name in enumerate(self.spaces):    
            tag = get_name(name)
            new = pm.floatSliderGrp("_spaceBlendDict_{}_slider_{}".format(self._index, i),
                                    l=str(name), 
                                    value=self._spaceBlendDict[tag],
                                    step=0.001, 
                                    field=1, 
                                    min=0, 
                                    max=1,
                                    changeCommand=partial(dict.__setitem__, self._spaceBlendDict, tag),
                                    parent=check[-1])
            blends.append(new)
            i += 1

        self.setUI('_spaceBlendDict', check[:4] + blends)
     

    def updateRollTwistList(self, *args, **kwargs):
        add = kwargs.get('add', False)
        selected = kwargs.get('selected', None)
        listType = kwargs.get('listType', None)

        targetList = self.rollList if listType == 'rollList' else self.twistList
        # Handle selection
        if selected is not None:
            if selected:
                selectedNodes = pm.ls(sl=True, type='transform')
            else:
                ui_elements = self.getUI(listType)
                selectedNodes = pm.textField(ui_elements[-1], q=True, text=True)

            print('Selected nodes:', selectedNodes)
            self.setNodeAttrSelected(listType, selected=selectedNodes, add=add)
            
            if not add:
                targetList[:] = []

            for node in selectedNodes:
                nodeName = node.name() if isinstance(node, pm.PyNode) else str(node)
                if nodeName not in targetList:
                    targetList.append(nodeName)
            
        # ---- UI Update ----
        combinedList = list(dict.fromkeys(self.rollList + self.twistList))
        start_joint = getattr(self, 'startJoint', None) or getattr(self, 'shoulderJoint', None)

        #adding joints from keywords if they are not in list
        if start_joint:
            if self.twistKeyword:
                twistJoints = util.findAllInChain(start_joint, self.twistKeyword, allDescendents=True, disableWarning=True)
                if twistJoints:
                    for j in twistJoints:
                        jnt_name = j.name()
                        if jnt_name not in combinedList:
                            combinedList.append(jnt_name)
            if self.rollKeyword:
                rollJoints = util.findAllInChain(start_joint, self.rollKeyword, allDescendents=True, disableWarning=True)
                if rollJoints:
                    for j in rollJoints:
                        jnt_name = j.name()
                        if jnt_name not in combinedList:
                            combinedList.append(jnt_name)

        # clear the weight controls
        check = self.getUI('_rollTwistAmountDict')
        for ui in self.getUI('_rollTwistAmountDict')[4:]:
            pm.deleteUI(ui)
        check = check[:4]
        self.setUI('_rollTwistAmountDict', check)
             
        get_name = lambda x: str(x).split('|:')[-1]
        # update the weight dictionary
        for item in combinedList:
            tag = get_name(item)
            if self._rollTwistAmountDict.get(tag) == None:
                self._rollTwistAmountDict[tag] = 1.0

        check_names = [get_name(x) for x in combinedList]
        for k in list(self._rollTwistAmountDict.keys()):
            if k not in check_names:
                del self._rollTwistAmountDict[k]

        # Build new sliders
        newSliders = []
        i=0
        for i, name in enumerate(combinedList):
            tag = get_name(name)
            #print(f"Building slider for: {tag}")
            if tag not in self._rollTwistAmountDict:
                self._rollTwistAmountDict[tag] = 1.0  # Default weight

            slider = pm.floatSliderGrp(
                f"{listType}_{self._index}_slider_{i}",
                l=str(name),
                value=self._rollTwistAmountDict[tag],
                step=0.001,
                field=True,
                min=0,
                max=1,
                changeCommand=partial(dict.__setitem__, self._rollTwistAmountDict, tag),
                parent=check[-1]
            )
            newSliders.append(slider)
            i += 1

        self.setUI('_rollTwistAmountDict', check[:5] + newSliders)
     
    def findAndCreate(self,
                      root,
                      moduleSpaceSwitchList = None, 
                      group = None,
                      controlSize = 1.0,
                      mainCtrl=None,
                      **kwargs):
        """Search Root Node for keywords and issue create command
           Should Be overwritten for each node to get proper args"""
        return


    def createControlAttributes(self, ctrl):
        """Control visibility layers"""

        #if not hasattr(ctrl, '__iter__'):
        if not is_iterable(ctrl):
            ctrl = [ctrl]    
        for c in ctrl:
            pm.addAttr(c, ln = "controlLayer", at= "short", defaultValue=0, k=0)
            pm.setAttr(c.name() + ".controlLayer", self.controlLayer)

        return
    
    def setRetargetHintAttributes(self, ctrl, *args, **kwargs):
        """Write the retarget hints used to create retarget from skeleton to controls"""

        if cmds.objExists(ctrl + '.evoRetargetHint'):
            ctrl.deleteAttr('evoRetargetHint')
        if not retargets.modules.get(kwargs.get('retargetType')):
            label = 'Module ' + str(self._index+1) + '  -  ' + self._label + '  -  ' + self.keyword
            pm.warning('Invalid RetargetType "{}" for module "{}"'.format(kwargs.get('retargetType'),
                                                                           label))
            return

        ctrl.addAttr('evoRetargetHint', dt = 'string')
        ctrl.setAttr('evoRetargetHint', json.dumps([util.node_to_string(args), 
                                                    util.node_to_string(kwargs)]))

    def validate(self, root, *args, **kwargs):
        """Returns error string if invalid"""
        return

############# Get ctrl class from obj in Maya ###########

def networkToModule(networkNode, cls, keys=None):
    """
    Reads attributes on a network node and creates/returns an instance of the module class from the data
    
    :param pm.nt.Network networkNode: Network node to read attrs off of 
    :param Type[ModuleBase] cls: Class type of module to create an instance of
    :param keys: __dict__ keys to check for-- if None we will check all user-defined non-message attrs on the node
    
    """

    networkNode = pm.PyNode(networkNode)
    obj = cls()

    if keys is None:
        attrs = networkNode.listAttr(userDefined=True)
        keys = [a.attrName() for a in attrs if a.attrName() != "moduleClass" and a.type() != 'message']

    for k in keys:
        if not networkNode.hasAttr(k):
            continue
        # Attrs that start with _ are just menu options for the EvoRig UI
        if k.startswith('_'):
            continue

        plug = networkNode.attr(k)
        atype = plug.type()

        # read attrs
        if atype in ("bool", "long", "short", "byte", "double", "float"):
            setattr(obj, k, plug.get())
        elif atype == "string":
            s = plug.get()
            # try JSON decode; fall back to raw string
            try:
                setattr(obj, k, json.loads(s))
            except Exception:
                setattr(obj, k, s)
        else:
            # anything odd, store raw
            setattr(obj, k, plug.get())

    obj._moduleNetworkNodeName = networkNode.name()
    obj._rigNetworkNodeName = networkNode.parent.get().name()

    return obj

def instantiateModuleFromNetwork(networkNode):
    """
    Reads the module class from network node and returns an instance of the module
    
    :param pm.nt.Network networkNode: Network node whose data we want to read and create a module instance from 
    
    """

    networkNode = pm.PyNode(networkNode)
    clsPath = networkNode.attr("moduleClass").get()
    modName, clsName = clsPath.rsplit(".", 1)

    mod = importlib.import_module(modName)
    cls = getattr(mod, clsName)

    return networkToModule(networkNode, cls)


def findNetworkByInfo(rigNetwork, moduleClassStr, keywordStr):
    """
    Searches the rig network for a connected module network node matching class and keyword.

    :param pm.nt.Network rigNetwork: Main rig network node 
    :param str moduleClassStr: Name of class to look for (e.g. "cr_MakeEngineIK.engineIKCtrl").
    :param str keywordStr: Keyword identifying the module instance.

    :return: The matching module network node, or None if no match is found.
    :rtype: pm.nt.Network or None
    """

    rigNetwork = pm.PyNode(rigNetwork)
    modules = rigNetwork.modules.get()

    for mod in modules: 
        clsVal = mod.moduleClass.get()
        keyVal = mod.keyword.get()

        if clsVal == moduleClassStr and keyVal == keywordStr:
            return mod

    return None
