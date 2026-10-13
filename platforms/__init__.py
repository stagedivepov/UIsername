"""Registro das plataformas. Para adicionar uma nova: crie platforms/<nome>.py (copie um existente)
e inclua a classe na lista PLATFORMS abaixo. A interface se adapta sozinha."""
from platforms.roblox import Roblox
from platforms.github import GitHub
from platforms.discord import Discord
from platforms.twitch import Twitch
from platforms.tiktok import TikTok
from platforms.instagram import Instagram
from platforms.youtube import YouTube
from platforms.telegram import Telegram
from platforms.playstation import PlayStation
from platforms.reddit import Reddit
from platforms.steam import Steam
from platforms.gitlab import GitLab
from platforms.bluesky import Bluesky

from platforms.x import X
from platforms.kick import Kick
from platforms.minecraft import Minecraft
from platforms.chesscom import ChessCom
from platforms.lichess import Lichess

PLATFORMS = [Roblox(), GitHub(), Discord(), Twitch(), TikTok(), Instagram(), YouTube(), Telegram(),
             PlayStation(), Reddit(), Steam(), GitLab(), Bluesky(), X(), Kick(), Minecraft(), ChessCom(), Lichess()]
PLATFORM_BY_NAME = {p.name: p for p in PLATFORMS}
