import os
import sys
from collections import OrderedDict as od;
import importlib

if 2 < sys.version_info.major < 3.4:
    reload = __import__('imp').reload
elif sys.version_info.major > 3.4:
    reload = importlib.reload

# Dynamically import only classes from this folder only if VALID_ATTRIBUTE is True

VALID_ATTRIBUTE = '_isCtrl'
g = globals()
folder = os.path.dirname(__file__)
sys.path.insert(0,folder)
modules = od()

# Look through this folder
for f in os.listdir(folder):
    # Only python files that arent this file
    if os.path.isfile(os.path.join(folder,f)) and os.path.splitext(f)[-1].lower() == '.py' and f != os.path.basename(__file__):
        # Look through the classes in that file
        module = importlib.import_module(os.path.splitext(f)[0])
        found = False
        for name,obj in module.__dict__.items():
            # If it has a valid attribute and is defined in this file (not imported)
            if hasattr(obj, VALID_ATTRIBUTE) and getattr(obj, VALID_ATTRIBUTE) and obj.__module__.lower() == os.path.splitext(f)[0].lower():
                modules[obj._label], g[name] = obj,obj
                found = True
        if found:
            reload(module)

# Cleanup extras
del g['os']
del g['sys']
del g['od']
del g['importlib']
del g['folder']
del g['f']



# import os
# import re
# import sys
# import inspect
# from collections import OrderedDict as od;
# import importlib

# g = globals()
# folder = os.path.dirname(__file__)

# #dynamic importing has reloading issues, solved by correct 
# #dependency order reloaded, fewest to highest dependencies

# def refDepth(mod, depth = 0):
#     '''Calculates level of dependencies for modules in this folder'''
#     if not inspect.ismodule(mod):
#         return depth
#     minDepth = depth
#     for name, item in mod.__dict__.items():
#         if inspect.isfunction(item):
#             funcMod = sys.modules[item.__module__]
#             if funcMod != mod:
#                 minDepth = max(minDepth, refDepth(funcMod, depth+1))
#             continue
#         if not inspect.ismodule(item):
#             continue
#         if not hasattr(item, '__file__') or folder not in item.__file__:
#             continue        
#         minDepth = max(refDepth(item, depth+1), minDepth)
#     return max(minDepth, depth)
# importSort = lambda x: refDepth(__import__(x, globals(), locals(), [], -1))

# #dynamically find modules
# moduleLoads = [x.split('.')[0] for x in os.listdir(folder) if re.findall('([^_]+\.py$)|([^_]+\.py?$)', x)]
# moduleLoads.sort(key = importSort)

# #force reloading
# for item in moduleLoads:
#     reload(__import__(item, globals(), locals(), [], -1))

# modules = od()
# #find ctrl classes and import them to keep wc module less cluttered
# for item in moduleLoads:
#     module = __import__(item, globals(), locals(), [], -1)
#     for name, obj in module.__dict__.items():
#         if hasattr(obj, '_isCtrl') and obj._isCtrl:
#             g[name] = obj
#             modules[g[name]._label] = g[name]


# #cleaning up leftovers to keep wc module less cluttered
# del g['od']
# del g['x']
# del g['refDepth']
# del g['importSort']
# del g['item']
# del g['module']
# del g['inspect']
# del g['re']
# del g['name']
# del g['obj']
# del g['sys']
# del g['os']
# del g['folder']
# del g['g']

