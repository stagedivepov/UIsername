"""
UIsername - gerador e verificador de usernames.

Estrutura do projeto:
  app.py                 -> ponto de entrada (abre a janela)
  core/                  -> configuração, geração de nomes, worker (rede/proxies), sessão e servidor local
  platforms/<nome>.py    -> UMA plataforma por arquivo (regras de formato + verificação na API)
  ui/                    -> interface (HTML, CSS e JS)
  words.py               -> listas de verbos (modos "Verbos em inglês/português")

A interface roda numa janela nativa (pywebview). Se o pywebview não estiver instalado,
o app abre no navegador padrão e encerra sozinho quando a aba é fechada.
"""
import os
import sys
import threading
import time
import webbrowser

from core.config import APP_TITLE, UI_DIR, DATA_DIR, CRASH_FILE
from core.server import AppServer
from core.session import Session


def run_in_browser(server: AppServer, session: Session):
    """Plano B sem pywebview: abre o navegador e encerra quando ele para de consultar o servidor."""
    print(server.url, flush=True)
    webbrowser.open(server.url)
    started = time.time()
    while True:
        time.sleep(1.0)
        idle = time.time() - session.last_poll
        if session.last_poll == 0 and time.time() - started < 60:
            continue                                # ainda esperando a primeira conexão
        if idle > 120 and not session.running:
            break


class WindowControls:
    """Only local window actions are exposed to the webview."""
    def __init__(self, fullscreen=False):
        self._window = None
        self._maximized = False
        self._fullscreen = bool(fullscreen)

    def state(self):
        return {"fullscreen": self._fullscreen, "maximized": self._maximized}

    def minimize(self):
        self._window.minimize()

    def maximize(self):
        self._maximized = not self._maximized
        if self._maximized:
            self._window.maximize()
        else:
            self._window.restore()
        return self.state()

    def resize(self, width, height):
        if type(width) is not int or type(height) is not int:
            return False
        if self._fullscreen or self._maximized:
            return False
        self._window.resize(min(max(width, 900), 10000), min(max(height, 620), 10000))
        return True

    def fullscreen(self):
        self._window.toggle_fullscreen()
        self._fullscreen = not self._fullscreen
        return self.state()

    def close(self):
        self._window.destroy()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    session = Session()
    server = AppServer(session)
    server.start()

    if os.environ.get("USERNAMEGEN_NO_WINDOW"):    # modo de teste: só o servidor
        print(server.url, flush=True)
        threading.Event().wait()
        return

    try:
        import webview
    except ImportError:
        try:
            run_in_browser(server, session)
        finally:
            session.stop()
            server.stop()
        return

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    start_fullscreen = session.load_settings()["startup_mode"] == "fullscreen"
    controls = WindowControls(fullscreen=start_fullscreen)
    window = webview.create_window(APP_TITLE, server.url, width=1180, height=800,
                                   min_size=(900, 620), background_color="#101217",
                                   frameless=True, easy_drag=False, shadow=True, fullscreen=start_fullscreen, js_api=controls)
    controls._window = window
    window.events.closing += lambda: session.stop_event.set()
    opened = threading.Event()
    window.events.loaded += opened.set
    try:
        try:
            webview.start(icon=os.path.join(UI_DIR, "app.ico"))
        except Exception:
            if opened.is_set():
                raise
            run_in_browser(server, session)
    finally:
        session.stop()
        server.stop()


def _report_crash():
    import traceback
    err = traceback.format_exc()
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CRASH_FILE, "w", encoding="utf-8") as f:
            f.write(err)
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(APP_TITLE, "O app encontrou um erro e vai fechar.\n\n" + err[-1200:])
        r.destroy()
    except Exception:  # noqa
        print(err)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa
        _report_crash()
        sys.exit(1)
