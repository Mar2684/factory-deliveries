"""Coquille web de la to-do list — bibliothèque standard UNIQUEMENT.

Aucune logique métier ici : tout passe par le noyau `todo_core.TaskStore`.

Lancement (depuis le dossier todo-app/) :
    python app.py
Variables d'environnement :
    PORT       port d'écoute (défaut : 8000)
    TODO_FILE  fichier JSON de persistance (défaut : tasks.json, répertoire courant)

Routes :
    GET  /             -> 200, page HTML (formulaire + liste des tâches)
    POST /add          -> 303 vers / (400 si titre invalide)
    POST /toggle/<id>  -> 303 vers / (404 si id inconnu)
    POST /delete/<id>  -> 303 vers / (404 si id inconnu)
"""

import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

# Bootstrap d'import robuste : fonctionne en « python todo-app/app.py »
# comme en import de package (« todo-app.app »).
import os as _os
import sys as _sys
_APP_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _APP_DIR not in _sys.path:
    _sys.path.insert(0, _APP_DIR)
from todo_core import TaskStore

DEFAULT_PORT = 8000
DEFAULT_TODO_FILE = "tasks.json"

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>To-do list</title>
</head>
<body>
  <h1>To-do list</h1>
  <form method="post" action="/add">
    <input type="text" name="title" placeholder="Nouvelle tâche" required>
    <button type="submit">Ajouter</button>
  </form>
  <ul>
{rows}
  </ul>
</body>
</html>
"""

_ERROR_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Erreur {code}</title></head>
<body><h1>Erreur {code}</h1><p>{message}</p><p><a href="/">retour</a></p></body>
</html>
"""


def render_page(store: TaskStore) -> str:
    """Construit la page HTML à partir de l'état du noyau (lecture seule)."""
    rows = []
    for task in store.list():
        safe_id = html.escape(task.id, quote=True)
        safe_title = html.escape(task.title)
        state = "faite" if task.done else "à faire"
        toggle_label = "à refaire" if task.done else "faite"
        rows.append(
            f"    <li>"
            f"<strong>{safe_title}</strong> ({state}) "
            f'<form method="post" action="/toggle/{safe_id}" style="display:inline">'
            f'<button type="submit">{toggle_label}</button></form> '
            f'<form method="post" action="/delete/{safe_id}" style="display:inline">'
            f'<button type="submit">supprimer</button></form>'
            f"</li>"
        )
    if not rows:
        rows = ["    <li>Aucune tâche pour le moment.</li>"]
    return _PAGE_TEMPLATE.format(rows="\n".join(rows))


class TodoHandler(BaseHTTPRequestHandler):
    """Handler HTTP : routage uniquement, zéro logique métier."""

    server_version = "TodoApp/1.0"

    @property
    def store(self) -> TaskStore:
        return self.server.store  # type: ignore[attr-defined]

    # ------------------------------------------------------------ helpers
    def _send_html(self, code: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect_see_other(self, location: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_error_page(self, code: int, message: str) -> None:
        self._send_html(code, _ERROR_TEMPLATE.format(
            code=code, message=html.escape(message)))

    def _read_form(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        return parse_qs(raw.decode("utf-8", errors="replace"),
                        keep_blank_values=True)

    # -------------------------------------------------------------- routes
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send_html(200, render_page(self.store))
        else:
            self._send_error_page(404, f"Ressource inconnue : {path}")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        if path == "/add":
            title = self._read_form().get("title", [""])[0]
            try:
                self.store.add(title)
            except ValueError as exc:
                self._send_error_page(400, str(exc))
                return
            self._redirect_see_other("/")
            return

        if path.startswith("/toggle/"):
            task_id = unquote(path[len("/toggle/"):])
            try:
                task = self.store.get(task_id)
                self.store.set_done(task_id, not task.done)
            except KeyError:
                self._send_error_page(404, f"Tâche inconnue : {task_id}")
                return
            self._redirect_see_other("/")
            return

        if path.startswith("/delete/"):
            task_id = unquote(path[len("/delete/"):])
            try:
                self.store.delete(task_id)
            except KeyError:
                self._send_error_page(404, f"Tâche inconnue : {task_id}")
                return
            self._redirect_see_other("/")
            return

        self._send_error_page(404, f"Ressource inconnue : {path}")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # log concis sur une ligne, utile pour le smoke test
        print("%s - %s" % (self.address_string(), format % args))


def main() -> None:
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    todo_file = os.environ.get("TODO_FILE", DEFAULT_TODO_FILE)
    store = TaskStore(todo_file)
    server = ThreadingHTTPServer(("", port), TodoHandler)
    server.store = store  # type: ignore[attr-defined]
    print(f"To-do list servie sur http://localhost:{port} "
          f"(persistance : {os.path.abspath(todo_file)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
