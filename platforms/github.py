"""Plataforma github: regras de formato + verificação de disponibilidade."""
import json
import re
import string
import time

from core.config import REQUEST_TIMEOUT
from core.platform_base import Platform

GITHUB_API = "https://api.github.com/users/"
GITHUB_GRAPHQL = "https://api.github.com/graphql"               # vários nomes por requisição (com token)



class GitHub(Platform):
    name = "GitHub"
    mark = "G"
    desc = "Consulta a API pública do GitHub. Um token opcional aumenta o limite de requisições."
    tags = ("Sem proxy", "1–39 caracteres")
    token_title = "Token do GitHub (opcional)"
    token_hint = "com token: consulta em lote (bem mais rápido)"
    min_len, max_len = 1, 39
    sep, sep_name = "-", "hífen"
    style = "lower"
    delay = 0.3
    random_chars = string.ascii_lowercase + string.digits
    has_token = True

    def local_ok(self, username):
        return (1 <= len(username) <= 39
                and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9]))*", username) is not None)

    def batch_limit(self, token=""):
        return 50 if token else 1                   # lote só com token (GraphQL exige autenticação)

    def check_batch(self, session, names, token="", stop=None):
        """GraphQL: até 50 nomes por requisição. repositoryOwner cobre usuários E organizações,
        igual ao endpoint REST (que também considera nomes de organizações como ocupados)."""
        q = "query { " + " ".join(f"u{k}: repositoryOwner(login: {json.dumps(n)}) {{ login }}"
                                  for k, n in enumerate(names)) + " }"
        headers = {"Authorization": f"Bearer {token}", "User-Agent": "UsernameGenerator"}
        r = session.post(GITHUB_GRAPHQL, json={"query": q}, headers=headers, timeout=REQUEST_TIMEOUT)
        limit, rem = r.headers.get("X-RateLimit-Limit"), r.headers.get("X-RateLimit-Remaining")
        self.remaining = f"{rem}/{limit}" if rem is not None and limit else None
        if r.status_code == 401:
            return {}, ("ratelimit", "Token do GitHub inválido ou expirado. Confira o token.")
        if r.status_code in (403, 429):
            retry_after = r.headers.get("Retry-After", "")
            if retry_after.isdigit():               # limite secundário: espera e repete
                return {}, ("retry", retry_after)
            reset = r.headers.get("X-RateLimit-Reset", "")
            when = time.strftime("%H:%M", time.localtime(int(reset))) if reset.isdigit() else "em breve"
            return {}, ("ratelimit", f"Limite da API do GitHub atingido (libera às {when}).")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        j = r.json()
        for e in j.get("errors") or []:
            if e.get("type") == "RATE_LIMITED":
                return {}, ("ratelimit", "Limite da API do GitHub atingido. Tente de novo mais tarde.")
        data = j.get("data")
        if data is None:
            raise RuntimeError("resposta GraphQL sem dados")
        errors = j.get("errors") or []
        unresolved = {e.get("path", [None])[0] for e in errors
                      if e.get("path") and e.get("type") != "NOT_FOUND"}
        if any(not e.get("path") and e.get("type") != "NOT_FOUND" for e in errors):
            raise RuntimeError("A API GraphQL retornou erros sem resultado confiável")
        return {n: ("taken" if data[f"u{k}"] else "available")
                for k, n in enumerate(names) if f"u{k}" in data and f"u{k}" not in unresolved}, None

    def check(self, session, username, token="", proxy=None):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "UsernameGenerator"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = session.get(GITHUB_API + username, headers=headers, timeout=REQUEST_TIMEOUT)
        limit, rem = r.headers.get("X-RateLimit-Limit"), r.headers.get("X-RateLimit-Remaining")
        self.remaining = f"{rem}/{limit}" if rem is not None and limit else None
        if r.status_code == 404:
            return "available", ""       # não existe -> provavelmente livre
        if r.status_code == 200:
            return "taken", ""
        if r.status_code == 429 or (r.status_code == 403 and rem == "0"):
            reset = r.headers.get("X-RateLimit-Reset", "")
            when = time.strftime("%H:%M", time.localtime(int(reset))) if reset.isdigit() else "em breve"
            return "ratelimit", (f"Limite da API do GitHub atingido (libera às {when}). "
                                 "Use um token para aumentar o limite.")
        raise RuntimeError(f"HTTP {r.status_code}")
