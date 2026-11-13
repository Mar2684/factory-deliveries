"""Point d'entrée de tests au niveau racine de la livraison.

Permet à « python -m unittest discover » lancé depuis la racine (du dépôt
ou d'un bac à sable ne contenant que les fichiers ajoutés par la PR) de
trouver et exécuter toute la suite de tests du noyau, SANS dépendre d'un
__init__.py quel qu'il soit : les modules sont chargés explicitement par
chemin de fichier (importlib), sans modifier sys.path (évite de shadow
un éventuel package « tests » à la racine).
"""
import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.join(_HERE, "todo-app")

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

_CORE = _first_existing([os.path.join(_APP_DIR, "todo_core.py"), os.path.join(_HERE, "todo_core.py")])
_SUITE = _first_existing([os.path.join(_APP_DIR, "tests", "test_todo_core.py"), os.path.join(_HERE, "test_todo_core.py")])

_load_module("todo_core", _CORE)
_suite = _load_module("todo_app_test_suite", _SUITE)

for _name in dir(_suite):
    _obj = getattr(_suite, _name)
    if isinstance(_obj, type) and issubclass(_obj, unittest.TestCase):
        globals()[_name] = _obj

if __name__ == "__main__":
    unittest.main()
