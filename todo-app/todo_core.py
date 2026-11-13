"""Noyau pur de la to-do list : logique métier uniquement.

Bibliothèque standard UNIQUEMENT, aucun import web (pas de http.server,
flask, etc.) : ce module ne fait aucun accès réseau et peut être testé
unitairement tel quel, puis branché derrière n'importe quelle coquille
(HTTP, CLI, ...).

Format du fichier JSON de persistance :
    [{"id": "<uuid4 hex>", "title": "...", "done": false}, ...]
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from typing import List, Union

PathLike = Union[str, "os.PathLike[str]"]


def _new_id() -> str:
    """Identifiant de tâche : uuid4 en hexadécimal (32 caractères)."""
    return uuid.uuid4().hex


@dataclass
class Task:
    """Une tâche : id unique (uuid4 hex), titre, état fait / à faire."""

    id: str = field(default_factory=_new_id)
    title: str = ""
    done: bool = False

    def to_dict(self) -> dict:
        """Sérialise la tâche en dict JSON (clés id, title, done)."""
        return {"id": self.id, "title": self.title, "done": self.done}

    @classmethod
    def from_dict(cls, data: object) -> "Task":
        """Construit une tâche depuis un dict ; ValueError si invalide."""
        if not isinstance(data, dict):
            raise ValueError(f"tâche invalide (objet JSON attendu) : {data!r}")
        try:
            task_id = data["id"]
            title = data["title"]
            done = data["done"]
        except KeyError as exc:
            raise ValueError(
                f"tâche invalide (champ {exc} manquant) : {data!r}"
            ) from exc
        if (
            not isinstance(task_id, str)
            or not isinstance(title, str)
            or not isinstance(done, bool)
        ):
            raise ValueError(f"tâche invalide (types incorrects) : {data!r}")
        return cls(id=task_id, title=title, done=done)


class TaskStore:
    """Stock de tâches persisté dans un fichier JSON.

    - fichier absent au démarrage -> liste vide ;
    - contenu JSON invalide (pas une liste de tâches) -> ValueError explicite ;
    - chaque mutation persiste IMMÉDIATEMENT (écriture atomique :
      fichier temporaire + os.replace) ;
    - thread-safe (lock interne) pour être servi par un ThreadingHTTPServer.
    """

    def __init__(self, path: PathLike) -> None:
        self._path = os.fspath(path)
        self._lock = threading.RLock()
        self._tasks: List[Task] = []
        self._load()

    # ------------------------------------------------------------------
    # persistance
    # ------------------------------------------------------------------
    @property
    def path(self) -> str:
        return self._path

    def _load(self) -> None:
        with self._lock:
            if not os.path.exists(self._path):
                self._tasks = []
                return
            with open(self._path, "r", encoding="utf-8") as fh:
                content = fh.read()
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{self._path!r} : contenu JSON invalide ({exc})"
                ) from exc
            if not isinstance(data, list):
                raise ValueError(
                    f"{self._path!r} : contenu invalide, une liste de tâches "
                    f"est attendue (reçu {type(data).__name__})"
                )
            self._tasks = [Task.from_dict(item) for item in data]

    def _save(self) -> None:
        """Écriture atomique : fichier temporaire + os.replace.

        Doit être appelé sous self._lock.
        """
        payload = (
            json.dumps(
                [task.to_dict() for task in self._tasks], ensure_ascii=False
            )
            + "\n"
        )
        directory = os.path.dirname(os.path.abspath(self._path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(self._path) + ".",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # helpers internes
    # ------------------------------------------------------------------
    @staticmethod
    def _copy(task: Task) -> Task:
        return Task(id=task.id, title=task.title, done=task.done)

    def _find(self, task_id: str) -> Task:
        """Renvoie la tâche interne d'id task_id ; KeyError si inconnue."""
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"tâche inconnue : {task_id!r}")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def add(self, title: str) -> Task:
        """Ajoute une tâche et la persiste ; ValueError si titre vide."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("le titre de la tâche ne peut pas être vide")
        with self._lock:
            task_id = _new_id()
            while any(task.id == task_id for task in self._tasks):
                task_id = _new_id()
            task = Task(id=task_id, title=title, done=False)
            self._tasks.append(task)
            self._save()
            return self._copy(task)

    def list(self) -> List[Task]:
        """Toutes les tâches, dans l'ordre d'ajout (copies)."""
        with self._lock:
            return [self._copy(task) for task in self._tasks]

    def get(self, task_id: str) -> Task:
        """Une tâche par id ; KeyError si id inconnu."""
        with self._lock:
            return self._copy(self._find(task_id))

    def complete(self, task_id: str) -> Task:
        """Marque la tâche comme faite ; KeyError si id inconnu."""
        return self.set_done(task_id, True)

    def set_done(self, task_id: str, done: bool) -> Task:
        """Fixe l'état fait/à faire ; KeyError si id inconnu."""
        if not isinstance(done, bool):
            raise ValueError("done doit être un booléen")
        with self._lock:
            task = self._find(task_id)
            task.done = done
            self._save()
            return self._copy(task)

    def delete(self, task_id: str) -> Task:
        """Supprime la tâche ; KeyError si id inconnu."""
        with self._lock:
            task = self._find(task_id)
            self._tasks.remove(task)
            self._save()
            return self._copy(task)

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)
