"""Bluesky hosted handles. Custom domains have different ownership semantics and are excluded."""
import re
import string

from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body

SUFFIX = ".bsky.social"


class Bluesky(Platform):
    name, mark = "Bluesky", "BS"
    desc = "Gera e consulta nomes .bsky.social. Aceita @nome ou o handle completo; nomes não encontrados podem estar reservados."
    tags = ("Sem proxy", "3–18 caracteres")
    min_len, max_len = 3, 18
    sep, sep_name = "-", "hífen"
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 0.6
    lookup_only = True

    def normalize(self, username):
        return username.strip().removeprefix("@").lower().removesuffix(SUFFIX)

    def local_ok(self, username):
        return re.fullmatch(r"[a-z0-9][a-z0-9-]{1,16}[a-z0-9]", username) is not None

    def format_username(self, username):
        return username + SUFFIX if self.local_ok(username) else username

    def check(self, session, username, token="", proxy=None):
        response = get(session, "https://bsky.social/xrpc/com.atproto.identity.resolveHandle",
                       params={"handle": self.format_username(username)})
        signal = http_signal(response)
        if signal:
            return signal
        data = json_body(response)
        if not isinstance(data, dict):
            raise RuntimeError("Missing identity response")
        if response.status_code == 200:
            if isinstance(data.get("did"), str) and re.fullmatch(r"did:[a-z0-9]+:[A-Za-z0-9._:%-]+", data["did"]):
                return "taken", ""
            raise RuntimeError("Missing valid DID")
        # Generic InvalidRequest may be a resolver outage; only explicit absence is accepted.
        if response.status_code == 400 and data.get("error") == "HandleNotFound":
            return "available", ""
        raise RuntimeError("Unrecognized handle response")
