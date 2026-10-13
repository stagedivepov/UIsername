"""Plataforma playstation: regras de formato + verificação de disponibilidade."""
import re
import string

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

PSN_API = "https://accounts.api.playstation.com/api/v1/accounts/onlineIds"



class PlayStation(Platform):
    """EXPERIMENTAL. Usa o endpoint não oficial do cadastro da PlayStation (POST onlineIds, sem reservar o nome).
    Ele pode ter mudado e passado a exigir login; nesse caso o app para e avisa, em vez de marcar nomes errados."""
    name = "PlayStation"
    mark = "PS"
    desc = "Testa o Online ID no endpoint do cadastro da PlayStation. Experimental: pode exigir login."
    tags = ("Experimental", "3–16 caracteres")
    min_len, max_len = 3, 16
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.3
    direct_delay = 2.0
    random_chars = string.ascii_lowercase + string.digits
    first_chars = string.ascii_lowercase            # o Online ID precisa começar com letra
    proxy_optional = True

    def local_ok(self, username):
        return re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]{2,15}", username) is not None

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = (requests if proxy else session).post(PSN_API, json={"onlineId": username, "reserveIfAvailable": False},
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
                                                 "Gecko/20100101 Firefox/121.0"},
                          proxies=proxies, timeout=PROXY_TIMEOUT)
        sc = r.status_code
        if 200 <= sc < 300:
            return "available", ""
        if sc == 400:
            return "taken", ""
        if sc == 429:
            return "retry", "60"
        if sc in (401, 403):
            return "ratelimit", (f"A PlayStation recusou a consulta (HTTP {sc}). O endpoint não oficial pode "
                                 "ter mudado e passado a exigir login.")
        if sc in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {sc}")
