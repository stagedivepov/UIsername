import re
from platforms.public_profile import PublicProfile
class Minecraft(PublicProfile):
    name, mark = "Minecraft", "MC"
    desc = "Consulta nomes da edição Java no serviço da Minecraft. Não verifica gamertags da edição Bedrock."
    tags = ("Sem proxy", "3–16 caracteres")
    min_len, max_len = 3, 16
    pattern = r"[a-z0-9_]{3,16}"
    endpoint = "https://api.minecraftservices.com/minecraft/profile/lookup/name/"
    profile_field = "name"
    def valid_identity(self, body): return isinstance(body.get("id"), str) and re.fullmatch(r"[0-9a-f]{32}", body["id"]) is not None
    def explicit_absence(self, body, username):
        return body.get("path") == "/minecraft/profile/lookup/name/" + username and body.get("errorMessage") == "Couldn't find any profile with name " + username
