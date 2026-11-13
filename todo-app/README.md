# todo-app — to-do list web en Python (stdlib uniquement)

Architecture **noyau + coquille**, 100 % autonome dans ce dossier :
- `todo_core.py` — noyau pur (logique métier, aucun import web, thread-safe,
  persistance JSON atomique par fichier temporaire + `os.replace`) ;
- `app.py` — coquille web `http.server` (ThreadingHTTPServer), zéro logique métier ;
- `tests/` — tests unitaires du noyau (unittest, stdlib uniquement).

## Lancement

```bash
cd todo-app
python app.py            # http://localhost:8000
```

Variables d'environnement : `PORT` (défaut `8000`), `TODO_FILE`
(défaut `tasks.json` dans le répertoire courant), ex. :
`PORT=8123 TODO_FILE=/tmp/tasks.json python app.py`

Routes : `GET /` (page HTML), `POST /add` (champ `title`), `POST /toggle/<id>`,
`POST /delete/<id>` → 303 vers `/` (400 titre vide, 404 id inconnu).

## Tests

```bash
cd todo-app && python -m unittest discover -s tests -t . -v
```

## Format du fichier JSON

```json
[{"id": "<uuid4 hex>", "title": "Acheter du pain", "done": false}]
```

Fichier absent → liste vide ; contenu invalide (pas une liste) → `ValueError`.
