"""Classe-base de uma plataforma. Para criar uma nova: copie um arquivo de platforms/,
ajuste as regras e registre a classe em platforms/__init__.py."""
import os
import re
import time

from core.config import NAMES_DIR, CHARSET


class Platform:
    name = ""
    icon_slug = ""
    mark = "•"                              # sigla de identificação na interface
    desc = ""
    tags = ()
    min_len, max_len = 1, 20
    sep, sep_name = "_", "underscore"      # separador entre palavras
    style = "title"                         # "title" = Verbo  |  "lower" = verbo
    delay = 0.2                             # pausa entre requisições
    random_chars = CHARSET
    modes = ("random", "en", "pt", "es", "name", "check")
    has_token = False                       # mostra o campo de token
    needs_proxy = False                     # exige lista de proxies
    proxy_optional = False                  # aceita proxies, mas funciona sem (direto pelo seu IP)
    direct_delay = None                     # pausa maior quando roda sem proxy (None = usa 'delay')
    batch_size = 1                          # > 1 = consulta vários nomes por requisição (modo rápido)
    first_chars = None                      # caracteres permitidos na 1ª letra (None = qualquer um)
    remaining = None                        # cota da API (se a plataforma informar)
    token_required = False                  # o campo de token é obrigatório?
    token_title = "Token (opcional)"
    token_hint = ""                         # texto de exemplo dentro do campo
    token_help = ""                         # explicação curta embaixo do campo
    token_error = "Informe o token."
    token_pattern = ""                      # regex que o token precisa casar ("" = qualquer valor)
    lookup_only = False                    # profile absence is not registration availability

    def default_token(self) -> str:
        """Valor inicial do campo de token (ex.: variável de ambiente)."""
        return ""

    def token_ok(self, token: str) -> bool:
        return re.search(self.token_pattern, token) is not None if self.token_pattern else True

    @property
    def folder(self):
        return os.path.join(NAMES_DIR, self.name)

    @property
    def file(self):
        return os.path.join(self.folder, "valids.txt")

    def save(self, username):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(self.format_username(username) + "\n")

    def format_username(self, username):
        return username

    def normalize(self, username) -> str:
        return username.strip()

    def local_ok(self, username) -> bool:
        """Regras de formato (checadas antes de gastar uma requisição)."""
        raise NotImplementedError

    def check(self, session, username, token="", proxy=None):
        """Retorna (status, detalhe).
        status: 'available' | 'taken' | 'ratelimit' (fatal) | 'retry' (detalhe = segundos
        de espera do proxy) | 'badproxy' (descarta o proxy)."""
        raise NotImplementedError

    def batch_limit(self, token="") -> int:
        """Quantos nomes cabem numa requisição (1 = sem lote)."""
        return self.batch_size

    def direct_pause(self, token=""):
        """Pausa entre consultas quando roda sem proxy (None = usa 'delay')."""
        return self.direct_delay

    def check_batch(self, session, names, token="", stop=None):
        """Verifica vários nomes de uma vez. Retorna (resultados, sinal):
        resultados = {nome: 'available' | 'taken'} (só os que foram resolvidos)
        sinal = None | ('retry', segundos) | ('ratelimit', mensagem)."""
        raise NotImplementedError

    def single_fallback(self, session, names, token="", stop=None):
        """Plano B do lote: verifica um por um, devolvendo o que deu certo até o primeiro limite."""
        results = {}
        for n in names:
            if stop is not None and stop.is_set():
                break
            status, detail = self.check(session, n, token)
            if status in ("available", "taken"):
                results[n] = status
            elif status in ("retry", "ratelimit"):
                return results, (status, detail)
            if stop is not None:
                if stop.wait(self.delay):
                    break
            else:
                time.sleep(self.delay)
        return results, None

    def meta(self) -> dict:
        """Dados que a interface precisa para montar a tela da plataforma."""
        return {
            "icon_slug": self.icon_slug or self.name.lower(),
            "name": self.name, "mark": self.mark, "desc": self.desc, "tags": list(self.tags),
            "min_len": self.min_len, "max_len": self.max_len,
            "sep": self.sep, "sep_name": self.sep_name, "modes": list(self.modes),
            "has_token": self.has_token, "token_required": self.token_required,
            "token_title": self.token_title, "token_hint": self.token_hint,
            "token_help": self.token_help, "token_error": self.token_error,
            "token_pattern": self.token_pattern, "default_token": self.default_token(),
            "needs_proxy": self.needs_proxy, "proxy_optional": self.proxy_optional,
            "file": self.file, "folder": self.folder,
            "display_file": os.path.join("UIsername", "Names", self.name, "valids.txt"),
            "lookup_only": self.lookup_only,
        }
