from platforms.public_profile import PublicProfile
class Lichess(PublicProfile):
    name, mark = "Lichess", "LI"
    desc = "Consulta perfis pela API pública do Lichess, sem credenciais. Nomes ausentes podem estar reservados."
    tags = ("Sem proxy", "3–20 caracteres")
    min_len, max_len = 3, 20
    pattern = r"[a-z0-9][a-z0-9_-]{1,18}[a-z0-9]"
    sep, sep_name = "-", "hífen"
    endpoint = "https://lichess.org/api/user/"
    profile_field = "username"
    def valid_identity(self, body): return isinstance(body.get("id"), str) and body["id"].lower() == body["username"].lower()
    def explicit_absence(self, body, username): return body.get("error") == "Not found"
