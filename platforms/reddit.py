"""Reddit's documented username_available endpoint; optional OAuth access token."""
import re
import string

from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body


class Reddit(Platform):
    name, mark = "Reddit", "RD"
    desc = "Verifica usernames do Reddit. Se o acesso público for bloqueado, use um token OAuth autorizado."
    tags = ("Token opcional", "3–20 caracteres")
    min_len, max_len = 3, 20
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 1.0
    has_token = True
    token_title = "Token OAuth do Reddit (opcional)"
    token_hint = "OAuth access token"
    token_help = "Use um access token de um aplicativo autorizado pelo Reddit. Não use sua senha."

    def normalize(self, username):
        name = username.strip().lower()
        if name.startswith("/u/"):
            return name[3:]
        if name.startswith("u/"):
            return name[2:]
        return name.removeprefix("@")

    def local_ok(self, username):
        return re.fullmatch(r"[a-z0-9_-]{3,20}", username) is not None

    def check(self, session, username, token="", proxy=None):
        base = "https://oauth.reddit.com" if token else "https://www.reddit.com"
        response = get(session, base + "/api/username_available", params={"user": username}, token=token)
        signal = http_signal(response)
        if signal:
            return signal
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        value = json_body(response)
        if type(value) is not bool:
            raise RuntimeError("Missing availability boolean")
        return ("available" if value else "taken"), ""
