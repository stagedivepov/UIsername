"""Plataforma instagram: regras de formato + verificação de disponibilidade."""
import re
import string

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

INSTAGRAM_API = "https://www.instagram.com/api/v1/users/web_profile_info/"



class Instagram(Platform):
    """Sem API oficial de disponibilidade: usa o endpoint web de perfil.
    404 (ou usuário nulo) = livre | usuário retornado = em uso."""
    name = "Instagram"
    mark = "IG"
    desc = "Consulta o perfil público do Instagram. Funciona direto pelo seu IP (devagar) ou girando entre proxies."
    tags = ("Proxy opcional", "1–30 caracteres")
    min_len, max_len = 1, 30
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.15
    direct_delay = 4.0                      # sem proxy: o Instagram é bem mais rígido, 1 consulta a cada ~4s
    random_chars = string.ascii_lowercase + string.digits
    proxy_optional = True

    def normalize(self, username):
        return username.strip().lstrip("@").lower()

    def local_ok(self, username):
        return (1 <= len(username) <= 30
                and re.fullmatch(r"[a-z0-9_.]+", username) is not None
                and not username.startswith(".") and not username.endswith(".")
                and ".." not in username)

    @staticmethod
    def _headers():
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        }

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = (requests if proxy else session).get(INSTAGRAM_API, params={"username": username}, headers=self._headers(),
                         proxies=proxies, timeout=PROXY_TIMEOUT, allow_redirects=False)
        sc = r.status_code
        if sc == 404:
            return "available", ""
        if sc == 200:
            try:
                j = r.json()
            except ValueError:
                return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")                # caiu na página de login
            if j.get("require_login"):
                return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
            data = j.get("data")
            if not isinstance(data, dict) or "user" not in data:
                raise RuntimeError("Resposta sem dados de perfil")
            return ("taken" if data["user"] is not None else "available"), ""
        if sc == 429:
            try:
                wait = float(r.headers.get("Retry-After", 60))
            except ValueError:
                wait = 60.0
            return "retry", str(min(max(wait, 1.0), 600.0))
        if sc in (301, 302, 401, 403):
            return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
        if sc in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {sc}")
