from platforms.public_profile import PublicProfile
class ChessCom(PublicProfile):
    name, mark = "Chess.com", "CH"
    icon_slug = "chessdotcom"
    desc = "Consulta perfis pela API pública do Chess.com, sem credenciais. Nomes ausentes podem estar reservados."
    tags = ("Sem proxy", "3–25 caracteres")
    min_len, max_len = 3, 25
    pattern = r"[a-z0-9_-]{3,25}"
    endpoint = "https://api.chess.com/pub/player/"
    profile_field = "username"
    def valid_identity(self, body): return type(body.get("player_id")) is int and body["player_id"] > 0
    def explicit_absence(self, body, username):
        message = body.get("message", "")
        return type(body.get("code")) is int and body["code"] == 0 and isinstance(message, str) and message.replace('\\"', '"').lower() == ('User "' + username + '" not found.').lower()
