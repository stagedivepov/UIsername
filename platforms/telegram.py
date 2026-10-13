"""Plataforma telegram: regras de formato + verificação de disponibilidade."""
import html
import re
import string

import requests

from core.config import PROXY_TIMEOUT
from core.platform_base import Platform

TELEGRAM_URL = "https://t.me/"



class Telegram(Platform):
    """Sem API pública de disponibilidade: lê a página t.me/<usuario>. Quando o nome não existe, o título
    da página vira 'Telegram: Contact @nome'; quando existe (usuário, canal, grupo ou bot) mostra o nome real."""
    name = "Telegram"
    mark = "TG"
    desc = "Lê a página pública t.me do @username. Usuários, canais e bots dividem o mesmo espaço de nomes."
    tags = ("Proxy opcional", "5–32 caracteres")
    min_len, max_len = 5, 32
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.1
    direct_delay = 1.0
    random_chars = string.ascii_lowercase + string.digits
    first_chars = string.ascii_lowercase            # o username precisa começar com letra
    proxy_optional = True

    def normalize(self, username):
        return username.strip().lstrip("@").lower()

    def local_ok(self, username):
        return (re.fullmatch(r"[a-z][a-z0-9_]{3,30}[a-z0-9]", username) is not None
                and "__" not in username)

    def check(self, session, username, token="", proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = (requests if proxy else session).get(TELEGRAM_URL + username, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Accept": "text/html,application/xhtml+xml"}, proxies=proxies, timeout=PROXY_TIMEOUT)
        sc = r.status_code
        if sc == 200:
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', r.text)
            if not m:
                return "retry", "30"                 # página inesperada (bloqueio/captcha): esfria
            title = html.unescape(m.group(1)).strip().lower()
            return ("available" if title == f"telegram: contact @{username}" else "taken"), ""
        if sc == 429:
            return "retry", "60"
        if sc in (407, 502, 503, 504):
            return "badproxy", ""
        raise RuntimeError(f"HTTP {sc}")
