"""Worker: verifica os usernames numa thread e envia eventos para a fila (inclui rodízio de proxies)."""
from functools import wraps
from copy import copy
import math
import queue
import threading
import time

import requests

from core.generator import generate_username
from core.platform_base import Platform
from core.utils import rng


class ObservedSession(requests.Session):
    last_response = None
    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        self.last_response = response
        return response


def observe(cfg, method, *args, **kwargs):
    observer = cfg.get("_observer")
    if observer:
        try: getattr(observer, method)(*args, **kwargs)
        except Exception: pass  # metrics must never interrupt an existing verification


def managed_worker(fn):
    @wraps(fn)
    def wrapped(p, total, cfg, events, stop, token="", *args):
        if cfg.get("username_interval", 0) > p.delay:
            p = copy(p)
            p.delay = cfg["username_interval"]  # also applies to a batch's individual fallback
        if cfg.get("_observer") and not getattr(p, "_metrics_wrapped", False):
            p = copy(p)
            original_check = p.check
            def tracked_check(network, name, token="", proxy=None):
                outcome = original_check(network, name, token, proxy)
                observe(cfg, "capture", name, outcome[0], getattr(network, "last_response", None))
                return outcome
            p.check = tracked_check
            p._metrics_wrapped = True
        with (ObservedSession() if cfg.get("_observer") else requests.Session()) as session:
            session.trust_env = False  # explicit proxy settings only; no implicit environment/netrc credentials
            try:
                return fn(p, total, cfg, events, stop, token, *args, session=session)
            except Exception as exc:
                events.put(("fatal", 0, f"Falha na execução: {type(exc).__name__}"))
                observe(cfg, "finish", "failed")
                events.put(("done", 0, "failed"))
    return wrapped


class ProxyPool:
    """Rodízio de proxies: pula os descartados e os que estão esperando (limite 429)."""

    def __init__(self, proxies):
        self.all = list(proxies)
        rng.shuffle(self.all)
        self.bad = set()
        self.cool = {}          # proxy -> instante em que volta a ser usado
        self._i = 0

    def alive_count(self):
        return len(self.all) - len(self.bad)

    def next(self):
        now, n = time.time(), len(self.all)
        for _ in range(n):
            px = self.all[self._i % n]
            self._i += 1
            if px not in self.bad and self.cool.get(px, 0) <= now:
                return px
        return None

    def wait_time(self):
        """Segundos até algum proxy voltar; None se todos foram descartados."""
        waits = [self.cool.get(px, 0) - time.time() for px in self.all if px not in self.bad]
        return max(min(waits), 0.0) if waits else None

    def mark_bad(self, px):
        self.bad.add(px)

    def cooldown(self, px, seconds):
        self.cool[px] = time.time() + seconds


def check_with_pool(p, session, name, token, pool, stop, events, i):
    """Verifica um nome trocando de proxy quando um falha ou toma limite."""
    last_msg = 0.0
    while not stop.is_set():
        px = pool.next()
        if px is None:
            wait = pool.wait_time()
            if wait is None:
                return "ratelimit", "Todos os proxies falharam. Adicione proxies novos e tente de novo."
            if time.time() - last_msg > 15:
                events.put(("info", i, f"Proxies em espera (limite do site). Retomando em ~{int(wait) + 1}s..."))
                last_msg = time.time()
            stop.wait(min(max(wait, 0.2), 1.0))
            continue
        try:
            status, detail = p.check(session, name, token, px)
        except requests.exceptions.RequestException:
            pool.mark_bad(px)
            continue
        if status == "retry":
            pool.cooldown(px, float(detail or 30))
            continue
        if status == "badproxy":
            pool.mark_bad(px)
            continue
        return status, detail
    return "stopped", ""


def retry_delay(detail, attempt):
    try:
        seconds = float(detail or 5)
        if not math.isfinite(seconds) or seconds < 0: seconds = 5
    except (ValueError, TypeError): seconds = 5
    return max(seconds, min(max(seconds, 1) * attempt, 3600))


def _direct_check(p, session, name, token):
    """Consulta sem proxy: erro de servidor/proxy (502, 503...) vira nova tentativa, nunca 'indisponível'."""
    status, detail = p.check(session, name, token)
    if status == "badproxy":
        return "retry", "5"
    return status, detail


@managed_worker
def run_worker_batch(p: Platform, total: int, cfg: dict, events: queue.Queue,
                     stop: threading.Event, token: str = "", *, session=None):
    """Modo rápido: junta até N nomes e verifica todos numa única requisição."""
    size = p.batch_limit(token)
    seen = set()
    names = cfg.get("names")
    reason, i = "finished", 0
    while i < total and reason == "finished":
        if stop.is_set():
            reason = "stopped"
            break
        chunk = []                                  # [(índice, nome)]
        while i < total and len(chunk) < size:
            i += 1
            if names:
                name = p.normalize(names[i - 1])
            else:
                name = generate_username(p, cfg)
                for _ in range(10):                 # evita repetir nomes na mesma sessão
                    if name not in seen:
                        break
                    name = generate_username(p, cfg)
                seen.add(name)
                observe(cfg, "generated", i)
            if not p.local_ok(name):
                events.put(("badformat", i, p.format_username(name)))
                continue
            chunk.append((i, name))
        if not chunk:
            continue
        last = chunk[-1][0]
        done, tries = set(), 0
        check_started = time.monotonic()
        try:
            while not stop.is_set():
                pending = list(dict.fromkeys(n for k, n in chunk if k not in done))
                if not pending:
                    break
                results, sig = p.check_batch(session, pending, token, stop)
                for k, n in chunk:
                    st = results.get(n)
                    if k in done or st is None:
                        continue
                    observe(cfg, "result", k, st, n, (time.monotonic() - check_started) / max(1, len(chunk)))
                    if st == "available":
                        p.save(n)
                        events.put(("valid", k, p.format_username(n)))
                    elif st == "taken":
                        events.put(("invalid", k, p.format_username(n)))
                    else:
                        events.put(("error", k, "Resposta de disponibilidade desconhecida."))
                    done.add(k)
                if p.remaining:
                    events.put(("quota", last, f"Cota da API: {p.remaining}"))
                if sig is None:
                    for k, n in chunk:
                        if k not in done and not stop.is_set():
                            observe(cfg, "result", k, "unknown", n, (time.monotonic()-check_started)/max(1,len(chunk)))
                            events.put(("error", k, f"{n}: resposta incompleta da plataforma."))
                            done.add(k)
                    break
                if sig[0] == "ratelimit":
                    for k, n in chunk:
                        if k not in done: observe(cfg, "result", k, "ratelimit", n)
                    events.put(("fatal", last, sig[1]))
                    reason = "limit"
                    break
                tries += 1
                if tries > 5:
                    events.put(("fatal", last, "O site continua limitando as requisições. "
                                               "Aguarde alguns minutos e tente de novo."))
                    reason = "limit"
                    break
                wait = retry_delay(sig[1], tries)
                events.put(("info", last, f"Limite do site. Nova tentativa em {int(wait)}s ({tries}/5)..."))
                if stop.wait(wait):
                    break
        except requests.exceptions.RequestException as e:
            for k, n in chunk:
                if k not in done:
                    observe(cfg, "result", k, "error", n)
                    events.put(("error", k, f"Erro de conexão ({type(e).__name__}). Confira a rede e as credenciais."))
        except Exception as e:  # noqa
            for k, n in chunk:
                if k not in done:
                    observe(cfg, "result", k, "error", n)
                    events.put(("error", k, f"Falha ao processar resposta ou salvar resultado ({type(e).__name__})."))
        if stop.is_set():
            reason = "stopped"
            break
        if reason == "finished":
            stop.wait(max(p.delay, cfg.get("username_interval", 0) * len(chunk)))
    observe(cfg, "finish", "completed" if reason == "finished" else reason)
    events.put(("done", 0, reason))


@managed_worker
def run_worker(p: Platform, total: int, cfg: dict, events: queue.Queue,
               stop: threading.Event, token: str = "", proxies=None, *, session=None):
    """Roda em outra thread e envia tuplas (tipo, índice, dado) para a fila."""
    pool = ProxyPool(proxies) if ((p.needs_proxy or p.proxy_optional) and proxies) else None
    seen = set()
    names = cfg.get("names")            # modo "Verificar usernames"
    reason = "finished"
    if cfg.get("batch_enabled", True) and p.batch_limit(token) > 1:
        run_worker_batch(p, total, cfg, events, stop, token)
        return
    slow = 0.0                          # freio automático: aumenta a pausa quando o site reclama
    for i in range(1, total + 1):
        if stop.is_set():
            reason = "stopped"
            break
        if names:
            name = p.normalize(names[i - 1])
        else:
            name = generate_username(p, cfg)
            for _ in range(10):         # evita repetir nomes na mesma sessão
                if name not in seen:
                    break
                name = generate_username(p, cfg)
            seen.add(name)
            observe(cfg, "generated", i)
        if not p.local_ok(name):
            events.put(("badformat", i, p.format_username(name)))
            continue
        check_started = time.monotonic()
        try:
            if pool:
                status, detail = check_with_pool(p, session, name, token, pool, stop, events, i)
                events.put(("quota", i, f"Proxies ativos: {pool.alive_count()}/{len(pool.all)}"))
            else:
                status, detail = _direct_check(p, session, name, token)
                first_retry = status == "retry"
                tries = 0
                while status == "retry" and tries < 5 and not stop.is_set():
                    tries += 1
                    wait = retry_delay(detail, tries)
                    events.put(("info", i, f"Limite do site. Nova tentativa em {int(wait)}s ({tries}/5)..."))
                    if stop.wait(wait):
                        break
                    status, detail = _direct_check(p, session, name, token)
                if status == "retry":
                    if stop.is_set():
                        status = "stopped"
                    else:
                        status, detail = "ratelimit", ("O site continua limitando as requisições. "
                                                       "Aguarde alguns minutos e tente de novo.")
                slow = (min(max(slow * 1.5, 1.0), 8.0) if first_retry
                        else (slow * 0.9 if slow > 0.05 else 0.0))
                if p.remaining:
                    events.put(("quota", i, f"Cota da API: {p.remaining}"))
            if status != "stopped":
                observe(cfg, "result", i, status, name, time.monotonic()-check_started, getattr(session,"last_response",None))
            if status == "stopped":
                reason = "stopped"
                break
            if status == "ratelimit":
                events.put(("fatal", i, detail))
                reason = "limit"
                break
            if status == "available":
                p.save(name)
                events.put(("valid", i, p.format_username(name)))
            elif status == "taken":
                events.put(("invalid", i, p.format_username(name)))
            else:
                events.put(("error", i, f"{name}: resposta de disponibilidade desconhecida."))
        except requests.exceptions.RequestException as e:
            observe(cfg, "result", i, "error", name, time.monotonic()-check_started)
            events.put(("error", i, f"Erro de conexão ({type(e).__name__}). Confira a rede e as credenciais."))
        except Exception as e:  # noqa
            observe(cfg, "result", i, "error", name, time.monotonic()-check_started)
            events.put(("error", i, f"Falha ao processar resposta ou salvar resultado ({type(e).__name__})."))
        pause = p.direct_pause(token)
        interval = max(cfg.get("username_interval", 0), p.delay if (pool or pause is None) else pause)
        if stop.wait(interval + (0 if pool else slow)):
            reason = "stopped"
            break
    observe(cfg, "finish", "completed" if reason == "finished" else reason)
    events.put(("done", 0, reason))
