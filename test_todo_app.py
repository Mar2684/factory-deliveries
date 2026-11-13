"""Point d'entree de tests (decouverte unittest sans dependre d'un __init__.py).
"""
import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

def _first_existing(candidates):
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(candidates)

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

_CORE = _first_existing([
    os.path.join(_HERE, "todo_core.py"),
    os.path.join(_HERE, "todo-app", "todo_core.py"),
    os.path.join(os.path.dirname(_HERE), "todo-app", "todo_core.py"),
])
_SUITE = _first_existing([
    os.path.join(_HERE, "tests", "test_todo_core.py"),
    os.path.join(_HERE, "todo-app", "tests", "test_todo_core.py"),
    os.path.join(os.path.dirname(_HERE), "todo-app", "tests", "test_todo_core.py"),
    os.path.join(_HERE, "test_todo_core.py"),
])

_load_module("todo_core", _CORE)
_suite = _load_module("todo_app_test_suite", _SUITE)

for _name in dir(_suite):
    _obj = getattr(_suite, _name)
    if isinstance(_obj, type) and issubclass(_obj, unittest.TestCase):
        globals()[_name] = _obj

if __name__ == "__main__":
    unittest.main()
