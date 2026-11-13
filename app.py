"""Coquille web de la to-do list — la plus fine possible.

Bibliothèque standard UNIQUEMENT (http.server) : aucune dépendance pip.
Toute la logique métier vit dans le noyau (todo.py) ; ce fichier ne fait
que la brancher sur HTTP.

Lancement : ``python app.py`` depuis le répertoire ``todo-app/``.
Variables d'environnement :
  - ``PORT``      : port d'écoute (défaut 8000)
  - ``TODO_FILE`` : fichier JSON de persistance (défaut "tasks.json" dans le
    répertoire courant)
"""

from __future__ import annotations

import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from todo import TodoStore

PORT = int(os.environ.get("PORT", "8000"))
TODO_FILE = os.environ.get("TODO_FILE", "tasks.json")

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>To-do list</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ font-size: 1.6rem; }}
  form.add {{ display: flex; gap: .5rem; margin-bottom: 1.5rem; }}
  form.add input[type=text] {{ flex: 1; padding: .5rem .75rem; border: 1px solid #bbb; border-radius: 6px; font-size: 1rem; }}
  button {{ padding: .4rem .8rem; border: 1px solid #999; border-radius: 6px; background: #f5f5f5; cursor: pointer; font-size: .9rem; }}
  button:hover {{ background: #e9e9e9; }}
  button.danger {{ border-color: #c66; color: #a00; background: #fff5f5; }}
  button.danger:hover {{ background: #ffe5e5; }}
  ul.tasks {{ list-style: none; padding: 0; }}
  li.task {{ display: flex; align-items: center; gap: .5rem; padding: .5rem 0; border-bottom: 1px solid #eee; }}
  li.task .title {{ flex: 1; }}
  li.task .title.done {{ text-decoration: line-through; color: #888; }}
  form.inline {{ display: inline; margin: 0; }}
  p.empty {{ color: #888; font-style: italic; }}
</style>
</head>
<body>
<h1>To-do list</h1>
<form class="add" method="post" action="/add">
  <input type="text" name="title" placeholder="Nouvelle tâche..." required autofocus>
  <button type="submit">Ajouter</button>
</form>
{body}
</body>
</html>
"""


def render_page(store: TodoStore) -> str:
    """Construit la page HTML complète (formulaire + liste des tâches)."""
    tasks = store.list()
    if not tasks:
        body = '<p class="empty">Aucune tâche pour le moment.</p>'
    else:
        items = []
        for task in tasks:
            title = html.escape(task.title)
            if task.done:
                title = f'<span class="title done">{title}</span>'
                toggle_label = "à refaire"
            else:
                title = f'<span class="title">{title}</span>'
                toggle_label = "faite"
            items.append(
                f'<li class="task">{title}'
                f'<form class="inline" method="post" action="/toggle/{task.id}">'
                f'<button type="submit">{toggle_label}</button></form>'
                f'<form class="inline" method="post" action="/delete/{task.id}">'
                f'<button type="submit" class="danger">supprimer</button></form>'
                f"</li>"
            )
        body = '<ul class="tasks">' + "\n".join(items) + "</ul>"
    return PAGE_TEMPLATE.format(body=body)


class TodoHandler(BaseHTTPRequestHandler):
    server_version = "TodoApp/1.0"
    protocol_version = "HTTP/1.1"

    @property
    def store(self) -> TodoStore:
        return self.server.store  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Helpers de réponse
    # ------------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: int = 200) -> None:
        self._send(status, body.encode("utf-8"), "text/html; charset=utf-8")

    def _send_text(self, status: int, message: str) -> None:
        self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def _redirect_home(self) -> None:
        """303 See Other vers / après une mutation réussie."""
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(render_page(self.store), 200)
        else:
            self._send_text(404, "404 Not Found")

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/add":
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8")
                fields = parse_qs(body, keep_blank_values=True)
                title = fields.get("title", [""])[0]
                self.store.add(title)  # ValueError si titre vide -> 400
            elif path.startswith("/toggle/"):
                task_id = path[len("/toggle/"):]
                task = self.store.get(task_id)  # KeyError si inconnu -> 404
                self.store.set_done(task_id, not task.done)
            elif path.startswith("/delete/"):
                task_id = path[len("/delete/"):]
                self.store.delete(task_id)  # KeyError si inconnu -> 404
            else:
                self._send_text(404, "404 Not Found")
                return
        except ValueError as exc:
            self._send_text(400, f"400 Bad Request : {exc}")
            return
        except KeyError as exc:
            self._send_text(404, f"404 Not Found : {exc}")
            return
        self._redirect_home()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # logs concis sur une seule ligne
        super().log_message(format, *args)


def main() -> None:
    store = TodoStore(TODO_FILE)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TodoHandler)
    server.store = store  # type: ignore[attr-defined]
    print(f"To-do app : http://localhost:{PORT}  (fichier JSON : {TODO_FILE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
