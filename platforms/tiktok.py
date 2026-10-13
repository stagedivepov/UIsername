"""Plataforma tiktok: regras de formato + verificação de disponibilidade."""
import json
import re
import string

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

TIKTOK_URL = "https://www.tiktok.com/@"                     # página pública do perfil



class TikTok(Platform):
    """Sem API oficial: lê a página pública do perfil (@usuario) e interpreta o JSON embutido.
    statusCode 10202 = usuário não existe (livre) | 0 = existe (em uso)."""
    name = "TikTok"
    mark = "TT"
    desc = "Consulta o perfil público do TikTok. Funciona direto pelo seu IP (devagar) ou girando entre proxies."
    tags = ("Proxy opcional", "2–24 caracteres")
    min_len, max_len = 2, 24
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.1
    direct_delay = 2.0                      # sem proxy: 1 consulta a cada ~2s para evitar bloqueio
    random_chars = string.ascii_lowercase + string.digits
    proxy_optional = True

    def normalize(self, username):
        return username.strip().lstrip("@").lower()

    def local_ok(self, username):
        return (2 <= len(username) <= 24
                and re.fullmatch(r"[a-z0-9_.]+", username) is not None
                and not username.endswith("."))

    @staticmethod
    def _headers():
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = (requests if proxy else session).get(TIKTOK_URL + username, headers=self._headers(), proxies=proxies,
                         timeout=PROXY_TIMEOUT, allow_redirects=False)
        sc = r.status_code
        if sc == 200:
            m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
                          r.text, re.S)
            if not m:
                return ("retry", "60") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
            try:
                scope = json.loads(m.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]
            except (ValueError, KeyError, TypeError):
                return "retry", "60"
            code = scope.get("statusCode")
            if code == 10202:
                return "available", ""
            if code in (0, 10221, 10222) or scope.get("userInfo"):
                return "taken", ""                   # existe (ou está banido/reservado)
            raise RuntimeError(f"statusCode {code}")
        if sc == 429:
            return "retry", "60"
        if sc in (301, 302, 403):
            return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
        if sc in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {sc}")
