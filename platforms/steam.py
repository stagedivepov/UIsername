"""Steam public profile vanity URLs, not private login names or non-unique display names."""
import re
import string

from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body


class Steam(Platform):
    name, mark = "Steam", "ST"
    desc = "Verifica o identificador da URL pública steamcommunity.com/id/nome. Requer uma chave da Steam Web API."
    tags = ("Requer credenciais", "2–32 caracteres")
    min_len, max_len = 2, 32
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 0.5
    has_token = token_required = True
    token_title = "Chave da Steam Web API"
    token_hint = "32 hexadecimal characters"
    token_pattern = r"^[A-Fa-f0-9]{32}$"
    token_error = "Informe uma chave válida da Steam Web API (32 caracteres hexadecimais)."
    token_help = "Obtenha sua chave em steamcommunity.com/dev/apikey. A consulta não verifica o login privado nem o nome de exibição."
    lookup_only = True

    def normalize(self, username):
        return username.strip().removeprefix("@").lower()

    def local_ok(self, username):
        return re.fullmatch(r"[a-z0-9_-]{2,32}", username) is not None

    def check(self, session, username, token="", proxy=None):
        if not self.token_ok(token):
            return "ratelimit", self.token_error
        response = get(session, "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
                       params={"key": token, "vanityurl": username, "url_type": 1})
        signal = http_signal(response)
        if signal:
            return signal
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        body = json_body(response)
        data = body.get("response") if isinstance(body, dict) else None
        if not isinstance(data, dict) or type(data.get("success")) is not int:
            raise RuntimeError("Missing vanity URL result")
        if data["success"] == 1 and re.fullmatch(r"\d{17}", str(data.get("steamid", ""))):
            return "taken", ""
        if data["success"] == 42 and data.get("message") == "No match":
            return "available", ""
        raise RuntimeError("Unrecognized vanity URL result")
