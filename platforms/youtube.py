"""Plataforma youtube: regras de formato + verificação de disponibilidade."""
import re
import string

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

YOUTUBE_API = "https://www.googleapis.com/youtube/v3/channels"     # API oficial (forHandle)
YOUTUBE_URL = "https://www.youtube.com/@"



class YouTube(Platform):
    """Com chave da YouTube Data API v3: channels.list?forHandle= (oficial, custa 1 unidade de cota,
    10.000/dia grátis). Sem chave: lê a página pública youtube.com/@handle (404 = não existe).
    Handle que existe = em uso; handles reservados/bloqueados pelo YouTube podem aparecer como livres."""
    name = "YouTube"
    mark = "YT"
    desc = "Verifica @handles. Com chave gratuita da API do YouTube, a consulta é oficial (10 mil por dia)."
    tags = ("Chave opcional", "3–30 caracteres")
    min_len, max_len = 3, 30
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.1
    direct_delay = 1.5
    random_chars = string.ascii_lowercase + string.digits
    proxy_optional = True
    has_token = True
    token_title = "Chave da API do YouTube (opcional)"
    token_hint = "AIza..."
    token_help = ("Crie uma chave grátis no Google Cloud (YouTube Data API v3): são 10.000 consultas por dia, "
                  "sem proxy. Sem chave, o app lê a página pública do canal (mais lento). Handles reservados "
                  "pelo YouTube podem aparecer como livres.")

    def direct_pause(self, token=""):
        return 0.1 if (token or "").strip() else self.direct_delay

    def normalize(self, username):
        return username.strip().lstrip("@").lower()

    def local_ok(self, username):
        return (3 <= len(username) <= 30
                and re.fullmatch(r"[a-z0-9][a-z0-9_.\-]*", username) is not None)

    @staticmethod
    def _error(r):
        try:
            err = r.json().get("error", {})
            reason = (err.get("errors") or [{}])[0].get("reason", "")
            return reason, str(err.get("message", ""))[:120]
        except Exception:  # noqa
            return "", ""

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        key = (token or "").strip()
        if key:
            r = (requests if proxy else session).get(YOUTUBE_API, params={"part": "id", "forHandle": "@" + username, "key": key},
                             proxies=proxies, timeout=PROXY_TIMEOUT)
            if r.status_code == 200:
                data = r.json().get("items")
                if not isinstance(data, list):
                    raise RuntimeError("Resposta sem lista de canais")
                return ("taken" if data else "available"), ""
            if r.status_code in (400, 401, 403):
                reason, msg = self._error(r)
                if reason in ("quotaExceeded", "dailyLimitExceeded"):
                    return "ratelimit", ("Cota diária da API do YouTube esgotada (10.000 consultas/dia). "
                                         "Ela renova à meia-noite, horário do Pacífico.")
                if reason in ("rateLimitExceeded", "userRateLimitExceeded"):
                    return "retry", "10"
                return "ratelimit", f"A API do YouTube recusou a chave: {msg or reason or r.status_code}"
            if r.status_code in (407, 502, 503, 504):
                return "badproxy", ""
            raise RuntimeError(f"HTTP {r.status_code}")
        r = (requests if proxy else session).get(YOUTUBE_URL + username, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Accept-Language": "en-US,en;q=0.5"}, proxies=proxies, timeout=PROXY_TIMEOUT,
            allow_redirects=False)
        sc = r.status_code
        if sc == 404:
            return "available", ""
        if sc == 200:
            return "taken", ""
        if sc == 429:
            return "retry", "60"
        if sc in (301, 302, 303, 307, 308, 403):
            return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
        if sc in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {sc}")
