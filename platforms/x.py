import re
import string
from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body
class X(Platform):
    name, mark = "X (Twitter)", "X"
    icon_slug = "x"
    desc = "Consulta usuários pela API oficial do X. Requer Bearer Token com acesso ao endpoint de usuários."
    tags = ("Requer credenciais", "1–15 caracteres")
    min_len, max_len = 1, 15
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 1.0
    lookup_only = True
    has_token = token_required = True
    token_title = "Bearer Token do X"
    token_hint = "Bearer Token"
    token_pattern = r"^\S{10,}$"
    token_error = "Informe um Bearer Token autorizado para a API do X."
    token_help = "Use seu token do portal de desenvolvedores do X. O acesso depende do plano e das permissões da API."
    def normalize(self, username): return username.strip().removeprefix("@").lower()
    def local_ok(self, username): return re.fullmatch(r"[a-z0-9_]{1,15}", username) is not None
    def check(self, session, username, token="", proxy=None):
        if not self.token_ok(token): return "ratelimit", self.token_error
        r = get(session, "https://api.x.com/2/users/by/username/" + username, token=token)
        signal = http_signal(r)
        if signal: return signal
        body = json_body(r)
        if not isinstance(body, dict): raise RuntimeError("Missing X user response")
        data = body.get("data")
        if r.status_code == 200 and isinstance(data, dict) and isinstance(data.get("username"), str) and data["username"].lower() == username and re.fullmatch(r"[0-9]+", str(data.get("id", ""))): return "taken", ""
        errors = body.get("errors")
        if r.status_code in (200, 404) and not data and isinstance(errors, list) and errors and all(
            isinstance(e, dict) and e.get("type") in ("https://api.x.com/2/problems/resource-not-found", "https://api.twitter.com/2/problems/resource-not-found")
            and e.get("resource_type") == "user" and e.get("parameter") == "username"
            and str(e.get("value", e.get("resource_id", ""))).lower() == username for e in errors): return "available", ""
        raise RuntimeError("Unrecognized X user response")
