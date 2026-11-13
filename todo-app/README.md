# todo-app — petite to-do list web en Python (stdlib uniquement)

Architecture **NOYAU + COQUILLE** :

- `todo.py` — **noyau** : logique pure (aucune dépendance web, bibliothèque standard uniquement). Testable unitairement.
- `app.py` — **coquille** : surface web la plus fine possible (`http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler`, stdlib uniquement). Elle ne fait que brancher le noyau sur HTTP.
- `tests/test_todo.py` — tests unitaires du noyau (`unittest`, module standard, aucun accès réseau).

Aucune dépendance externe : **Python 3 standard suffit, aucun `pip install`, pas de `requirements.txt`.**

## Lancer les tests

Depuis le répertoire `todo-app/` :

```bash
cd todo-app
python -m unittest discover -s tests -t . -v
```

## Lancer l'application

Depuis le répertoire `todo-app/` :

```bash
python app.py
```

Puis ouvrir http://localhost:8000 dans un navigateur.

- Page d'accueil (`GET /`) : formulaire d'ajout (champ `title`) + liste des tâches, chaque tâche ayant un bouton **faite / à refaire** et un bouton **supprimer**.
- `POST /add` (champ `title`), `POST /toggle/<id>`, `POST /delete/<id>` : délèguent au noyau puis répondent `303 See Other` vers `/` (`400` si titre invalide, `404` si id inconnu).

## Variables d'environnement

| Variable    | Défaut                          | Rôle                                  |
|-------------|---------------------------------|---------------------------------------|
| `PORT`      | `8000`                          | Port d'écoute du serveur              |
| `TODO_FILE` | `tasks.json` (répertoire courant) | Fichier JSON de persistance         |

Exemple :

```bash
PORT=9000 TODO_FILE=/tmp/mes-taches.json python app.py
```

## Format du fichier JSON

Une liste d'objets `{"id": ..., "title": ..., "done": ...}` :

```json
[
  {
    "id": "6ffbc915f87e4a0ebb0cc776f92ca407",
    "title": "Acheter du pain",
    "done": false
  }
]
```

- Fichier absent au démarrage → liste vide.
- Chaque mutation (`add`, `complete`, `delete`) persiste **immédiatement** via écriture atomique (fichier temporaire + `os.replace`) pour éviter un fichier corrompu.

## API du noyau (`todo.py`)

- `Task` (dataclass) : `id: str`, `title: str`, `done: bool`.
- `TodoStore(path)` : charge le fichier JSON au démarrage.
  - `add(title) -> Task` — id `uuid4` hex, `done=False` ; `ValueError` si titre vide ou composé d'espaces.
  - `list() -> list[Task]` — toutes les tâches, ordre d'ajout.
  - `get(task_id) -> Task` — `KeyError` si id inconnu.
  - `complete(task_id) -> Task` — marque faite ; `KeyError` si id inconnu.
  - `set_done(task_id, done) -> Task` — marque faite / à refaire ; `KeyError` si id inconnu.
  - `delete(task_id) -> None` — supprime ; `KeyError` si id inconnu.
