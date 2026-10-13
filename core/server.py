"""Servidor HTTP local (só 127.0.0.1) que serve a interface (pasta ui/) e a API JSON.

Segurança: cada execução gera um token aleatório; as rotas /api exigem esse token no cabeçalho
e o Host precisa ser o endereço local (protege contra páginas externas e DNS rebinding).
"""
import json
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.config import UI_DIR
from core.session import Session
from core.features import Features
from core.storage import StorageError


class AppServer:
    def __init__(self, session: Session):
        self.session = session
        self.features = Features(session)
        self.token = secrets.token_urlsafe(24)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?k={self.token}"

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.features.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "UsernameGenerator"

            def log_message(self, *args):       # silencia o log no console
                pass

            # ---------- helpers ----------
            def _host_ok(self) -> bool:
                return self.headers.get("Host", "") in (f"127.0.0.1:{outer.port}", f"localhost:{outer.port}")

            def _send(self, code: int, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, data, code: int = 200):
                self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")

            def _static(self, path: str):
                rel = "index.html" if path in ("", "/") else path.lstrip("/")
                full = os.path.normpath(os.path.join(UI_DIR, rel))
                if not full.startswith(os.path.normpath(UI_DIR) + os.sep) or not os.path.isfile(full):
                    return self._send(404, b"not found", "text/plain")
                ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
                    ctype += "; charset=utf-8"
                with open(full, "rb") as f:
                    self._send(200, f.read(), ctype)

            # ---------- rotas ----------
            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                url = urlparse(self.path)
                if not url.path.startswith("/api/"):
                    return self._static(url.path)
                if self.headers.get("X-App-Token") != outer.token:
                    return self._json({"ok": False, "error": "unauthorized"}, 401)
                s = outer.session
                if url.path == "/api/state":
                    with s.lock:
                        return self._json({**s.meta(), "state": s.snapshot(), "epoch": s.epoch})
                if url.path == "/api/poll":
                    q = parse_qs(url.query)
                    try:
                        after, epoch = int(q.get("after", ["0"])[0]), int(q.get("epoch", ["0"])[0])
                    except ValueError:
                        after, epoch = 0, 0
                    return self._json(s.poll(after, epoch))
                self._json({"ok": False, "error": "not found"}, 404)

            def do_POST(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                if self.headers.get("X-App-Token") != outer.token:
                    return self._json({"ok": False, "error": "unauthorized"}, 401)
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    if n < 0 or n > 2_000_000:
                        self.close_connection = True
                        return self._json({"ok": False, "error": "Tamanho da requisição inválido."}, 413)
                    body = json.loads(self.rfile.read(n) or b"{}")
                except (ValueError, OSError):
                    self.close_connection = True
                    return self._json({"ok": False, "error": "JSON inválido."}, 400)
                if not isinstance(body, dict):
                    return self._json({"ok": False, "error": "Objeto JSON esperado."}, 400)
                s, route = outer.session, urlparse(self.path).path
                try:
                    feature_reply = outer.features.dispatch(route.removeprefix("/api/"), body)
                    if feature_reply is not None:
                        return self._json(feature_reply)
                    if route == "/api/select":
                        return self._json(s.select(str(body.get("platform", ""))))
                    if route == "/api/leave":
                        return self._json(s.leave())
                    if route == "/api/start":
                        return self._json(s.start(body))
                    if route == "/api/stop":
                        s.stop()
                        return self._json({"ok": True})
                    if route == "/api/clear-log":
                        s.clear_log()
                        return self._json({"ok": True})
                    if route == "/api/open-folder":
                        return self._json(s.open_folder())
                    if route == "/api/valid":
                        return self._json(s.valid_names())
                    if route == "/api/log":
                        tag = body.get("tag") if body.get("tag") in ("info", "warn") else "info"
                        s.log_line(str(body.get("text", ""))[:300], tag)
                        return self._json({"ok": True})
                    if route == "/api/proxies":
                        s.save_proxies(str(body.get("text", "")))
                        return self._json({"ok": True})
                    if route == "/api/settings":
                        settings = s.save_settings(body)
                        return self._json({"ok": True, "settings": settings})
                except ValueError as exc:
                    return self._json({"ok": False, "error": str(exc) or "Configurações inválidas."}, 400)
                except StorageError as exc:
                    return self._json({"ok": False, "error": str(exc)}, 503)
                except OSError:
                    return self._json({"ok": False, "error": "Não foi possível salvar. Verifique a permissão da pasta."}, 500)
                except Exception as e:  # noqa
                    return self._json({"ok": False, "error": f"Erro interno: {e}"}, 500)
                self._json({"ok": False, "error": "not found"}, 404)

        return Handler
