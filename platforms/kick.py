import re
import string
from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body
class Kick(Platform):
    name, mark = "Kick", "K"
    desc = "Consulta canais pela API oficial da Kick. Requer token autorizado; ausência de canal não garante cadastro."
    tags = ("Requer credenciais", "3–25 caracteres")
    min_len, max_len = 3, 25
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 1.0
    lookup_only = True
    has_token = token_required = True
    token_title = "Access Token da Kick"
    token_hint = "OAuth access token"
    token_pattern = r"^\S{10,}$"
    token_error = "Informe um Access Token autorizado para a API da Kick."
    token_help = "Use um App Access Token ou um User Access Token com escopo channel:read, obtido no portal da Kick."
    def normalize(self, username): return username.strip().removeprefix("@").lower()
    def local_ok(self, username): return re.fullmatch(r"[a-z0-9_]{3,25}", username) is not None
    def check(self, session, username, token="", proxy=None):
        if not self.token_ok(token): return "ratelimit", self.token_error
        r = get(session, "https://api.kick.com/public/v1/channels", params={"slug": username}, token=token)
        signal = http_signal(r)
        if signal: return signal
        body = json_body(r)
        data = body.get("data") if isinstance(body, dict) else None
        if r.status_code == 200 and isinstance(data, list):
            if not data: return "available", ""
            if any(isinstance(c, dict) and isinstance(c.get("slug"), str) and c["slug"].lower() == username for c in data): return "taken", ""
        raise RuntimeError("Unrecognized Kick channel response")
