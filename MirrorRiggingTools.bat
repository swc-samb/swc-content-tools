@echo off

robocopy "T:\Tools\Maya\PYTHON\wildcardRig\EvoRig" "T:\GitP4\Tools\Maya\PYTHON\WildcardRig\EvoRig" /COPY:DAT
robocopy "T:\Tools\Maya\PYTHON\wildcardAnim" "T:\GitP4\Tools\Maya\PYTHON\wildcardAnim" mb_MirrorAnimation.py EvoRigIKFKSwitch.py spaceSwitching.py arkAnimExporterUI.py spaceSwitching.py /COPY:DAT
robocopy "T:\Tools\Maya\PYTHON\wildcardModel" "T:\GitP4\Tools\Maya\PYTHON\wildcardModel" export_static_mesh_fbx.py /COPY:DAT
robocopy "T:\Tools\Maya\ICONS" "T:\GitP4\Tools\Maya\ICONS" MirrorAnimation_Icon.png /COPY:DAT
robocopy "T:\Tools\Maya\ICONS" "T:\GitP4\Tools\Maya\ICONS" alter.png /COPY:DAT
robocopy "T:\Tools\Maya\SHELVES" "T:\GitP4\Tools\Maya\SHELVES" shelf_wildcardModding.mel /COPY:DAT

exit /B