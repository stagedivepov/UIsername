"""GitLab.com user and group namespace lookup (not a registration guarantee)."""
import re
import string
from urllib.parse import quote

from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body

API = "https://gitlab.com/api/v4"
RESERVED = set("admin api assets dashboard explore files groups health_check help import jwt login oauth profile projects public search snippets uploads users".split())


class GitLab(Platform):
    name, mark = "GitLab", "GL"
    desc = "Consulta usuários e grupos no GitLab.com. Nomes não encontrados ainda podem estar reservados."
    tags = ("Token opcional", "2–255 caracteres")
    min_len, max_len = 2, 255
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 0.6
    has_token = True
    token_title = "Token do GitLab (opcional)"
    token_hint = "Personal access token"
    token_help = "Se necessário, use um token com acesso de leitura à API do GitLab.com."
    lookup_only = True

    def normalize(self, username):
        return username.strip().removeprefix("@").lower()

    def local_ok(self, username):
        return (2 <= len(username) <= 255
                and re.fullmatch(r"[a-z0-9](?:[a-z0-9]|[_.-](?=[a-z0-9]))*[a-z0-9]", username) is not None
                and username not in RESERVED
                and not username.endswith((".git", ".atom", ".png")))

    def check(self, session, username, token="", proxy=None):
        response = get(session, API + "/users", params={"username": username}, token=token)
        signal = http_signal(response)
        if signal:
            return signal
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        users = json_body(response)
        if not isinstance(users, list):
            raise RuntimeError("Missing user list")
        if users:
            if any(isinstance(u, dict) and isinstance(u.get("username"), str)
                   and u["username"].lower() == username.lower() for u in users):
                return "taken", ""
            raise RuntimeError("Unexpected username response")
        # Groups occupy the same top-level namespace as users.
        response = get(session, API + "/groups/" + quote(username, safe=""), token=token)
        signal = http_signal(response)
        if signal:
            return signal
        group = json_body(response)
        if response.status_code == 200 and isinstance(group, dict):
            path = group.get("full_path")
            if isinstance(path, str) and path.lower() == username.lower():
                return "taken", ""
        if response.status_code == 404 and isinstance(group, dict) and group.get("message") == "404 Group Not Found":
            return "available", ""
        raise RuntimeError("Unrecognized namespace response")
