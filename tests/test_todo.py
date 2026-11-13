"""Tests unitaires du noyau (todo.py) — unittest, module standard, aucun accès réseau."""

import json
import os
import tempfile
import unittest

from todo import Task, TodoStore


class TodoStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "tasks.json")
        self.store = TodoStore(self.path)

    # ------------------------------------------------------------------
    # Fichier absent -> liste vide
    # ------------------------------------------------------------------

    def test_missing_file_gives_empty_list(self) -> None:
        absent = os.path.join(self._tmp.name, "absent.json")
        self.assertEqual(TodoStore(absent).list(), [])
        # le store du setUp pointe aussi vers un fichier inexistant au départ
        self.assertEqual(self.store.list(), [])

    # ------------------------------------------------------------------
    # add + list
    # ------------------------------------------------------------------

    def test_add_and_list_keep_insertion_order(self) -> None:
        t1 = self.store.add("Acheter du pain")
        t2 = self.store.add("Lire un livre")
        tasks = self.store.list()
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(isinstance(t, Task) for t in tasks))
        self.assertEqual([t.id for t in tasks], [t1.id, t2.id])
        self.assertEqual([t.title for t in tasks], ["Acheter du pain", "Lire un livre"])
        self.assertFalse(tasks[0].done)
        self.assertFalse(tasks[1].done)

    def test_add_generates_unique_ids(self) -> None:
        ids = {self.store.add(f"tâche {i}").id for i in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(len(i) == 32 for i in ids))  # uuid4 hex

    def test_add_empty_or_blank_title_raises_valueerror(self) -> None:
        for bad in ("", "   ", "\t\n  "):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.store.add(bad)
        self.assertEqual(self.store.list(), [])  # rien n'a été persisté

    # ------------------------------------------------------------------
    # complete
    # ------------------------------------------------------------------

    def test_complete_marks_task_done(self) -> None:
        task = self.store.add("Trier les papiers")
        done = self.store.complete(task.id)
        self.assertIsInstance(done, Task)
        self.assertTrue(done.done)
        self.assertEqual(done.id, task.id)
        self.assertTrue(self.store.list()[0].done)

    def test_complete_unknown_id_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            self.store.complete("id-inconnu")

    def test_set_done_can_uncomplete(self) -> None:
        task = self.store.add("Faire du sport")
        self.store.complete(task.id)
        back = self.store.set_done(task.id, False)
        self.assertFalse(back.done)
        self.assertFalse(self.store.list()[0].done)

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def test_delete_removes_task(self) -> None:
        t1 = self.store.add("tâche 1")
        t2 = self.store.add("tâche 2")
        self.store.delete(t1.id)
        self.assertEqual([t.title for t in self.store.list()], ["tâche 2"])
        self.store.delete(t2.id)
        self.assertEqual(self.store.list(), [])

    def test_delete_unknown_id_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            self.store.delete("id-inconnu")

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def test_persistence_across_instances(self) -> None:
        t1 = self.store.add("persistante")
        self.store.complete(t1.id)
        self.store.add("deuxième")
        # Recharge via une NOUVELLE instance sur le même fichier
        reloaded = TodoStore(self.path)
        tasks = reloaded.list()
        self.assertEqual([t.title for t in tasks], ["persistante", "deuxième"])
        self.assertEqual(tasks[0].id, t1.id)
        self.assertTrue(tasks[0].done)
        self.assertFalse(tasks[1].done)

    def test_delete_is_persisted(self) -> None:
        task = self.store.add("supprime-moi")
        self.store.delete(task.id)
        self.assertEqual(TodoStore(self.path).list(), [])

    def test_json_file_format(self) -> None:
        task = self.store.add("Vérifier le format")
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(
            data,
            [{"id": task.id, "title": "Vérifier le format", "done": False}],
        )

    def test_no_leftover_temp_files_after_mutations(self) -> None:
        self.store.add("x")
        self.store.complete(self.store.list()[0].id)
        leftovers = [f for f in os.listdir(self._tmp.name) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
