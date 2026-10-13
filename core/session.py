"""Sessão: guarda o estado da execução (contadores, log, status) e controla o worker.

É a lógica que antes ficava misturada com os widgets em app.py. A interface só conversa com
esta classe (via server.py), então nada aqui depende de tela.
"""
import collections
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tempfile
import time

from core.config import (APP_TITLE, APP_VERSION, LOG_MAX, MODE_INFO, PROXY_FILE, PROXY_RE,
                         SETTINGS_FILE)
from core import preferences
from core.utils import slug_words
from core.worker import run_worker
from platforms import PLATFORMS, PLATFORM_BY_NAME
from words import VERB_COUNTS

IDLE_SUBTITLE = "Configure ao lado e clique em Iniciar"
STATUS_LABELS = {"idle": "Parado", "running": "Rodando", "stopped": "Interrompido",
                 "limit": "Limite atingido", "done": "Concluído", "failed": "Falha na execução"}
_proxy_lock = threading.RLock()
BLOCKED_MSG = "Pare o processo (botão Parar) antes de trocar de app."


def parse_proxies(text: str):
    """Texto -> (lista de proxies válidos em formato URL, nº de linhas ignoradas)."""
    good, bad = [], 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if PROXY_RE.match(line):
            url = line if "://" in line else "http://" + line
            if url not in good:
                good.append(url)
        else:
            bad += 1
    return good, bad


class Session:
    def __init__(self):
        self.lock = threading.RLock()
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.platform = None
        self.features = None
        self.running = False
        self.stopping = False
        self._log = collections.deque(maxlen=LOG_MAX)
        self._log_id = 0
        self.epoch = 0                      # muda quando o log é limpo (a tela se refaz)
        self.last_poll = 0.0
        self._reset_counters()
        threading.Thread(target=self._pump, daemon=True).start()

    # ---------- estado ----------
    def _reset_counters(self):
        self.counts = {"valid": 0, "invalid": 0, "error": 0}
        self.total = 0
        self.progress = 0.0
        self.quota = ""
        self.status = "idle"
        self.subtitle = IDLE_SUBTITLE

    def meta(self) -> dict:
        return {
            "title": APP_TITLE, "version": APP_VERSION,
            "verb_counts": VERB_COUNTS,
            "modes": [{"key": k, "title": t} for k, t in MODE_INFO.items()],
            "proxy_pattern": PROXY_RE.pattern,
            "platforms": [p.meta() for p in PLATFORMS],
            "proxies": self.load_proxies(),
            "settings": self.load_settings(),
        }

    def snapshot(self) -> dict:
        c = self.counts
        return {
            "platform": self.platform.name if self.platform else None,
            "running": self.running, "stopping": self.stopping,
            "status": {"key": self.status, "label": STATUS_LABELS[self.status]},
            "counts": {**c, "done": c["valid"] + c["invalid"] + c["error"]},
            "total": self.total, "progress": self.progress,
            "quota": self.quota, "subtitle": self.subtitle,
        }

    def poll(self, after: int, epoch: int) -> dict:
        with self.lock:
            self.last_poll = time.time()
            logs = [e for e in self._log if e["id"] > after] if epoch == self.epoch else list(self._log)
            return {"epoch": self.epoch, "logs": logs, "state": self.snapshot()}

    # ---------- log ----------
    def log_line(self, text: str, tag: str = "info", **extra):
        with self.lock:
            self._log_id += 1
            self._log.append({"id": self._log_id, "t": time.strftime("%H:%M:%S"), "tag": tag,
                              "text": text, **extra})

    def clear_log(self):
        with self.lock:
            self._log.clear()
            self.epoch += 1

    # ---------- navegação ----------
    def select(self, name: str) -> dict:
        p = PLATFORM_BY_NAME.get(name)
        if p is None:
            return {"ok": False, "error": "Plataforma desconhecida."}
        with self.lock:
            if self.running and p is not self.platform:
                self.log_line(BLOCKED_MSG, "warn")
                return {"ok": False, "error": BLOCKED_MSG}
            if p is not self.platform:
                self.platform = p
                self._reset_counters()
                self.clear_log()
            return {"ok": True}

    def leave(self) -> dict:
        """Volta para o início (bloqueado enquanto roda)."""
        with self.lock:
            if self.running:
                self.log_line(BLOCKED_MSG, "warn")
                return {"ok": False, "error": BLOCKED_MSG}
            return {"ok": True}

    # ---------- arquivos ----------
    @staticmethod
    def load_proxies() -> str:
        try:
            with open(PROXY_FILE, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    @staticmethod
    def save_proxies(text: str):
        os.makedirs(os.path.dirname(PROXY_FILE), exist_ok=True)
        if len(text) > 400000: raise ValueError('A lista de proxies excede o limite de 400.000 caracteres.')
        with _proxy_lock:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(PROXY_FILE), delete=False) as f:
                    temporary = f.name
                    f.write(text.strip() + "\n")
                    f.flush(); os.fsync(f.fileno())
                os.replace(temporary, PROXY_FILE)
            finally:
                if temporary and os.path.exists(temporary): os.unlink(temporary)

    @staticmethod
    def load_settings() -> dict:
        return preferences.load(SETTINGS_FILE)

    def save_settings(self, patch: dict):
        return preferences.save(SETTINGS_FILE, patch)

    def open_folder(self) -> dict:
        if not self.platform:
            return {"ok": False}
        folder = self.platform.folder
        os.makedirs(folder, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(folder)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return {"ok": True}

    def valid_names(self) -> dict:
        """Conteúdo do arquivo de disponíveis, para a interface copiar."""
        if not self.platform:
            return {"ok": False}
        try:
            with open(self.platform.file, encoding="utf-8") as f:
                data = f.read()
        except FileNotFoundError:
            self.log_line("Nenhum username disponível salvo ainda.", "warn")
            return {"ok": False}
        return {"ok": True, "text": data, "count": len(data.split())}

    # ---------- execução ----------
    def _fail(self, msg: str, field: str = "") -> dict:
        self.log_line(msg, "warn")
        return {"ok": False, "error": msg, "field": field}

    def start(self, d: dict) -> dict:
        with self.lock:
            if self.running:
                return {"ok": False, "error": "Já está rodando."}
            if self.features and self.features.identity_running:
                return self._fail("Cancele o Identity Checker antes de iniciar outra consulta.")
            p = PLATFORM_BY_NAME.get(d.get("platform"))
            mode = d.get("mode")
            if p is None or p is not self.platform or mode not in p.modes:
                return {"ok": False, "error": "Configuração inválida."}

            cfg = {"mode": mode, "length": 0, "base_name": "", "names": None,
                   "two_words": bool(d.get("two_words")),
                   "digits": bool(d.get("name_digits") if mode == "name" else d.get("digits")),
                   "use_sep": bool(d.get("use_sep")), "suffixes": bool(d.get("suffixes"))}
            proxy_text = str(d.get("proxies", ""))

            settings = self.load_settings()
            use_proxies = d.get("use_proxies", settings["use_proxies"])
            if type(use_proxies) is not bool:
                return self._fail("Opção de proxies inválida.", "proxies")
            proxies = []
            if use_proxies and (p.needs_proxy or p.proxy_optional):
                proxies, _ = parse_proxies(proxy_text)
                if not proxies:
                    return self._fail("Cole seus proxies antes de iniciar.", "proxies")

            if mode == "check":
                names = []
                for n in re.split(r"[,;\s]+", str(d.get("list", "")).strip()):
                    n = p.normalize(n)
                    if n and n not in names:
                        names.append(n)
                if not names:
                    return self._fail("Digite pelo menos um username para verificar.", "list")
                cfg["names"], total = names, len(names)
            else:
                try:
                    total = int(str(d.get("amount", "")).strip())
                    if total < 1:
                        raise ValueError
                except ValueError:
                    return self._fail("Digite uma quantidade válida de usernames.", "amount")
                if mode == "random":
                    try:
                        cfg["length"] = int(str(d.get("length", "")).strip())
                        if not p.min_len <= cfg["length"] <= p.max_len:
                            raise ValueError
                    except ValueError:
                        return self._fail(f"A quantidade de letras deve ser entre {p.min_len} e {p.max_len}.",
                                          "length")
                if mode == "name":
                    cfg["base_name"] = str(d.get("base_name", "")).strip()
                    if not slug_words(cfg["base_name"]):
                        return self._fail("Digite um nome para gerar as sugestões.", "base_name")

            if use_proxies and (p.needs_proxy or p.proxy_optional):
                self.save_proxies(proxy_text)
            token = str(d.get("token", "")).strip() if p.has_token else ""
            if p.token_required and not p.token_ok(token):
                return self._fail(p.token_error, "token")

            label = MODE_INFO[mode]
            cfg["username_interval"] = settings["username_interval"]
            cfg["batch_enabled"] = settings["batch_enabled"]
            cfg["name_language"] = d.get("name_language", "en")
            if cfg["name_language"] not in ("en", "pt", "es"):
                return self._fail("Idioma de sugestões inválido.", "base_name")
            self._reset_counters()
            self.total = total
            p.remaining = None
            self.running, self.stopping = True, False
            self.status = "running"
            self.subtitle = f"{label}  ·  {total} usernames"
            self.stop_event.clear()
            extra = f" · {len(proxies)} proxies" if proxies else ""
            self.log_line(f"Iniciando ({p.name} · {label}): {total} usernames{extra}", "info")
            pause = p.direct_pause(token)
            if p.proxy_optional and not proxies and (pause or 0) >= 1:
                self.log_line(f"Sem proxies: verificando direto pelo seu IP (1 a cada ~{pause:g}s). "
                              "Pode ser bloqueado com poucas consultas.", "warn")
            if cfg["batch_enabled"] and p.batch_limit(token) > 1:
                self.log_line(f"Modo rápido: {p.batch_limit(token)} usernames por requisição.", "info")

            if self.features:
                cfg["_observer"] = self.features.legacy_observer(p, mode)
            threading.Thread(target=run_worker, daemon=True,
                             args=(p, total, cfg, self.events, self.stop_event, token, proxies)).start()
            return {"ok": True}

    def stop(self):
        with self.lock:
            if not self.running or self.stopping:
                return
            self.stopping = True
            self.stop_event.set()
            self.log_line("Parando...", "warn")

    # ---------- eventos do worker ----------
    def _pump(self):
        while True:
            try:
                kind, i, data = self.events.get(timeout=0.2)
            except queue.Empty:
                continue
            with self.lock:
                self._handle(kind, i, data)

    def _handle(self, kind, i, data):
        t, c = self.total, self.counts
        if kind == "valid":
            c["valid"] += 1
            self.log_line("Não encontrado" if self.platform and self.platform.lookup_only else "Disponível", "valid", name=data, i=i, n=t)
        elif kind == "invalid":
            c["invalid"] += 1
            self.log_line("Indisponível", "invalid", name=data, i=i, n=t)
        elif kind == "badformat":
            c["invalid"] += 1
            self.log_line("Formato inválido", "invalid", name=data, i=i, n=t)
        elif kind == "error":
            c["error"] += 1
            self.log_line(f"[{i}/{t}]  {data}", "warn")
        elif kind == "info":
            self.log_line(data, "info")
        elif kind == "fatal":
            self.log_line(f"Parado: {data}", "warn")
        elif kind == "quota":
            self.quota = data
        elif kind == "done":
            self.running = self.stopping = False
            self.status = data if data in ("stopped", "limit", "failed") else "done"
            label = "Não encontrados" if self.platform and self.platform.lookup_only else "Disponíveis"
            self.log_line(f"{STATUS_LABELS[self.status]} · {label}: {c['valid']}", "info")
        if kind in ("valid", "invalid", "badformat", "error") and t:
            self.progress = min(sum(c.values()) / t, 1.0)
