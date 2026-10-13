"""Plataforma twitch: regras de formato + verificação de disponibilidade."""
import os
import re
import string
import time

from core.config import REQUEST_TIMEOUT
from core.platform_base import Platform

TWITCH_API = "https://api.twitch.tv/helix/users"            # API oficial da Twitch (Helix)
TWITCH_TOKEN_API = "https://id.twitch.tv/oauth2/token"



class Twitch(Platform):
    """Twitch via API oficial (Helix). O endpoint antigo do repositório f-o/twitcher-username-availability-checker
    (passport.twitch.tv) não é oficial e hoje responde 404, então usamos: GET /helix/users?login=<nome>
    -> lista vazia = livre | usuário retornado = em uso.
    Precisa de um app gratuito em dev.twitch.tv/console (Client ID + Client Secret)."""
    name = "Twitch"
    mark = "T"
    desc = "Usa a API oficial da Twitch (Helix). Precisa de um app gratuito em dev.twitch.tv para gerar as credenciais."
    tags = ("Requer credenciais", "4–25 caracteres")
    min_len, max_len = 4, 25
    sep, sep_name = "_", "underscore"
    style = "lower"
    delay = 0.15
    batch_size = 100                        # a Helix aceita até 100 logins por requisição
    random_chars = string.ascii_lowercase + string.digits
    has_token = True
    token_required = True
    token_title = "Credenciais da Twitch"
    token_hint = "client_id:client_secret"
    token_help = ("Crie um app grátis em dev.twitch.tv/console e cole o Client ID e o Client Secret "
                  "separados por dois-pontos. Nomes suspensos ou desativados podem aparecer como livres.")
    token_error = "Informe as credenciais no formato client_id:client_secret."
    token_pattern = r"^[^:]*\S[^:]*:\s*\S"          # client_id:client_secret (os dois preenchidos)

    def __init__(self):
        self._cred = None       # credenciais usadas para gerar o token atual
        self._token = None      # app access token (client credentials)
        self._exp = 0.0         # quando o token expira

    def default_token(self):
        cid, sec = os.environ.get("TWITCH_CLIENT_ID", ""), os.environ.get("TWITCH_CLIENT_SECRET", "")
        return f"{cid}:{sec}" if cid and sec else ""

    def normalize(self, username):
        return username.strip().lower()             # nomes da Twitch não diferenciam maiúsculas

    def local_ok(self, username):
        return (4 <= len(username) <= 25
                and re.fullmatch(r"[a-z0-9_]+", username) is not None)

    def _get_token(self, session, cred, force=False):
        """Gera (ou reaproveita) o app access token. Retorna None se as credenciais forem recusadas."""
        if not force and self._token and self._cred == cred and time.time() < self._exp - 60:
            return self._token
        cid, _, sec = cred.partition(":")
        r = session.post(TWITCH_TOKEN_API, data={"client_id": cid.strip(), "client_secret": sec.strip(),
                                                 "grant_type": "client_credentials"},
                         timeout=REQUEST_TIMEOUT)
        if r.status_code in (400, 401, 403):
            return None
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} ao gerar o token da Twitch")
        data = r.json()
        self._cred, self._token = cred, data["access_token"]
        self._exp = time.time() + float(data.get("expires_in", 3600))
        return self._token

    def check(self, session, username, token="", proxy=None):
        cred = (token or "").strip()
        if not self.token_ok(cred):
            return "ratelimit", self.token_error
        cid = cred.partition(":")[0].strip()
        bad_cred = ("ratelimit", "Credenciais da Twitch inválidas. Confira o Client ID e o Client Secret.")
        for attempt in range(2):                     # 2ª volta: token expirou (401) -> gera outro
            tok = self._get_token(session, cred, force=attempt > 0)
            if tok is None:
                return bad_cred
            r = session.get(TWITCH_API, params={"login": username},
                            headers={"Client-Id": cid, "Authorization": f"Bearer {tok}"},
                            timeout=REQUEST_TIMEOUT)
            if r.status_code != 401:
                break
        else:
            return bad_cred
        limit, rem = r.headers.get("Ratelimit-Limit"), r.headers.get("Ratelimit-Remaining")
        self.remaining = f"{rem}/{limit}" if rem is not None and limit else None
        if r.status_code == 200:
            data = r.json().get("data")
            if not isinstance(data, list):
                raise RuntimeError("Resposta sem lista de usuários")
            return ("taken" if data else "available"), ""
        if r.status_code == 400:                     # login inválido para a Twitch
            return "taken", ""
        if r.status_code == 429:                     # limite de requisições: o worker espera e repete
            reset = r.headers.get("Ratelimit-Reset", "")
            wait = float(reset) - time.time() if reset.isdigit() else 5.0
            return "retry", str(min(max(wait, 1.0), 60.0))
        raise RuntimeError(f"HTTP {r.status_code}")

    def check_batch(self, session, names, token="", stop=None):
        """Até 100 logins por requisição (custa 1 ponto, igual a consultar 1 nome)."""
        cred = (token or "").strip()
        if not self.token_ok(cred):
            return {}, ("ratelimit", self.token_error)
        cid = cred.partition(":")[0].strip()
        bad_cred = ({}, ("ratelimit", "Credenciais da Twitch inválidas. Confira o Client ID e o Client Secret."))
        for attempt in range(2):                     # 2ª volta: token expirou (401) -> gera outro
            tok = self._get_token(session, cred, force=attempt > 0)
            if tok is None:
                return bad_cred
            r = session.get(TWITCH_API, params=[("login", n) for n in names],
                            headers={"Client-Id": cid, "Authorization": f"Bearer {tok}"},
                            timeout=REQUEST_TIMEOUT)
            if r.status_code != 401:
                break
        else:
            return bad_cred
        limit, rem = r.headers.get("Ratelimit-Limit"), r.headers.get("Ratelimit-Remaining")
        self.remaining = f"{rem}/{limit}" if rem is not None and limit else None
        if r.status_code == 200:
            data = r.json().get("data")
            if not isinstance(data, list) or any(not isinstance(u, dict) or not u.get("login") for u in data):
                raise RuntimeError("Resposta sem lista válida de usuários")
            taken = {u["login"].lower() for u in data}
            return {n: ("taken" if n.lower() in taken else "available") for n in names}, None
        if r.status_code == 400:                     # algum login inválido no lote: refaz um por um
            return self.single_fallback(session, names, token, stop)
        if r.status_code == 429:
            reset = r.headers.get("Ratelimit-Reset", "")
            wait = float(reset) - time.time() if reset.isdigit() else 5.0
            return {}, ("retry", str(min(max(wait, 1.0), 60.0)))
        raise RuntimeError(f"HTTP {r.status_code}")
