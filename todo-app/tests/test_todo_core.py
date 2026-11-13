"""Tests unitaires du noyau todo_core (unittest, stdlib uniquement).

Aucune dépendance web, aucun accès réseau : on manipule uniquement des
fichiers temporaires (tempfile.TemporaryDirectory).

Lancement :
    depuis todo-app/        : python -m unittest discover -s tests -t . -v
    depuis la racine dépôt  : la CI lance python -m unittest discover -s tests -t .
                              à la racine (elle ne voit que tests/ racine).
"""

import json
import os
import sys
import tempfile
import threading
import unittest

# Bootstrap d'import robuste : fonctionne que le module soit importé comme
# « todo-app.tests.test_todo_core », « tests.test_todo_core » ou exécuté en script.
import os as _os
import sys as _sys
_APP_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _APP_DIR not in _sys.path:
    _sys.path.insert(0, _APP_DIR)
from todo_core import Task, TaskStore  # noqa: E402


class TaskTest(unittest.TestCase):
    def test_id_is_uuid4_hex_by_default(self):
        task = Task(title="x")
        self.assertIsInstance(task.id, str)
        self.assertEqual(len(task.id), 32)
        int(task.id, 16)  # lève ValueError si ce n'est pas de l'hexadécimal
        self.assertFalse(task.done)

    def test_to_dict_keys_and_values(self):
        task = Task(id="abc", title="t", done=True)
        self.assertEqual(task.to_dict(), {"id": "abc", "title": "t", "done": True})

    def test_from_dict_roundtrip(self):
        task = Task(title="une tâche", done=True)
        clone = Task.from_dict(task.to_dict())
        self.assertEqual(clone, task)

    def test_from_dict_invalid(self):
        for bad in (None, 42, "x", ["id"], {}, {"id": "a", "title": "b"},
                    {"id": 1, "title": "b", "done": False}):
            with self.assertRaises(ValueError):
                Task.from_dict(bad)


class TaskStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "tasks.json")

    def _store(self):
        return TaskStore(self.path)

    # ------------------------------------------------------------ chargement
    def test_missing_file_gives_empty_list(self):
        store = self._store()
        self.assertEqual(store.list(), [])
        self.assertEqual(len(store), 0)
        # le chargement ne crée pas le fichier
        self.assertFalse(os.path.exists(self.path))

    def test_invalid_content_not_a_list_raises_value_error(self):
        for bad in ('{"a": 1}', "42", '"texte"', "null", "not json at all", ""):
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(bad)
            with self.assertRaises(ValueError, msg=f"contenu: {bad!r}"):
                TaskStore(self.path)

    def test_invalid_task_item_raises_value_error(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump([{"id": "a", "title": "b"}], fh)  # "done" manquant
        with self.assertRaises(ValueError):
            TaskStore(self.path)

    # ------------------------------------------------------------------ add
    def test_add_returns_task_and_keeps_order(self):
        store = self._store()
        t1 = store.add("première")
        t2 = store.add("deuxième")
        t3 = store.add("troisième")
        self.assertIsInstance(t1, Task)
        self.assertEqual(t1.title, "première")
        self.assertFalse(t1.done)
        self.assertEqual([t.title for t in store.list()],
                         ["première", "deuxième", "troisième"])
        self.assertEqual([t.id for t in store.list()], [t1.id, t2.id, t3.id])

    def test_add_empty_or_blank_title_raises_value_error(self):
        store = self._store()
        for bad in ("", "   ", " \t\n "):
            with self.assertRaises(ValueError, msg=f"titre: {bad!r}"):
                store.add(bad)
        self.assertEqual(store.list(), [])

    def test_ids_are_unique(self):
        store = self._store()
        tasks = [store.add(f"tâche {i}") for i in range(200)]
        ids = [t.id for t in tasks]
        self.assertEqual(len(ids), len(set(ids)))

    # -------------------------------------------------------------- get/complete
    def test_get_known_and_unknown(self):
        store = self._store()
        task = store.add("x")
        self.assertEqual(store.get(task.id).title, "x")
        with self.assertRaises(KeyError):
            store.get("id-inconnu")

    def test_complete_marks_done_and_persists(self):
        store = self._store()
        task = store.add("x")
        done_task = store.complete(task.id)
        self.assertTrue(done_task.done)
        self.assertTrue(store.get(task.id).done)

    def test_set_done_toggles_both_ways(self):
        store = self._store()
        task = store.add("x")
        self.assertTrue(store.set_done(task.id, True).done)
        self.assertFalse(store.set_done(task.id, False).done)

    def test_complete_and_set_done_unknown_id_raise_key_error(self):
        store = self._store()
        store.add("x")
        with self.assertRaises(KeyError):
            store.complete("id-inconnu")
        with self.assertRaises(KeyError):
            store.set_done("id-inconnu", True)

    # ---------------------------------------------------------------- delete
    def test_delete_removes_task(self):
        store = self._store()
        t1 = store.add("a")
        t2 = store.add("b")
        store.delete(t1.id)
        self.assertEqual([t.title for t in store.list()], ["b"])
        self.assertEqual(store.get(t2.id).title, "b")
        with self.assertRaises(KeyError):
            store.get(t1.id)

    def test_delete_unknown_id_raises_key_error(self):
        store = self._store()
        store.add("a")
        with self.assertRaises(KeyError):
            store.delete("id-inconnu")

    # ------------------------------------------------------------ persistance
    def test_persistence_roundtrip_on_new_instance(self):
        store = self._store()
        t1 = store.add("acheter du pain")
        t2 = store.add("lire un livre")
        t3 = store.add("écrire un test ✅")
        store.complete(t2.id)
        store.delete(t3.id)

        reloaded = TaskStore(self.path)  # NOUVELLE instance, même fichier
        tasks = reloaded.list()
        self.assertEqual([(t.id, t.title, t.done) for t in tasks],
                         [(t1.id, "acheter du pain", False),
                          (t2.id, "lire un livre", True)])

    def test_each_mutation_persists_immediately(self):
        store = self._store()
        task = store.add("immédiat")
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, [{"id": task.id, "title": "immédiat", "done": False}])

        store.complete(task.id)
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data[0]["done"], True)

        store.delete(task.id)
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, [])

    def test_exact_json_format_written_on_disk(self):
        store = self._store()
        t1 = store.add("Acheter du pain")
        t2 = store.add("Écrire ✅")
        store.complete(t1.id)
        expected = [
            {"id": t1.id, "title": "Acheter du pain", "done": True},
            {"id": t2.id, "title": "Écrire ✅", "done": False},
        ]
        with open(self.path, encoding="utf-8") as fh:
            raw = fh.read()
        # format exact : liste JSON compacte (ensure_ascii=False) + saut de ligne
        self.assertEqual(raw, json.dumps(expected, ensure_ascii=False) + "\n")
        parsed = json.loads(raw)
        self.assertEqual(parsed, expected)
        for item in parsed:
            self.assertEqual(set(item.keys()), {"id", "title", "done"})

    def test_atomic_write_leaves_no_temp_file(self):
        store = self._store()
        for i in range(5):
            store.add(f"t{i}")
        store.complete(store.list()[0].id)
        store.delete(store.list()[-1].id)
        self.assertEqual(os.listdir(self.tmp.name), ["tasks.json"])

    # ------------------------------------------------------------ encapsulation
    def test_returned_tasks_are_copies(self):
        store = self._store()
        task = store.add("x")
        got = store.get(task.id)
        got.done = True
        got.title = "modifié"
        fresh = store.get(task.id)
        self.assertFalse(fresh.done)
        self.assertEqual(fresh.title, "x")
        tasks = store.list()
        tasks.clear()
        self.assertEqual(len(store.list()), 1)

    # ------------------------------------------------------------- thread-safe
    def test_concurrent_adds_are_thread_safe(self):
        store = self._store()
        n_threads, n_adds = 8, 25

        def worker():
            for i in range(n_adds):
                store.add(f"t-{i}")

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        tasks = store.list()
        self.assertEqual(len(tasks), n_threads * n_adds)
        self.assertEqual(len({t.id for t in tasks}), n_threads * n_adds)
        # le fichier sur disque est cohérent lui aussi
        self.assertEqual(len(TaskStore(self.path).list()), n_threads * n_adds)


if __name__ == "__main__":
    unittest.main()
