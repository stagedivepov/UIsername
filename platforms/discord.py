"""Plataforma discord: regras de formato + verificação de disponibilidade."""
import base64
import json
import re
import string
import uuid

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

DISCORD_API = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"



class Discord(Platform):
    name = "Discord"
    mark = "D"
    desc = "Verifica o novo sistema de usernames do Discord. Funciona direto pelo seu IP (devagar) ou girando entre proxies."
    tags = ("Proxy opcional", "2–32 caracteres")
    min_len, max_len = 2, 32
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.1
    direct_delay = 1.5                      # sem proxy: 1 consulta a cada ~1,5s para evitar o limite do Discord
    random_chars = string.ascii_lowercase + string.digits
    proxy_optional = True

    def normalize(self, username):
        return username.strip().lower()

    def local_ok(self, username):
        return (2 <= len(username) <= 32
                and re.fullmatch(r"[a-z0-9_.]+", username) is not None
                and ".." not in username)

    @staticmethod
    def _headers():
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        props = {"os": "Windows", "browser": "Firefox", "device": "", "system_locale": "en-US",
                 "browser_user_agent": ua, "browser_version": "121.0", "os_version": "10",
                 "referrer": "", "referring_domain": "", "referrer_current": "",
                 "referring_domain_current": "", "release_channel": "stable",
                 "client_build_number": 260101, "client_event_source": None}
        return {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/register",
            "X-Discord-Locale": "en-US",
            "X-Super-Properties": base64.b64encode(json.dumps(props).encode()).decode(),
            "Cookie": f"__dcfduid={uuid.uuid4()}",
        }

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        # requests.post (sem session) para não reaproveitar cookies entre proxies diferentes
        r = (requests if proxy else session).post(DISCORD_API, json={"username": username}, headers=self._headers(),
                          proxies=proxies, timeout=PROXY_TIMEOUT)
        if r.status_code == 200:
            taken = r.json().get("taken")
            if not isinstance(taken, bool):
                raise RuntimeError("Resposta sem disponibilidade válida")
            return ("taken" if taken else "available"), ""
        if r.status_code == 400:
            return "taken", ""                      # username recusado pelo Discord
        if r.status_code == 429:                    # este proxy/IP tomou limite
            try:
                wait = float(r.json().get("retry_after", 30))
            except Exception:  # noqa
                wait = 30.0
            return "retry", str(min(max(wait, 1.0), 600.0))
        if r.status_code == 403:
            return ("retry", "120") if proxy else ("ratelimit", "O serviço bloqueou a consulta direta ou exige login. Tente mais tarde ou use uma API autorizada.")
        if r.status_code in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {r.status_code}")
