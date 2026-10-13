"""Strict read-only lookups for public profiles; absence is not registration availability."""
import re
import string
from urllib.parse import quote
from core.platform_base import Platform
from platforms.http_helpers import get, http_signal, json_body

class PublicProfile(Platform):
    lookup_only = True
    style = "lower"
    random_chars = string.ascii_lowercase + string.digits
    delay = 1.0
    def normalize(self, username): return username.strip().removeprefix("@").lower()
    def local_ok(self, username):
        return self.min_len <= len(username) <= self.max_len and re.fullmatch(self.pattern, username) is not None
    def check(self, session, username, token="", proxy=None):
        r = get(session, self.endpoint + quote(username, safe=""), proxy=proxy)
        signal = http_signal(r)
        if signal: return signal
        body = json_body(r)
        if r.status_code == 200 and isinstance(body, dict):
            value = body.get(self.profile_field)
            if isinstance(value, str) and value.lower() == username.lower() and self.valid_identity(body):
                return "taken", ""
        if r.status_code == 404 and isinstance(body, dict) and self.explicit_absence(body, username):
            return "available", ""
        raise RuntimeError("Unrecognized profile response")
    def valid_identity(self, body): return True
    def explicit_absence(self, body, username): return False
