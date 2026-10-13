"""Plataforma roblox: regras de formato + verificação de disponibilidade."""
import re
import string

from core.config import REQUEST_TIMEOUT
from core.platform_base import Platform

ROBLOX_API = "https://auth.roblox.com/v2/usernames/validate"
ROBLOX_LOOKUP_API = "https://users.roblox.com/v1/usernames/users"   # busca vários nomes de uma vez
BIRTHDAY = "02/27/2000"



class Roblox(Platform):
    name = "Roblox"
    mark = "R"
    desc = "Verifica se o username está livre usando a API oficial de validação da Roblox."
    tags = ("Sem proxy", "3–20 caracteres")
    min_len, max_len = 3, 20
    sep, sep_name = "_", "underscore"
    style = "title"
    delay = 0.2
    batch_size = 100
    random_chars = string.ascii_letters + string.digits

    def local_ok(self, username):
        return (3 <= len(username) <= 20
                and re.fullmatch(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?", username) is not None)

    def check(self, session, username, token="", proxy=None):
        r = session.get(ROBLOX_API, params={"Username": username, "Birthday": BIRTHDAY,
                                            "Context": 0}, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            return "retry", "20"                    # o worker espera e tenta de novo
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        code = r.json().get("code")
        if type(code) is not int:
            raise RuntimeError("Resposta sem código de validação")
        return ("available" if code == 0 else "taken"), ""

    def check_batch(self, session, names, token="", stop=None):
        """1) busca os nomes em lote: quem já existe é 'taken'. 2) só os que sobraram passam
        pelo validador oficial (que também pega nomes proibidos). Bem menos requisições."""
        r = session.post(ROBLOX_LOOKUP_API, json={"usernames": names, "excludeBannedUsers": False},
                         timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            return {}, ("retry", "10")
        if r.status_code == 400:
            return self.single_fallback(session, names, token, stop)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        found = set()
        for u in r.json().get("data", []):
            found.add(str(u.get("requestedUsername", "")).lower())
            found.add(str(u.get("name", "")).lower())
        results = {n: "taken" for n in names if n.lower() in found}
        rest = [n for n in names if n not in results]
        more, sig = self.single_fallback(session, rest, token, stop)
        results.update(more)
        return results, sig
