# Mirror Animation
# By Michael Buettner
#
# Copyright 2017 Wildcard Studios
# July 11, 2017
#
''' 
Usage:
    
import mb_MirrorAnimation
mb_MirrorAnimation.makeWindow()

'''


__author__ = 'Michael Buettner'
__version__ = '2.2.0'

import pymel.core as pm
import maya.cmds as mc
import maya.mel as mm
import logging
#import numpy as np
import pymel.core.datatypes as pymeldt
import math
import types

import sys, os

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
    reload = __import__('importlib').reload

pathDidExist = True

if 'MAYA_TOOLS_PATH' in os.environ.keys():
    path = os.path.join(os.environ['MAYA_TOOLS_PATH'],'PYTHON\\wildcardRig')

else:
    path = 'T:\\Tools\\Maya\\PYTHON\\wildcardRig'
    if not os.path.exists(path):
        pathDidExist = False
        path = os.path.join(mc.internalVar(uad = True), 'scripts\\wildcard\\PYTHON\\wildcardRig')

path = os.path.normpath(path) 
    
if path in sys.path:
    del sys.path[sys.path.index(path)]
sys.path.insert(1, path)

def deletePYC(path):
    for item in os.listdir(path):
        filepath = os.path.join(path, item)
        if os.path.isdir(filepath):
            deletePYC(filepath)
        else:
            if '.' in item and 'pyc' == item.lower().split('.')[-1]:
                os.remove(filepath)
                print('deleting {}'.format(filepath))
if pathDidExist:
    deletePYC(os.path.join(path, 'EvoRig'))


from EvoRig import mb_rig_utilities as util
reload(util)

logging.basicConfig(level=logging.DEBUG)


worldkeywordsinput = 'wld_ WristIk_ ROOT_ ElbowIk_ LowerArmIk_ TopIk_ FootIk_ Neck Head'
worldkeywords = worldkeywordsinput.split()
worldTransKeywordsInput = '_hand_ik_'
worldTransKeywords = worldTransKeywordsInput.split()
bCurrentFrame = True
leftprefix = 'l_'
rightprefix = 'r_'
optionsObjectName = 'mb_MirrorAnimation_Options'

def makeWindow():
    #Type in the name and the size of the window
    windowName = "mb_MirrorAnimation"
    windowSize = (240, 330)
    #check to see if this window already exists
    if (mc.window(windowName , exists=True)):
        mc.deleteUI(windowName)
    window = mc.window( windowName, title= windowName, widthHeight=(windowSize[0], windowSize[1]) , resizeToFitChildren=True)
    #Type your UI code here
    mc.columnLayout( "mainColumn", adjustableColumn=True )
    mc.text( label='Version '+ __version__, al='right' )
	

    
    currentFrameBox = mc.checkBox("nameCurrentFrameBox", label = "Current Time", annotation='Only copy or flip the key at current time. When off: Operate on animation curve', value = bCurrentFrame, parent = "mainColumn")

    #Mirror Button
    mc.columnLayout( "columnName02", columnAttach=('both', 5), rowSpacing=5, columnWidth=250)
    mc.button(label = "Mirror Selected", command = mirrorButton, annotation='Mirrors animation from selected to unselected Objects on other side', parent = "columnName02")
    mc.button(label = "Swap", command = swapButton, bgc=(.7,.5,0), annotation='Swaps animation between right and left', parent = "columnName02")
    mc.button(label = "Mirror Left to Right", command = leftToRightButton, bgc=(0,0,0.7), annotation='Mirrors animation from left to right', parent = "columnName02")
    mc.button(label = "Mirror Right to Left", command = rightToLeftButton, bgc=(0.7,0,0), annotation='Mirrors animation from right to left', parent = "columnName02")
    
    
    #Mirror single curve or pose buttons
    mc.frameLayout ("layoutFrame01", label = "Flip Curves", collapsable = True, parent = "mainColumn")
    mc.rowColumnLayout('rowColumnLayout01', numberOfColumns = 3,columnWidth=[(1, 80), (2, 80), (3, 80)])
    #mc.gridLayout("nameGridLayout01", numberOfRowsColumns = (2,3), cellWidthHeight = (80,20), parent = "flipCurveColumn")
    mc.button(label = "Translation X", command = pm.Callback(flipAttributeCurve, "translateX"), annotation='Flip Translate X curve/pose', parent = "rowColumnLayout01")
    mc.button(label = "Translation Y", command = pm.Callback(flipAttributeCurve, "translateY"), annotation='Flip Translate Y curve/pose', parent = "rowColumnLayout01")
    mc.button(label = "Translation Z", command = pm.Callback(flipAttributeCurve, "translateZ"), annotation='Flip Translate Z curve/pose', parent = "rowColumnLayout01")
    mc.button(label = "Rotation X", command = pm.Callback(flipAttributeCurve, "rotateX"), annotation='Flip Rotate X curve/pose', parent = "rowColumnLayout01")
    mc.button(label = "Rotation Y", command = pm.Callback(flipAttributeCurve, "rotateY"), annotation='Flip Rotate Y curve/pose', parent = "rowColumnLayout01")
    mc.button(label = "Rotation Z", command = pm.Callback(flipAttributeCurve, "rotateZ"), annotation='Flip Rotate Z curve/pose', parent = "rowColumnLayout01")
    
    
    mc.frameLayout ("layoutFrame00", label = "Setup", collapsable = True, collapse=True, parent = "mainColumn")
    #World Orientation TextField
    refcheck = True
    optionsObject = findOptionsObject()
    if optionsObject:
        refcheck = not(mc.referenceQuery(optionsObject, inr = True))
    """mc.text( label='World Orientation Controls', al='left' , parent = "layoutFrame00")
    mc.textField( "nameWorldOrientationTextField", text = worldkeywordsinput, changeCommand=changeWorldOrientationText, annotation='Controls matching any of these keywords will be treated as world aligned coordinates', enable=refcheck, parent = "layoutFrame00")
    
    mc.text( label='World Translation, Local Orient Controls', al='left' , parent = "layoutFrame00")
    mc.textField( "nameWorldTranslationTextField", text = worldTransKeywordsInput, changeCommand=changeWorldTranslationText, annotation='Controls matching any of these keywords will be treated as world aligned translation but local orientation coordinates', enable=refcheck, parent = "layoutFrame00")
    """ 
    mc.button(label = "Initialize Mirroring System", command = pm.Callback(initMirror), annotation='Initialize Mirroring System on selected controls', enable=refcheck, bgc=(0.7,0.7,0), parent = "layoutFrame00")
    

    mc.text( label='Left Keyword', al='left' , parent = "layoutFrame00")
    mc.textField( "nameLeftKeywordTextField", text = leftprefix, changeCommand=changeLeftKeywordText, annotation='left keyword', enable=refcheck, parent = "layoutFrame00")

    mc.text( label='Right Keyword', al='left' , parent = "layoutFrame00")
    mc.textField( "nameRightKeywordTextField", text = rightprefix, changeCommand=changeRightKeywordText, annotation='right keyword', enable=refcheck, parent = "layoutFrame00")
    """
    mc.text( label='Center Controls Forward Axis', al='left' , parent = "layoutFrame00")
   
    
    DirectionControl = mc.radioCollection('nameCenterForwardAxis')
    Direction0 = mc.radioButton( label='X', cc=centerForwardX)
    mc.radioButton( label='Y', cc=centerForwardY)
    mc.radioButton( label='Z', cc=centerForwardZ)
    #DirectionControl = mc.radioCollection( DirectionControl, edit=True, select=Direction0 )
    """

    #Mirror single curve or pose buttons
    mc.frameLayout ("layoutFrame02", label = "Curves", collapsable = True, parent = "mainColumn")
    mc.rowColumnLayout('rowColumnLayout02', numberOfColumns = 2,columnWidth=[(1, 100), (2, 100)])
    #mc.gridLayout("nameGridLayout02", numberOfRowsColumns = (2,2), cellWidthHeight = (100,20), parent = "layoutFrame02")
    mc.button(label = "Enable Cycle", command = setCurvesToCycle, annotation='Set curves to pre- and post-infinity cycle', parent = "rowColumnLayout02")

    mc.columnLayout( "helpColumn", adjustableColumn=True, parent = "mainColumn" )
    mc.helpLine()
    
    loadMirrorOptions()
    
    mc.showWindow( windowName )
    # Resize the main window
    #
    # This is a workaround to get MEL global variable value in Python
    #gMainWindow = maya.mel.eval('$tmpVar=$gMainWindow')
    mc.window( windowName, edit=True, widthHeight=(windowSize[0], windowSize[1]) )



def addMirrorAttribs(ctrl, mirrorAlign, leftAxis):
    exists = pm.attributeQuery("mirrorAlign", node=ctrl, exists=True)
    if exists:
        pm.deleteAttr(ctrl, at="mirrorAlign")
    
    pm.addAttr(ctrl.name(), ln = "mirrorAlign", attributeType="float3", k=0)
    pm.addAttr(ctrl.name(),longName='mirrorAlign'+'X', attributeType='float', parent='mirrorAlign')
    pm.addAttr(ctrl.name(),longName='mirrorAlign'+'Y', attributeType='float', parent='mirrorAlign')
    pm.addAttr(ctrl.name(),longName='mirrorAlign'+'Z', attributeType='float', parent='mirrorAlign')
    
    pm.setAttr(ctrl.name() + ".mirrorAlign", mirrorAlign, type="float3")

    exists = pm.attributeQuery("mirrorLeftAxisIndex", node=ctrl, exists=True)
    if exists:
        pm.deleteAttr(ctrl, at="mirrorLeftAxisIndex")
    pm.addAttr(ctrl.name(), ln = "mirrorLeftAxisIndex", attributeType="long", k=0)
    pm.setAttr(ctrl.name() + ".mirrorLeftAxisIndex", leftAxis)

""" If the axes of two controls line up after rotating 180 degrees (in radians: pi) around the mirror axis (default: X), """
""" then the controls are mirrored and we know that we should not flip any rotation when mirroring animation curves. """
def areMatricesMirrored(a, b, mirrorAxis=pymeldt.Vector(1,0,0)):
    
    rotateEulerAngles = (math.pi * mirrorAxis.x, math.pi * mirrorAxis.y, math.pi * mirrorAxis.z)

    rotatematch = True
    for i in range(3):
        A = pymeldt.Vector(a[i][0:3])         #np.array(a[i])
        B = pymeldt.Vector(b[i][0:3])         #np.array(b[i])
        rotatedA = A.rotateBy(rotateEulerAngles)
        #axisName = ['X','Y','Z']
        #print("{} -  Vector A: {}".format(axisName[i], A))
        #print("{} -  Vector B: {}".format(axisName[i], B))
        #print("{} - rotated A: {}".format(axisName[i], rotatedA))
        
        if not (rotatedA.dot(B) > 0.99):        #rotated vector does not match B, so this is not a mirrored Vector
            rotatematch = False

    return rotatematch
    

def compareAxes(cona, conb, mirrorAxis = [1.0, 0.0, 0.0, 0.0]):
    a = cona.getAttr('worldMatrix')
    b = conb.getAttr('worldMatrix')
    output = []
    leftAxisIndex = 0
    mirrorAxisDot = 0.0
    maxMirrorAxisDot = 0.0
    mirr = pymeldt.Vector(mirrorAxis[0:3])
    for i in range(3):
        #initialize arrays
        A = pymeldt.Vector(a[i][0:3])         #np.array(a[i])
        B = pymeldt.Vector(b[i][0:3])         #np.array(b[i])
        mirrorAxisDot = A.dot(mirr)    #np.dot(A, mirr)
        if abs(mirrorAxisDot) > maxMirrorAxisDot:
            maxMirrorAxisDot = abs(mirrorAxisDot)
            leftAxisIndex = i
            
        #axisName = ['X','Y','Z']
        #print("{} - Vector A: {} B: {}".format(axisName[i], A, B))
        #print("Dot of Mirror Axis: {}".format(mirrorAxisDot))
        output.append(math.copysign(1.0, A.dot(B)))
    #print("Left Axis is: {}".format(axisName[leftAxisIndex])) 

    if (areMatricesMirrored(a, b, mirr)):
        if mirr.x == 1.0:
            output = [1, -1, -1]
            leftAxisIndex = 0
        elif mirr.y == 1.0:
            output = [-1, 1, -1]
            leftAxisIndex = 1
        else:
            output = [-1, -1, 1]
            leftAxisIndex = 2

    addMirrorAttribs(cona, output, leftAxisIndex)
    addMirrorAttribs(conb, output, leftAxisIndex)
    
    return(output, leftAxisIndex)
    


def initMirror(controls=[], leftprefix='', rightprefix=''):
    sel = None
    if len(controls) == 0:
        sel = pm.ls(sl=True)
        if len(sel) < 1:
            logging.warning('At least one control must be selected. Select all controls first, then run this.')
            return
    else:
        sel = controls
    
    if len(leftprefix) == 0:
        leftprefix = str(mc.textField( "nameLeftKeywordTextField", query=True, text=True))
        rightprefix = str(mc.textField( "nameRightKeywordTextField", query=True, text=True))
    worldUpAxis = pm.upAxis(q=True, axis=True).upper()
    sceneMirrorAxis = [1.0, 0.0, 0.0, 0.0]
    if worldUpAxis == 'Y':
        sceneMirrorAxis = [1.0, 0.0, 0.0, 0.0]
    else:
        sceneMirrorAxis = [0.0, 1.0, 0.0, 0.0]

    for a in sel:
        #print("--Init Mirror--")
        #print("original: {}".format(a.name()) )
        try:
            b = pm.PyNode(util.mirrorName(a.name(), leftPrefix=leftprefix, rightPrefix=rightprefix) )
            #print("mirrored: {}".format(b))
            axisAlignment, leftAxisIndex = compareAxes(a, b, mirrorAxis = sceneMirrorAxis)
            #print("align: {} left axis index: {}".format(axisAlignment, leftAxisIndex))
        except Exception as e:
            print("Error:")
            print(type(e))
            print(e)
            print("initMirror() did not find mirrored control for name: {}".format(a.name()))
            continue
        #matrix = a.getAttr('worldMatrix')
        #bmatrix = b.getAttr('worldMatrix')

    createOptionsObject(leftprefix=leftprefix, rightprefix=rightprefix)

    return

def updateCenterFowardAxis(axisName):
    optionsObject = findOptionsObject()
    if not optionsObject:
        createOptionsObject()  
    mc.setAttr(optionsObjectName + ".centerForwardAxis", axisName, type='string')

def centerForwardX(on):
    #print('centerForwardX ' + str(on))
    if on:
        updateCenterFowardAxis('X')

def centerForwardY(on):
    if on:
        updateCenterFowardAxis('Y')

def centerForwardZ(on):
    if on:
        updateCenterFowardAxis('Z')

def createOptionsObject(leftprefix='', rightprefix=''):
    #attrExist = maya.cmds.attributeQuery(attr, node=obj, exists=True)
    #if not attrExist:
    # create an empty group
    #mc.group(empty = True, name = optionsObjectName)
    sel = mc.ls(sl=True)

    optionsObject = findOptionsObject()
    if optionsObject:
        pm.delete(optionsObject)

    pm.createNode( 'geometryVarGroup', name=optionsObjectName, skipSelect=True)
    #Add Attributes to new object
    mc.addAttr(optionsObjectName, ln='leftprefixText', dt="string", k=True)
    mc.addAttr(optionsObjectName, ln='rightprefixText', dt="string", k=True)
    

    #Fill new attributes with current values
    if len(leftprefix) == 0:
        leftprefix = str(mc.textField( "nameLeftKeywordTextField", query=True, text=True))
    mc.setAttr (optionsObjectName + ".leftprefixText", leftprefix, type='string')
    if len(rightprefix) == 0:
        rightprefix = str(mc.textField( "nameRightKeywordTextField", query=True, text=True))
    mc.setAttr (optionsObjectName + ".rightprefixText", rightprefix, type='string')

    #worldkeywords = str(mc.textField( "nameWorldOrientationTextField", query=True, text=True))
    #mc.setAttr (optionsObjectName + ".worldOrientationText", worldkeywords, type='string')
    #worldTranslationKeywords = str(mc.textField( "nameWorldTranslationTextField", query=True, text=True))
    #mc.setAttr (optionsObjectName + ".worldTranslationText", worldTranslationKeywords, type='string')

    #radioCol = mc.radioCollection('nameCenterForwardAxis', query=True, sl=True)
    #if radioCol != 'NONE':
    #    centerForwardAxis = mc.radioButton(radioCol, query=True, label=True)
    #else:
    #    centerForwardAxis = 'X'
    #updateCenterFowardAxis(centerForwardAxis)


def loadMirrorOptions():
    optionsObject = findOptionsObject()
    if optionsObject:
        logging.debug('Loading Mirror Options')
        try:
            leftprefix = mc.getAttr(optionsObject + ".leftprefixText")
            mc.textField( "nameLeftKeywordTextField", edit=True, text=leftprefix)
            rightprefix = mc.getAttr(optionsObject + ".rightprefixText")
            mc.textField( "nameRightKeywordTextField", edit=True, text=rightprefix)
        except:
            pass
        """
        try:
            centerForwardAxis = mc.getAttr(optionsObject + ".centerForwardAxis")
            radioCollectionItems = mc.radioCollection('nameCenterForwardAxis', query=True, collectionItemArray=True)
            if centerForwardAxis == 'X':
                i = 0
            elif centerForwardAxis == 'Y':
                i = 1
            else:
                i = 2
            mc.radioCollection('nameCenterForwardAxis', edit=True, select=radioCollectionItems[i])
        except:
            pass
        """
        


def changeWorldOrientationText(args):
    logging.debug('changeWorldOrientationText ' + str(args))
    
    worldkeywords = args#str(mc.textField( "nameWorldOrientationTextField", query=True, text=True))
     #mc.ls(name='mb_MirrorAnimation_Options')
    optionsObject = findOptionsObject()
    if not optionsObject:
        createOptionsObject()  
    # set Values
    mc.setAttr (optionsObjectName + ".worldOrientationText", worldkeywords, type='string')


def changeWorldTranslationText(args):
    logging.debug('changeWorldOrientationText ' + str(args))
    
    worldTranslationKeywords = args

    optionsObject = findOptionsObject()
    if not optionsObject:
        createOptionsObject()
    # set Values
    mc.setAttr (optionsObjectName + ".worldTranslationText", worldTranslationKeywords, type='string')


def changeLeftKeywordText(args):
    logging.debug('changeLeftKeywordText ' + str(args))
    leftprefix = args
    optionsObject = findOptionsObject()
    if not optionsObject:
        createOptionsObject()
    # set Values
    mc.setAttr (optionsObjectName + ".leftprefixText", leftprefix, type='string')

def changeRightKeywordText(args):
    logging.debug('changeRightKeywordText ' + str(args))
    rightprefix = args
    optionsObject = findOptionsObject()
    if not optionsObject:
        createOptionsObject()
    # set Values
    mc.setAttr (optionsObjectName + ".rightprefixText", rightprefix, type='string')
	
def findOptionsObject():
    optionsObject = mc.ls(optionsObjectName)
    if len(optionsObject) > 0:
        return optionsObject[0]
    else:
        optionsObject = mc.ls('*:'+optionsObjectName)
        if len(optionsObject) > 0:
            return optionsObject[0]
    return None
		        
  
    

def setCurvesToCycle(args):
    mc.setInfinity( pri='cycle', poi='cycle' )
    

def flipAttributeCurve(attribute):
    sel = mc.ls(sl=True)
    bCurrentFrame = mc.checkBox("nameCurrentFrameBox", query=True, value=True)
    #logging.debug('Using Current Frame is:' + str(bCurrentFrame))
    for a in sel:
        if bCurrentFrame:
            t = mc.currentTime( query=True )
            mc.scaleKey( a, time=(t,t), vs = -1.0, vp = 0.0 , at = attribute);
        else:
            mc.scaleKey( a, vs = -1.0, vp = 0.0 , at = attribute);

def mirrorScaleKey(ctrl):
    """
    worldkeywords = str(mc.textField( "nameWorldOrientationTextField", query=True, text=True)).split()
    worldTransKeywords = str(mc.textField( "nameWorldTranslationTextField", query=True, text=True)).split()

    radioCol = mc.radioCollection('nameCenterForwardAxis', query=True, sl=True)
    if radioCol != 'NONE':
        centerForwardAxis = mc.radioButton(radioCol, query=True, label=True)
    else:
        centerForwardAxis = 'X'
    print('centerFowardAxis: ' + str(centerForwardAxis))
    """
    ctrl = pm.PyNode(ctrl)
    #flipzkeywords = str(mc.textField( "nameFlipZTextField", query=True, text=True)).split()
    t = mc.currentTime(query=True)
    #logging.debug('time is: '+str(t))
    bCurrentFrame = mc.checkBox("nameCurrentFrameBox", query=True, value=True)
    start, end = getStartAndEnd()
    timestartend = (start, end)
    if bCurrentFrame:
        timestartend = (t,t)

    
    mirrorAlign = ctrl.getAttr("mirrorAlign")
    leftAxis = int(ctrl.getAttr("mirrorLeftAxisIndex"))

    axisNames = ['X', 'Y', 'Z']
    worldUpAxis = pm.upAxis(q=True, axis=True).upper()

    for i in range(3):
        align = mirrorAlign[i]
        translateAlign = align

        if i == leftAxis:
            align *= -1
        else:
            translateAlign *= -1

        if align > 0:
            #print('Flipping rotate{}'.format(axisNames[i]))
            pm.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotate" + axisNames[i])
    
        hasJointOrient = 0.0
        if ctrl.nodeType() == 'joint':  #Joint controls can have world orient translation. Check if jointOrient is non-zero
            jntori = ctrl.getAttr('jointOrient')
            x = pymeldt.Vector(jntori)
            hasJointOrient = x.dot(x)
            
        if hasJointOrient > 0.1:       #Joint controls is a joint and has joint orient set, so mirror only X
                flipAxis = 0
                if worldUpAxis == 'Z':
                    flipAxis = 1

                if i == flipAxis:
                    #print('Flipping translate{} (Has joint orient)'.format(axisNames[i]))
                    pm.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translate" + axisNames[i])
        else:
            if translateAlign > 0:
                #print('Flipping translate{}'.format(axisNames[i]))
                pm.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translate" + axisNames[i])

    """
    worldUpAxis = pm.upAxis(q=True, axis=True).upper()

    if any(word in str(ctrl) for word in worldTransKeywords):
        if worldUpAxis == 'Y':
            print('Treating Control ' + str(ctrl) + ' as world translation coordinates (Y-Up) with local orient, flipping translateX')
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateX")
        else:
            print('Treating Control ' + str(ctrl) + ' as world translation coordinates (Z-Up) with local orient, flipping translateY')
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateY")
    elif any(word in str(ctrl) for word in worldkeywords):
        
        if worldUpAxis == 'Y':
            print('Treating Control ' + str(ctrl) + ' as world coordinates (Y-Up), flipping translateX and rotation Y Z')
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateX")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateY")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateZ")
        else:
            print('Treating Control ' + str(ctrl) + ' as world coordinates (Z-Up), flipping translateX and rotation X Z')
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateY")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateX")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateZ")
    else:
        side = sourceSide(str(ctrl))
        if (side.find('center') > -1):
            if centerForwardAxis == 'X':
                print('Treating Control ' + str(ctrl) + ' as center coordinates (X), flipping translateY and rotation X Z')
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateX")
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateZ")

                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateY")
            elif centerForwardAxis == 'Y':
                print('Treating Control ' + str(ctrl) + ' as center coordinates (Y), flipping translateZ and rotation X Y')
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateX")
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateY")
                #if any(word in str(ctrl) for word in flipzkeywords):
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateZ")
            elif centerForwardAxis == 'Z':
                print('Treating Control ' + str(ctrl) + ' as center coordinates (Z), flipping translateX and rotation Y Z')
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateY")   
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "rotateZ")
                mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateX")
        else:
            print('Treating Control ' + str(ctrl) + ' as mirrored coordinates, flipping translate X Y Z')
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateX")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateY")
            mc.scaleKey( ctrl, time = timestartend, vs = -1.0, vp = 0.0 , at = "translateZ")
    """


def getStartAndEnd():
    start = mc.playbackOptions(query=True, minTime=True)
    end = mc.playbackOptions(query=True, maxTime=True)
    return start, end

def swapAnim(src,dest, start, end, pasteOption):
    locator = pm.spaceLocator(name="copyAnimLocator")
    #locator = mc.ls(sl=True)[0]
    destnode = pm.ls(dest)[0] # get pymel node
    attrList = destnode.listAttr(ud=True)
    #logging.debug('Attributes List: ' +str(attrList))
    for attr in attrList:
        newType = pm.getAttr(attr,type=True)
        #settable = pm.getAttr(attr,se=True)
        locked = pm.getAttr(attr, lock=True)
        keyable = pm.getAttr(attr,k=True)
        if keyable and not locked:
            if newType.find('string') == -1: #Ignore strings
                #logging.debug('Looping Attribute: ' + str(attr.shortName()) +  ' Type: ' + newType)
                pm.addAttr(locator, longName=attr.shortName(), at=newType, k=True)
    
    locatorName = str(locator)
    #logging.debug('Locator: ' + locatorName)
    
    mc.select(src)
    affectedLayers = (mc.animLayer(query=True, affectedLayers=True))
    mc.select(locatorName)
    #affectedLayers = mc.ls(type='animLayer')
    if affectedLayers:
        for layer in affectedLayers:
            muted = mc.animLayer(layer, query=True, mute=True)
            if not muted:
                mc.animLayer(layer, edit=True, addSelectedObjects=True)
    
    copyPasteAnim(dest,locatorName, start, end, pasteOption)
    copyPasteAnim(src,dest, start, end, pasteOption)
    copyPasteAnim(locatorName,src, start, end, pasteOption)
    mc.delete(locatorName)
    
def copyPasteAnim(src,dest,start,end, pasteOption):
    #logging.debug('Copy-pasting Src: ' + src +' Dest:' + dest + ' Start:' + str(start) + ' End:' + str(end) + ' option:' + pasteOption)
    animCurves = mc.keyframe(src, query=True, name=True)
    if not animCurves:
        return

    autoKeyState = mc.autoKeyframe(query=True, state=True)
    if not animCurves or not autoKeyState:
        #logging.warning('No anim curve on source found / Autokey disabled. Adding a key')
        mc.setKeyframe(src)
        animCurves = mc.keyframe(src, query=True, name=True)
    
    if (pasteOption == 'replaceCompletely'):
        mc.copyKey(src ,t = (start - 1000, end +1000))
        mc.pasteKey(dest, option = pasteOption)
    else:
        cutTemp = list()
        if not hasattr(animCurves, '__iter__'):
            logging.warning(f"Skipped because animCurves of {src} are not iterable. AnimCurves: {animCurves}")
            return

        for curve in animCurves:
            tempKey = mc.keyframe(curve, time=(start,), query=True, timeChange=True)
            if not tempKey:
                #logging.debug('Setting temp key on frame ' + str(start))
                mc.setKeyframe(curve, time=(start,), insert=True)
                cutTemp.append(curve)
                
            mc.copyKey(src, time=(start,end))
            mc.pasteKey(dest, option=pasteOption, time=(start,end), copies=1, connect=0, timeOffset=0)
            #delete temp key
            if cutTemp:
                if (dest.find(src) != -1):
                    #logging.debug('Source equal to destination')
                    mc.keyTangent(curve, outAngle=0, inAngle=0, time=(start,end))
                    #itt='linear', ott='linear')
                else:
                    mc.cutKey(cutTemp, time=(start,))
            #mc.setKeyframe(dest, itt='auto', ott='auto')
    
    
def sourceSide(src):
    leftprefix = str(mc.textField( "nameLeftKeywordTextField", query=True, text=True))
    rightprefix = str(mc.textField( "nameRightKeywordTextField", query=True, text=True))
    #logging.debug('Finding side for ' + src)
    if (src.find(':') > -1):
        src = src.split(':')[1]
    if src.find(leftprefix) == 0:
        return 'left'
    elif (src.find('_'+leftprefix) > 0):
        return 'left'
    elif src.find(rightprefix) == 0:
        return 'right'
    elif (src.find('_'+rightprefix) > 0):
        return 'right'
    else:
        return 'center'

def mirror(direction='selected'):
    sel = mc.ls(sl=True)
    """if len(sel) == 1:
        mirrorScaleKey(sel[0])
    elif len(sel) == 2:"""
    if len(sel) < 1:
        logging.warning('At least one control must be selected')
        return
    
    leftprefixes = [p.strip() for p in str(mc.textField( "nameLeftKeywordTextField", query=True, text=True)).split(",")]
    rightprefixes = [p.strip() for p in str(mc.textField( "nameRightKeywordTextField", query=True, text=True)).split(",")]
    mirrored = []
    for leftprefix, rightprefix in list(zip(leftprefixes, rightprefixes)):

        if leftprefix.startswith('_'):
            check_start = False
        else:
            check_start = True

        for a in sel:
            src = str(a)
        
            existsAlign = mc.attributeQuery("mirrorAlign", node=src, exists=True)
            existsLeft = mc.attributeQuery("mirrorLeftAxisIndex", node=src, exists=True)

            if existsAlign == False or existsLeft == False:
                confirm = mc.confirmDialog(title='Confirm', 
                                            message=f'Did not find mirror data on control: {a}. Cancelling operation.', 
                                            button=['OK'], 
                                            defaultButton='OK')
                print(f"Did not find mirror data on control: {a}. You need to select all controls and initialize the mirroring system in bind pose first.")
                return
            
            bSrcWasRight = False
            bSrcWasLeft = False
            shortSrc = src
            nameSpace = False
            if (shortSrc.find(':') > -1):
                split =  src.split(':')
                shortSrc = split[-1]
                nameSpace = ':'.join(split[:-1])
            dest = shortSrc

            # Face rig has side indication in middle, but normally we should only be checking start
            if not check_start:
                if leftprefix in shortSrc:
                    dest = shortSrc.replace(leftprefix, rightprefix, 1)
                    bSrcWasLeft = True

                elif rightprefix in shortSrc:
                    dest = shortSrc.replace(rightprefix, leftprefix, 1)
                    bSrcWasRight = True
            else:
                if shortSrc.startswith(leftprefix):
                    dest = shortSrc.replace(leftprefix, rightprefix, 1)
                    bSrcWasLeft = True

                elif shortSrc.startswith(rightprefix):
                    dest = shortSrc.replace(rightprefix, leftprefix, 1)
                    bSrcWasRight = True

            if not bSrcWasRight and not bSrcWasLeft:
                all_prefixes = leftprefixes + rightprefixes
                check_prefixes = [x for x in all_prefixes if not x in [leftprefix, rightprefix]]
                # Make sure actually center not just using other type of prefix
                if any(p for p in check_prefixes if p and p in shortSrc):
                    continue
                else:
                    # Make sure we don't go over node twice
                    if not a in mirrored:
                        bSrcWasCenter = True
                        mirrored.append(a)
                    else:
                        continue

            if nameSpace:
                dest = ':'.join([nameSpace, dest])       

            if direction == 'ltor':
                if bSrcWasRight:
                    temp = dest
                    dest = src
                    src = temp
            elif direction == 'rtol':
                if bSrcWasRight==False:
                    temp = dest
                    dest = src
                    src = temp
            elif direction == 'swap':
                if bSrcWasRight:
                    if dest in sel:    #Prevent swapping twice if both sides are selected
                        continue        #If swapping from right to left and destination was selected, skip

            if (len(mc.ls(dest)) == 0):    #No destination control found
                logging.warning('No destination control found: ' + dest)
                continue
            if (len(mc.ls(src)) == 0):    #No src control found
                logging.warning('No source control found: ' + src)
                continue
                
            #logging.debug('Copying from Source: ' + src + ' to Dest: ' + dest)
            start, end = getStartAndEnd()
            t = mc.currentTime(query=True)
            pasteOption = 'replaceCompletely'
            bCurrentFrame = mc.checkBox("nameCurrentFrameBox", query=True, value=True)
            if bCurrentFrame:
                start = t
                end = t
                pasteOption = 'merge'
            
            #autoKeyState = mc.autoKeyframe(query=True, state=True)
            #mc.autoKeyframe(state=True)

            if direction == 'swap':
                if (dest.find(src) == -1):
                    #logging.debug('Source is not equal to destination')
                    swapAnim(src, dest, start, end, pasteOption)
                    mirrorScaleKey(src)
                else:
                    copyPasteAnim(src, dest, start, end, pasteOption) #Create key in case there is none
                mirrorScaleKey(dest)
            else:
                copyPasteAnim(src, dest, start, end, pasteOption)
                mirrorScaleKey(dest)

            #mc.autoKeyframe(state=autoKeyState)
        
def mirrorButton(args):
    mirror('selected')
    
def leftToRightButton(args):
    mirror('ltor')

def rightToLeftButton(args):
    mirror('rtol')
    
def swapButton(args):
    sel = mc.ls(sl=True)
    mirror('swap')
    mc.select(sel)

#makeWindow()
