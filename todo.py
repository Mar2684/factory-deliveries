"""Noyau logique de la to-do list.

Logique pure, testable unitairement, AUCUNE dépendance web :
bibliothèque standard uniquement (json, uuid, dataclasses, pathlib, ...).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

PathLike = Union[str, os.PathLike]


@dataclass
class Task:
    """Une tâche : identifiant unique, titre, état fait / à faire."""

    id: str
    title: str
    done: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "done": self.done}

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            done=bool(data["done"]),
        )


class TodoStore:
    """Stock de tâches persisté dans un fichier JSON.

    Format du fichier : une liste d'objets ``{"id": str, "title": str, "done": bool}``.
    Fichier absent au démarrage -> liste vide.
    Chaque mutation persiste immédiatement (écriture atomique via fichier
    temporaire + ``os.replace`` pour éviter un fichier corrompu).
    """

    def __init__(self, path: PathLike) -> None:
        self._path = Path(path)
        # RLock : les méthodes publiques peuvent s'appeler entre elles
        # (ex. complete -> set_done) sans deadlock.
        self._lock = threading.RLock()
        self._tasks: List[Task] = []
        self._load()

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._tasks = []
            return
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            self._tasks = []
            return
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(
                f"Fichier {self._path} invalide : une liste de tâches est attendue"
            )
        self._tasks = [Task.from_dict(item) for item in data]

    def _save(self) -> None:
        """Écriture atomique : fichier temporaire dans le même répertoire + os.replace."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent),
            prefix=self._path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(
                    [task.to_dict() for task in self._tasks],
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
                fh.write("\n")
            os.replace(tmp_name, self._path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Internes (verrou supposé acquis par l'appelant)
    # ------------------------------------------------------------------

    def _find_locked(self, task_id: str) -> Task:
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Tâche inconnue : {task_id!r}")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def add(self, title: str) -> Task:
        """Ajoute une tâche (done=False, id uuid4 hex). Lève ValueError si titre vide."""
        if title is None:
            raise ValueError("Le titre de la tâche ne peut pas être vide")
        title = str(title)
        if not title.strip():
            raise ValueError("Le titre de la tâche ne peut pas être vide")
        with self._lock:
            task = Task(id=uuid.uuid4().hex, title=title, done=False)
            self._tasks.append(task)
            self._save()
            return task

    def list(self) -> List[Task]:
        """Toutes les tâches, dans l'ordre d'ajout."""
        with self._lock:
            return list(self._tasks)

    def get(self, task_id: str) -> Task:
        """Retourne la tâche d'identifiant donné. Lève KeyError si inconnu."""
        with self._lock:
            return self._find_locked(task_id)

    def complete(self, task_id: str) -> Task:
        """Marque la tâche comme faite. Lève KeyError si id inconnu."""
        return self.set_done(task_id, True)

    def set_done(self, task_id: str, done: bool) -> Task:
        """Marque la tâche comme faite (done=True) ou à refaire (done=False)."""
        with self._lock:
            task = self._find_locked(task_id)
            task.done = bool(done)
            self._save()
            return task

    def delete(self, task_id: str) -> None:
        """Supprime la tâche. Lève KeyError si id inconnu."""
        with self._lock:
            for index, task in enumerate(self._tasks):
                if task.id == task_id:
                    del self._tasks[index]
                    self._save()
                    return
        raise KeyError(f"Tâche inconnue : {task_id!r}")
