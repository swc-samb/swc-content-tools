

import os
import sys
import importlib

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from functools import partial

from wildcardRig.EvoRig import mb_rig_utilities as util


"""
size = 3 * self.settings.base_scale
		if GeoType == 'Diamond':
			node = pm.curve(d=1, name=Name, p=[(size, 0, -size), (size, 0, size), (-size, 0, size),
										   (-size, 0, -size), (size, 0, -size), (0, size, 0),
										   (-size, 0, size), (0, -size, 0), (size, 0, -size),
										   (size, 0, size), (0, size, 0), (-size, 0, -size),
										   (0, -size, 0), (size, 0, size)])
										   """

if 2 < sys.version_info.major < 3.4:
	reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
	reload = __import__('importlib').reload

if 2 < sys.version_info.major:
	xrange = range

reload(util)

__author__ = 'Michael Buettner'
__version__ = '0.2.2'

rigControlSizeSlider = "rigControlSizeSlider"

windowName = "Retarget Binder"

class RetargetBinderUI(object):
	def __init__(self):
		self.bindRotation = True
		self.bindTranslation = True
		self.snapRotation = False
		self.snapTranslation = False
		self.uiIndex = 0
		self.mainLayout = None
		self.controlSize = 1.0

		self.makeWindow()


	def initLayout(self):
		layout = self.mainLayout
		if layout is not None:  
			cmds.deleteUI(layout)
			
		mainColumn = pm.columnLayout(adjustableColumn=True, w=300, parent=self.window)
		self.mainLayout = mainColumn

		pm.rowColumnLayout(nc=2, cw=[(1, 150), (2, 150)], parent=mainColumn)

		

		self.toggleBindTranslationUI = pm.checkBox('toggleBindTranslationUI',
											value=self.bindTranslation,
											label='Bind Translation',
											changeCommand=partial(setattr, self, 'bindTranslation'))

		self.toggleBindRotationUI = pm.checkBox('toggleBindRotationUI',
											value=self.bindRotation,
											label='Bind Rotation',
											changeCommand=partial(setattr, self, 'bindRotation'))

		pm.separator(h=10, style="none")
		pm.separator(h=10, style="none")
		self.toggleSnapTranslationUI = pm.checkBox('toggleSnapTranslationUI',
											value=self.snapTranslation,
											label='Snap Translation',
											changeCommand=partial(setattr, self, 'snapTranslation'))

		self.toggleSnapRotationUI = pm.checkBox('toggleSnapRotationUI',
											value=self.snapRotation,
											label='Snap Rotation',
											changeCommand=partial(setattr, self, 'snapRotation'))

		pm.rowColumnLayout(nc=2, cw=[(1, 100), (2, 200)], parent=mainColumn)
		# size slider
		pm.text(label='Control Size', al='right')
		self.controlSizeUI = pm.floatSliderGrp(rigControlSizeSlider,
												l="",
												min=0.01,
												max=3,
												fieldMaxValue=100000,
												value=self.controlSize,
												step=0.01,
												field=1,
												cat=[1, 'left', -70],
												adj=1,
												changeCommand=partial(setattr, self, 'controlSize'))

		pm.rowColumnLayout(nc=1, cw=[(1, 300)], parent=mainColumn)

		pm.button(label='Basic Bind', command=self.basicBindCommand, annotation= 'Basic bind from source (1st selection) to destination (2nd selection). This is like a parent constraint.')
		pm.separator(h=5, style="none")
		pm.button(label='Complex Bind', command=self.complexBindCommand, annotation='Complex bind from source (1st selection) to destination (2nd selection). This treats rotation and translation separately.')
		pm.separator(h=5, style="none")
		pm.button(label='Relative Bind', command=self.relativeBindCommand, annotation='Bind joint from source (1st selection) to destination (2nd selection). Only local translation and no inherited rotation will translate the bound joint.')
		pm.separator(h=5, style="none")
		pm.button(label='Hierarchy Bind', command=self.hierarchyBindCommand, annotation='Bind all joints from source hierarchy (1st selection) to joints of same name in destination hierarchy (2nd selection) ')

	def show(self):
		cmds.showWindow(self.window)

	def doMakeNewWindow(self):
		self.window = pm.window(windowName + str(self.uiIndex),
									title=windowName,
									resizeToFitChildren=True,
									toolbox=False)  # widthHeight=(windowSize[0], windowSize[1])

	def makeWindow(self):
		windowSize = (200, 200)

		if not (cmds.window(windowName + str(self.uiIndex), exists=True)):
			print("Making window")
			self.doMakeNewWindow()
		else:
			cmds.deleteUI(windowName + str(self.uiIndex))
			print("Window already exists")
			self.doMakeNewWindow()

		self.initLayout()

		self.show()
		return self.window

	def getSelectedSourceAndTarget(self):
		sel = pm.ls(sl=True)
		if (len(sel) != 2):
			print("Need a selection of 2 objects to bind. Select Source first and Target second, then apply the binding.")
			return

		selfirst = sel[0]
		selsecond = sel[1]
		return selfirst, selsecond

	def basicBindCommand(self, args):
		print("Basic Bind")
		print(f"BindRotation {self.bindRotation} BindTranslation: {self.bindTranslation}")
		print(f"SnapRotation {self.snapRotation} SnapTranslation: {self.snapTranslation}")
		
		source,destination = self.getSelectedSourceAndTarget()

		ctrl = util.makeNurbsShape(15, name=destination + "_bind", forwardAxis='X')
		ctrl.setAttr("overrideEnabled", 1)
		ctrl.setAttr("overrideColor", 9)

		if self.snapTranslation:
			pm.parent(ctrl, source, r=True)
		else:
			pm.parent(ctrl, destination, r=True)

		pm.parent(ctrl, source, a=True)

		if (self.bindTranslation):
			pointConstraint = pm.pointConstraint(ctrl, destination, mo=not self.snapTranslation)
		if (self.bindRotation):
			orientConstraint = pm.orientConstraint(ctrl, destination, mo=not self.snapRotation)

		
		return
		

	def scaleCtrl(self, controlShape, tscale):
		spans = pm.getAttr(controlShape + ".spans")
		pm.select(controlShape + ".cv[0:" + str(spans) + "]", r=True )
		pm.scale(tscale[0] , tscale[1] , tscale[2], r=True)


	def complexBind(self, source, destination):
		ctrl = util.makeNurbsShape(15, name=destination + "_trans_bind", forwardAxis='X')	#Diamond
		ctrl.setAttr("overrideEnabled", 1)
		ctrl.setAttr("overrideColor", 9)
		rotCtrl = util.makeNurbsShape(8, name=destination + "_rot_bind", forwardAxis='X')	#Circle
		rotCtrl.setAttr("overrideEnabled", 1)
		rotCtrl.setAttr("overrideColor", 9)
		self.scaleCtrl(rotCtrl, [4,4,4])

		listRelativeJnts = source.listRelatives(p=True)
		if (len(listRelativeJnts) > 0):
			parentJnt = listRelativeJnts[0]
		else:
			parentJnt = source
		
		if self.snapTranslation:
			pm.parent(ctrl, source, r=True)
		else:
			pm.parent(ctrl, destination, r=True)
		pm.parent(ctrl, parentJnt, a=True)

		pm.orientConstraint(source, ctrl, mo=True)

		if self.snapRotation:
			pm.parent(rotCtrl, source, r=True)
		else:
			pm.parent(rotCtrl, destination, r=True)
		pm.parent(rotCtrl, ctrl, a=True)

		pm.parentConstraint(rotCtrl, destination, mo=not self.snapRotation)

		util.lockAndHideAttributes(ctrl, hideTranslation=False, hideRotation=True, hideScale=True)
		util.lockAndHideAttributes(rotCtrl, hideTranslation=True, hideRotation=False, hideScale=True)

		return
		
	def relativeBind(self, source, destination):
		
		readTranslateCtrl = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_read_bind_trans"))
		#readTranslateCtrl = util.makeNurbsShape(15, name=destination + "_read_bind_trans", forwardAxis='X')	#15 = Diamond
		readTranslateCtrl.setAttr("overrideEnabled", 1)
		readTranslateCtrl.setAttr("overrideColor", 7)
		readTranslateCtrl.hide()
		rotCtrl = util.makeNurbsShape(8, name=destination + "_bind_rotate_CON", scale=self.controlSize, forwardAxis='X')	#8 = Circle
		rotCtrl.setAttr("overrideEnabled", 1)
		rotCtrl.setAttr("overrideColor", 9)
		self.scaleCtrl(rotCtrl, [4,4,4])
		
		listRelativeJnts = source.listRelatives(p=True)
		if (len(listRelativeJnts) > 0):
			parentJnt = listRelativeJnts[0]
		else:
			parentJnt = source

		listDestParentJnts = destination.listRelatives(p=True)
		if (len(listDestParentJnts) > 0):
			destparentJnt = listDestParentJnts[0]
		else:
			destparentJnt = destination
		
		if self.snapTranslation:
			pm.parent(readTranslateCtrl, source, r=True)
		else:
			pm.parent(readTranslateCtrl, destination, r=True)
		pm.parent(readTranslateCtrl, parentJnt, a=True)
		#ctrlGrp = pm.group(em=True, n=destination + '_bind_INH', p=parentJnt)
		srcBase = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_src_bind_base"))
		#srcBase = util.makeNurbsShape(9, name=destination + "_src_bind_base", forwardAxis='X')	#Square
		srcBase.setAttr("overrideEnabled", 1)
		srcBase.setAttr("overrideColor", 8)
		pm.parent(srcBase, readTranslateCtrl, r=True)
		pm.parent(srcBase, parentJnt, a=True)
		pm.parent(readTranslateCtrl, srcBase, a=True)
		
		srcTransBase = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_src_bind_translate_base"))
		#srcTransBase = util.makeNurbsShape(9, name=destination + "_src_translate_base", forwardAxis='X')	#Square
		srcTransBase.setAttr("overrideEnabled", 1)
		srcTransBase.setAttr("overrideColor", 8)
		pm.parent(srcTransBase, readTranslateCtrl, r=True)
		pm.parent(srcTransBase, parentJnt, a=True)
		pm.pointConstraint(source, srcTransBase, mo=True)

		transctrl = util.makeNurbsShape(15, name=destination + "_bind_translate_CON", scale=self.controlSize, forwardAxis='X')	#Square
		transctrl.setAttr("overrideEnabled", 1)
		transctrl.setAttr("overrideColor", 9)
		pm.parent(transctrl, srcTransBase, r=True)

		#read translation of source + control
		pm.pointConstraint(transctrl, readTranslateCtrl, mo=True)	

		destInherit = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_dest_bind_INH"))
		#destInherit = util.makeNurbsShape(9, name=destination + "_dest_bind_INH", forwardAxis='X')	#Square
		destInherit.setAttr("overrideEnabled", 1)
		destInherit.setAttr("overrideColor", 7)
		pm.parent(destInherit, parentJnt, r=True)
		# Constrain destInherit by dest parent to allow adding the delta
		pm.parentConstraint(destparentJnt, destInherit, mo=not self.snapRotation)

		offsetctrl = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_dest_bind_offset"))
		#offsetctrl = util.makeNurbsShape(9, name=destination + "_dest_bind_offset", forwardAxis='X')	#Square
		offsetctrl.setAttr("overrideEnabled", 1)
		offsetctrl.setAttr("overrideColor", 7)
		pm.parent(offsetctrl, destination, r=True)
		pm.parent(offsetctrl, destInherit, a=True)

		writeTranslateCtrl = pm.createNode( 'transform', n=util.getNiceControllerName(destination.name(),"_write_translate_bind") , parent=offsetctrl)
		#writeTranslateCtrl = util.makeNurbsShape(9, name=destination + "_write_translate_bind", forwardAxis='X')	#Square
		writeTranslateCtrl.setAttr("overrideEnabled", 1)
		writeTranslateCtrl.setAttr("overrideColor", 9)
		pm.parent(writeTranslateCtrl, offsetctrl, r=True)
		#writeTranslateCtrl.hide()

		if self.snapRotation:
			pm.parent(rotCtrl, source, r=True)
		else:
			pm.parent(rotCtrl, destination, r=True)

		pm.parent(rotCtrl, writeTranslateCtrl, a=True)	#parent final control to offset/trans ctrl
		#Constrain rotation of writeTranslateCtrl
		pm.parentConstraint(source, writeTranslateCtrl, mo=True, skipTranslate=["x", "y", "z"])
		#pm.orientConstraint(source, transctrl, mo=True)
		#pm.pointConstraint(source, destInherit, mo=True)

		pm.connectAttr(readTranslateCtrl.name() + ".translate", writeTranslateCtrl.name() + ".translate")
		pm.parentConstraint(rotCtrl, destination, mo=not self.snapRotation)	#parent constrain dest

		util.lockAndHideAttributes(transctrl, hideTranslation=False, hideRotation=True, hideScale=True)
		util.lockAndHideAttributes(rotCtrl, hideTranslation=True, hideRotation=False, hideScale=True)

		return

	def complexBindCommand(self, args):
		print("Complex Bind - Always applies Translation and Rotation Bind.")

		source,destination = self.getSelectedSourceAndTarget()
		self.complexBind(source, destination)
		return
	
	def relativeBindCommand(self, args):
		print("Relative Bind - Always applies Translation and Rotation Bind.")

		source,destination = self.getSelectedSourceAndTarget()
		self.relativeBind(source, destination)
		return
	

	def hierarchyBindCommand(self, args):
		print("Hierarchy Bind - Binds all joints of a destination hierarchy.")
		
		source,destination = self.getSelectedSourceAndTarget()
		sourcechain = source.listRelatives(ad=True, type='joint')
		for i, srcJnt in enumerate(sourcechain):
			destJnt = util.findInChain(destination, srcJnt)
			print(f"Relative Binding {srcJnt} to {destJnt}")
			self.relativeBind(srcJnt, destJnt)



		
		









