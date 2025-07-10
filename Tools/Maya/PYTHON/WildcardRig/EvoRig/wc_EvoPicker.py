
import os
import sys
import re
import json
from functools import cmp_to_key, partial
from collections import OrderedDict as od


import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

from wildcardAnim import mb_MirrorAnimation
from wildcardAnim import spaceSwitching, EvoRigIKFKSwitch

__author__ = 'Ethan McCaughey'
__version__ = '1.0.1'


PREFIXES = {'right':'^r_|^right_|^rt_|^rgt_|^rght_|^ri_',
            'left':'^l_|^left_|^lt_|^lft_|^lf_',
            'center':'^c_|^center_|^ct_|^cnt_|^cntr_|^ctr_'}



#------------------------------------------------------------------------------
# Utility Functions
#------------------------------------------------------------------------------


def getNamespace(item):
    '''return namepace string'''

    namespace = ''
    if ':' in str(item):                
        namespace = ':'.join(str(item).split(':')[:-1]) + ':'
    return namespace


def flattenSets(item, done=None):
    '''flatten querying sets is busted for some reason'''

    # check to prevent inifinite loops
    check = done or {}
    if check.get(item):
        return
    check[item] = True

    # iterate through set items and recurse any sub sets
    result = []
    for child in pm.sets(item,q=True):
        if check.get(child):
            continue
        if isinstance(child, pm.nodetypes.ObjectSet):
            result.extend(flattenSets(child,check))
        else:
            result.append(child)
    return result


def subSets(item, done=None):
    '''Return all sets contained in set item'''

    # check to prevent infinite loops
    check = done or {}
    if check.get(item):
        return
    check[item] = True

    # iterate through set items and recurse any sub sets
    result = []
    for child in pm.sets(item,q=True):
        if check.get(child):
            continue
        if isinstance(child, pm.nodetypes.ObjectSet):
            result.append(item)
            result += (subSets(child,check))

    return result


def controlJoint(item):
    '''find neares object in itemList to item without expensive sorting'''

    # if item is a set return the top hierarchy joint for all controllers in set if any
    if isinstance(item, pm.nodetypes.ObjectSet):
        return (list(map(controlJoint,sorted(flattenSets(item), key=jsort))) or [None])[0]

    # get per controller rig settings from evo retarget hints
    if not cmds.objExists('{}.evoRetargetHint'.format(item)):
        return None
    args,kwargs = json.loads(item.getAttr('evoRetargetHint'))
    source = kwargs['source']

    # return source joint in current namespace
    namespace = getNamespace(item)
    name = '|'.join('{}{}'.format(namespace,x) for x in source.split('|') if x)
    return (pm.ls(name) or [None])[0]


def jsort(item):
    '''Sort Ctrls by source joint hierarchy length if any else sort to last'''

    # ensure sets with equal source joint hierarchy length subsort by number of subsets 
    offset = 0
    if isinstance(item, pm.nodetypes.ObjectSet):
        offset += 1.0-(0.5/(len(subSets(item)) or 1.0))

    # get source joint hierarchy length
    check = controlJoint(item)
    if check:
        return len(check.longName().split('|')) + offset
    else:
        return sys.float_info.max


def jsortList(itemList):
    '''Splits list into sets, ctrls with matching joints, and ctrls without matching joints
       - sorts sets and ctrls with matching control Joints by jsort
       - sorts unmatched controls alphabetically.
       - return sets + ctrls + unmatched ctrls'''

    # more robust sorter
    sets, matched_ctrls, unmatched_ctrls = [], [], []
    for item in itemList:
        if not controlJoint(item):
            unmatched_ctrls.append(item)
        elif isinstance(item, pm.nodetypes.ObjectSet):
            sets.append(item)
        else:
            matched_ctrls.append(item)

    sorted_sets = od()
    sorted_matched = od()
    sorted_unmatched = od()

    for unsorted_list, sorted_list in zip((sets, matched_ctrls, unmatched_ctrls), 
                                 (sorted_sets, sorted_matched, sorted_unmatched)):
        for item in unsorted_list:
            index = jsort(item)
            if sorted_list.get(index):
                sorted_list[index].append(item)
            else:
                sorted_list[index] = [item]

    result = []
    for unsorted_list in (sorted_sets, sorted_matched, sorted_unmatched):
        for index,item_list in sorted(unsorted_list.items()):
            result.extend(sorted(item_list))

    return result

    # sets.sort(key=jsort)
    # matched_ctrls.sort(key=jsort)
    # unmatched_ctrls.sort()

    # return sorted(sets + matched_ctrls + unmatched_ctrls)


def groupChain(itemList):
    '''Returns itemList grouped by name with nubmers removed key OrderedDict
       Good for autogrouping chains'''
    
    sortedList = jsortList(itemList)

    # group into OrderedDict by name with numbers removed key
    groups = od()
    for child in sortedList:
        basename = re.sub('_?[0-9]+','',str(child).split('|')[-1].split(':')[-1]).replace('_ctrl_set', '')
        if not groups.get(basename):
            groups[basename] = []
        groups[basename].append(child)

    for group in groups.values():
        group.sort()

    return groups

def prefixSide(name):
    basename = str(name).split(':')[-1].split('|')[-1]
    for side,regex in PREFIXES.items():
        if re.findall(regex, basename, re.IGNORECASE):
            return side

def prefixColor(item, button=False, overrideName=None):
    '''Color based on name prefix'''

    basename = overrideName or str(item).split('|')[-1].split(':')[-1]
    color = [0.2,0.4,0.2]
    bar = 0.1
    ik_highlight = 0.5
    side = prefixSide(basename)
    suffixCheck = re.sub('_?CON$|_?ctrl$|_?ctl$','', basename, re.IGNORECASE)
    
    if side == 'right':
        color = [0.5,0.15,0.15]
        #bar = 0.075
    elif side == 'left':
        color = [0.2,0.2,0.5]
        #bar = 0.05
    elif side == 'center':
        color = [0.5,0.5,0.2]
        ik_highlight = 0.45

    if not button:
        color = [n-bar for n in color]

    if not isinstance(item, pm.nodetypes.ObjectSet) and not isinstance(item, list):
        if re.findall('ik$', suffixCheck, re.IGNORECASE) and not re.findall('engineik$', suffixCheck, re.IGNORECASE):
            color = [n+ik_highlight for n in color]

    return color


def getRigAllControlSets(joints=None):
    '''Get  All Control Sets from joints or scene'''

    if joints and not isinstance(joints, list):
        joints = [joints]

    joints = joints or pm.ls(type='joint',r=1)
    # get rig set name for any root bone with rigGroup attribute
    rigSets = ['{}_AllControls_set'.format(x.getAttr('rigGroup')) for x in joints if cmds.objExists('{}.rigGroup'.format(x))]
    return pm.ls(*set(rigSets), r=1)
    

def getRigHierarchalSets(joints=None):
    '''Get Hierarchal Control Sets from joints or scene'''

    if joints and not isinstance(joints, list):
        joints = [joints]

    joints = joints or pm.ls(type='joint',r=1)
    # get rig set name for any root bone with rigGroup attribute
    rigSets = ['{}_set'.format(x.getAttr('rigGroup')) for x in joints if cmds.objExists('{}.rigGroup'.format(x))]
    return pm.ls(*set(rigSets), r=1)


def getMirror(item):
    '''Return mirror of item by prefix, same if there isnt a side prefix'''
    side = prefixSide(item)
    mirror = item
    if side in ['right','left']:
        prefix = (re.findall(PREFIXES['right'] + '|' + PREFIXES['left'], str(item), re.IGNORECASE) or [''])[0]
        search = '*' + str(item).split('|')[-1][len(prefix):]
        mirror = ([x for x in pm.ls(search) if prefixSide(x) != side] or [item])[0]
    return mirror

#------------------------------------------------------------------------------
# Utility Classes
#------------------------------------------------------------------------------

class boolSettingsNodeDict(dict):
    '''Stores and retrieves bool settings in renderLayer node'''
    def __init__(self):
        self.name = 'EvoPickerSettings'
        self.node = (cmds.ls(self.name) or cmds.createNode('renderLayer', ss=True, name=self.name))[0]

    def __setitem__(self, key, value):
        key = '_'.join(re.findall('[_a-zA-Z]+', str(key)))
        attr = self.node + '.' + key
        if not cmds.objExists(attr):
            self.node = (cmds.ls(self.name) or cmds.createNode('renderLayer', ss=True, name=self.name))[0]
            cmds.addAttr(self.node, ln=key, at='float')
        cmds.setAttr(attr,float(value))
    
    def __getitem__(self, key):
        key = '_'.join(re.findall('[_a-zA-Z]+', str(key)))
        attr = self.node + '.' + key
        if not cmds.objExists(attr):
            self.node = (cmds.ls(self.name) or cmds.createNode('renderLayer', ss=True, name=self.name))[0]
            cmds.addAttr(self.node, ln=key, at='float')
            return False
        else:
            return bool(cmds.getAttr(attr))


#------------------------------------------------------------------------------
# UI Classes
#------------------------------------------------------------------------------


class AutoPickerUI(object):
    '''Picker UI class'''

    def __init__(self):    
        self.window = None
        self.formLayout = None
        self.collapsed = boolSettingsNodeDict()
        self.frames = {}
        self.roots = [x for x in pm.ls(type='joint',r=1) if cmds.objExists('{}.rigGroup'.format(x)) and x.getAttr('rigGroup')]

        if not self.roots:
            pm.warning('No Evo Rigs Found!')
            return

        self.makeWindow()


    def makeWindow(self):
        # create window
        windowName = 'EvoPicker'
        if cmds.window(windowName + str(0), exists=True):
            pm.deleteUI(windowName + str(0))

        self.window = pm.window(windowName + str(0),
                                title=windowName,
                                # width=800,
                                # height=600,
                                resizeToFitChildren=True) 
        self.initLayout()
        pm.window(self.window, e=True, width=300, height=300)
        self.show()


    def show(self):
        pm.showWindow(self.window)
    
    
    def initLayout(self): 
        '''Main layout'''

        # reset form layout
        if self.formLayout is not None:
            pm.deleteUI(self.formLayout)

        self.formLayout = pm.formLayout(parent=self.window)

        # create tablayout and adjust formlayout
        self.tabs = pm.tabLayout(innerMarginWidth=5, innerMarginHeight=5, parent=self.formLayout)
        pm.formLayout(self.formLayout, 
                      edit=True, 
                      attachForm=((self.tabs, 'top', 0), 
                                  (self.tabs, 'left', 0), 
                                  (self.tabs, 'bottom', 0), 
                                  (self.tabs, 'right', 0)))       
        # do the tabs                           
        self.initRigTabs()
    

    def initRigTabs(self):
        '''Create a Picker button tab for each Rig_AllControls_set'''

        # iterate through EvoRig control sets
        tabs = od()
        for root in self.roots:
            
            rigSet = (getRigAllControlSets(root) or [None])[0]
            if not rigSet:
                pm.warning('EvoPicker: Rig All Controls set not found for "{}"'.format(root))
                continue

            # get namespace
            namespace = getNamespace(rigSet)

            # get simple name
            if namespace:
                name = [x for x in namespace.split(':') if x][-1]
            else:
                name = os.path.basename(cmds.file(q=True,sn=True)).split('.')[0] or 'untitled'

            # add index numbers if multiple references with the same name
            while tabs.get(name):
                index = int(re.findall('[0-9]+$', name) or [0])[0] + 1
                name = '{} {}'.format(re.sub('[0-9]+$', '', name), index)

            # main tab layout
            # tabs[name] = pm.rowColumnLayout(numberOfColumns=1, parent=self.tabs)
            tabs[name] = pm.formLayout(parent=self.tabs)

            # scroll layout for button sets
            scrollLayout = pm.scrollLayout(childResizable=False,
                                        #    width=900, 
                                        #    height=800, 
                                           parent=tabs[name])

            pm.formLayout(tabs[name], 
                            edit=True, 
                            attachForm=(
                                        (scrollLayout, 'top', 0), 
                                        (scrollLayout, 'left', 0), 
                                        (scrollLayout, 'bottom', 0), 
                                        (scrollLayout, 'right', 0))) 
            
            
            rowFormLayout = pm.formLayout(parent=scrollLayout)
            rowColumnLayout = pm.rowColumnLayout(numberOfColumns=3)

            pm.formLayout(rowFormLayout, 
                            edit=True, 
                            attachForm=(
                                        (rowColumnLayout, 'top', 0), 
                                        (rowColumnLayout, 'left', 0), 
                                        (rowColumnLayout, 'bottom', 0), 
                                        (rowColumnLayout, 'right', 0))) 


            # check for hierarchal sets
            controlSet = (getRigHierarchalSets(root) or [rigSet])[0]

            # seperate major controls with subsets like legs,arms,splines from simple fk ctrls
            # sort major controls by number of sub sets

            subCount = lambda x: -len(subSets(x))            
            controlSets = [x for x in pm.sets(controlSet, q=True) if subSets(x)] or pm.sets(controlSet, q=True)
            controlSets.sort(key=subCount)
            extraSets = [x for x in pm.sets(controlSet, q=True) if x not in controlSets and not subSets(x)]
            majorExtras = {}

            # try to match extra sets with a major set by nearest joint parent
            if extraSets: 
                # relevant controls
                majorControls = {x:True for xl in map(flattenSets,controlSets) for x in xl}
                extraControls = [x for xl in map(flattenSets,extraSets) for x in xl]

                # control to source joint                
                majorJoints = {x:controlJoint(x) for x in sorted(majorControls.keys(), key=subCount) if controlJoint(x)}
                jointMajors = {majorJoints[m]:m for m in reversed(sorted(majorJoints.keys(), key=subCount))}
                extraJoints = {x:controlJoint(x) for x in extraControls}

                # control to set lookup dictionaries
                lookupExtra = {}
                for extraSet in extraSets:
                     for x in pm.sets(extraSet, q=True):
                         lookupExtra[x] = extraSet
                lookupMajor = {}
                for majorSet in controlSets:
                     for x in flattenSets(majorSet):
                         lookupMajor[x] = majorSet

                # match extra controls to a major control by nearest joint parent
                # if no major control is up the joint chain, treat as a major control

                for extra, joint in extraJoints.items():
                    major = jointMajors.get(joint)
                    while joint and not major:
                        joint = (pm.listRelatives(joint,p=True) or [None])[0]
                        major = jointMajors.get(joint)

                    if major:
                        majorSet = lookupMajor[major]
                        if not majorExtras.get(majorSet):
                            majorExtras[majorSet] = []
                        majorExtras[majorSet].append(extra)
                    else:
                        extraSet = lookupExtra[extra]
                        if extraSet in extraSets:
                            del extraSets[extraSets.index(extraSet)]
                            controlSets.append(extraSet)

            # split into left, center, and right columns
            sideSorted = od([(x,[]) for x in ['left','center','right']])
            for item in controlSets:
                sideSorted[prefixSide(item) or 'center'].append(item)
            
            #create column for each side
            for side,controls in sideSorted.items():
                columnLayout = pm.columnLayout(parent=rowColumnLayout)

                # iterate through ctrl set and create button group hierarchy
                sortedList = jsortList(controls)
                for item in reversed(sortedList):
                    extras =  majorExtras.get(item)
                    current = self.initGroupLayout(item, columnLayout, extras)

                    # group on extra joints
                    if extras:
                        self.initGroupLayout(extras, current)

            
            # Layout for global buttons
            
            pm.separator(parent=tabs[name],height=20)

            buttonFormLayout = pm.formLayout(parent=tabs[name])
            # buttonColumn = pm.rowColumnLayout(numberOfColumns=4, parent=buttonFormLayout)

            pm.formLayout(tabs[name], 
                            edit=True, 
                            attachForm=(
                                        # (buttonFormLayout, 'top', 0), 
                                        (buttonFormLayout, 'left', 0), 
                                        (buttonFormLayout, 'bottom', 0), 
                                        (buttonFormLayout, 'right', 0)),
                         ) 
            
            buttonColumn = pm.rowColumnLayout(numberOfColumns=4, parent=buttonFormLayout)

            
            pm.formLayout(tabs[name], 
                            edit=True, 
                            attachControl = (scrollLayout, 'bottom', 0, buttonFormLayout),
                         ) 
            
                            
            buttonWidth = 210

            # Select All Button
            pm.button(label='Select All',
                      width=buttonWidth,
                      command=partial(self.select,list(map(str,flattenSets(rigSet)))))

            # Reset Selected Transforms
            pm.button(label='Reset Selected',
                      width=buttonWidth,
                      command=partial(self.resetSelected))

            # Collapse All Frames
            pm.button(label='Collapse All',
                      width=buttonWidth,
                      command=partial(self.collapseAll, True))

            # Expand All Frames
            pm.button(label='Expand All',
                      width=buttonWidth,
                      command=partial(self.collapseAll, False))

            # Select Mirror 
            pm.button(label='Select Mirror',
                      width=buttonWidth,
                      command=partial(self.selectMirror))

            # Mirror Tool
            pm.button(label='Mirror Tool',
                      width=buttonWidth,
                      command=partial(lambda x: mb_MirrorAnimation.makeWindow()))

            # Space Switching Tool
            pm.button(label='Space Switching Tool',
                      width=buttonWidth,
                      command=partial(lambda x: spaceSwitching.main()))

            # IKFK Switch Tool
            pm.button(label='IKFK Switch',
                      width=buttonWidth,
                      command=partial(lambda x: EvoRigIKFKSwitch.ikfk_switch_cmd()))


        # label tabs
        pm.tabLayout(self.tabs, 
                     edit=True, 
                     tabLabel=((uiItem, name) for name, uiItem in tabs.items()))


    def initGroupLayout(self, item, parent, extras=None, overrideName=None):  
        '''create button for controls, frameLayout for sets and recurse set items'''

        # flatten lists of length 1
        if isinstance(item, list) and len(item) == 1:
            item = item[0]
            
        isSet = isinstance(item, pm.nodetypes.ObjectSet)
        isList = isinstance(item, list)

        # buttons for items
        if not isSet and not isList:
            basename = str(item).split('|')[-1].split(':')[-1]
            button = pm.button(label=basename,
                               #width=200,
                               bgc=prefixColor(item, button=True),
                               parent=parent,
                               command=partial(self.select,str(item)))
            return button

        rowColumnLayout = cmds.rowColumnLayout(numberOfColumns=2, parent=parent)

        # get all children from set or treat item as all children
        if isSet:
            label = overrideName or str(item).split(':')[-1].replace('_ctrl_set', '')
            allItems = list(map(str,flattenSets(item) + (extras or [])))
            basename = str(item).split('|')[-1].split(':')[-1]
        else:
            label = overrideName or 'fk children'
            allItems = list(map(str,item + (extras or [])))
            basename = label


        color = prefixColor(item, overrideName=basename)

        # select all children button
        pm.button(label='All',
                  parent=rowColumnLayout,
                  bgc=color,
                  command=partial(self.select,allItems))


        # frame layout for sets
        frameLayout = pm.frameLayout("frameLayout" + str(item).replace(':', '_'), 
                                     label=label, 
                                     bgc=color,
                                     collapsable=True, 
                                     collapse=self.collapsed[str(item)], 
                                     cc=partial(self.collapsed.__setitem__, str(item), True),
                                     ec=partial(self.collapsed.__setitem__, str(item), False),
                                     parent=rowColumnLayout)
        columnLayout = pm.columnLayout(parent=frameLayout)
        self.frames[str(item)] = frameLayout
        
        if isSet:
            children = pm.sets(item,q=True)
        else:
            children = item[:]

        # group children into chain groups if their names only differ by number
        # then recurse
        
        # print('item', item)
        # print('children', children)

        chainGroup = groupChain(children)        
        if len(chainGroup) == 1:
            # if single grouping iterate through list normally
            children = jsortList(children)
            for child in children:
                self.initGroupLayout(child, columnLayout)
        else:
            # else iterate through chain group results
            for name, group in chainGroup.items():
                self.initGroupLayout(group, columnLayout, overrideName=name)

        return columnLayout


    def select(self, *args, **kwargs):
        '''Select objects respecting Control and Shift modifiers'''
        item = args
        mods = pm.getModifiers()
        shift = (mods & 1) > 0
        ctrl = (mods & 4) > 0
        
        pm.select(pm.ls(item), 
                  cl = not bool(pm.ls(item)),
                  r = not ctrl and not shift,
                  tgl = shift and not ctrl,
                  d = ctrl and not shift,
                  add = ctrl and shift)

            
    def selectMirror(self, *args, **kwargs):
        '''Select Mirror of selected Objects respecting Control and Shift modifiers'''
        self.select(list(map(getMirror,pm.ls(sl=True))))


    def resetSelected(self, _):
        '''Reset Translate, Rotate, and Scale attributes back to default'''

        #pm.makeIdentity(pm.ls(sl=True), t=True,r=True,s=True,a=False)
        
        # This is faster and less problematic... so far.
        for item in pm.ls(sl=True):
            for a,v in ([('t',0), ('r',0), ('s',1)]):
                for n in ['x','y','z']:
                    if not item.getAttr(a+n,l=True):
                        item.setAttr(a+n,v)


    def collapseAll(self, value, _):
        '''Set collapsed on all frames to value'''
        for name, frame in list(self.frames.items()):
            pm.frameLayout(frame, edit=True, collapse=value)
            self.collapsed[name] = value

        
        



