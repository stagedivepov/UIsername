"""Constantes, caminhos e configurações compartilhadas."""
import os
import re
import string
import sys

APP_TITLE = "UIsername"
APP_VERSION = "v2.0"

REQUEST_TIMEOUT = 10
PROXY_TIMEOUT = 8
CHARSET = string.ascii_letters + string.digits
LOG_MAX = 1500          # linhas máximas no log (evita lentidão em execuções longas)

SUFFIXES = """dev code codes coder tech labs hub pro io ai stack byte bytes logic craft works
studio hq ninja wizard engineer builds ops soft lab core net app cloud data""".split()
PREFIXES = "the real mr its hey dev code".split()

# key -> título. A ordem aqui define a ordem dos botões.
MODE_INFO = {
    "random": "Aleatório",
    "en": "Verbos em inglês",
    "pt": "Verbos em português",
    "es": "Verbos em espanhol",
    "name": "A partir do nome",
    "check": "Verificar usernames",
}

PROXY_RE = re.compile(r"^(?:[A-Za-z0-9]+://)?(?:[^@\s/]+@)?[A-Za-z0-9.\-]+:\d{2,5}$")


def base_dir() -> str:
    """Pasta do .exe (quando compilado) ou do projeto."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir() -> str:
    """Onde ficam os arquivos empacotados (interface). No .exe é a pasta temporária do PyInstaller."""
    return getattr(sys, "_MEIPASS", base_dir())


def user_data_dir() -> str:
    """User-specific writable storage, independent of executable/project location."""
    override = os.environ.get("USERNAMEGEN_DATA_DIR")
    if override:
        if not os.path.isabs(override):
            raise ValueError("USERNAMEGEN_DATA_DIR must be an absolute path")
        return os.path.normpath(override)
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        root = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    elif sys.platform == "darwin":
        root = os.path.join(home, "Library", "Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    if not os.path.isabs(root):
        root = os.path.join(home, "AppData", "Local") if sys.platform.startswith("win") else os.path.join(home, ".local", "share")
    return os.path.join(root, "UIsername")


DATA_DIR = user_data_dir()
NAMES_DIR = os.path.join(DATA_DIR, "Names")
PROXY_FILE = os.path.join(DATA_DIR, "proxies.txt")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
CRASH_FILE = os.path.join(DATA_DIR, "crash.log")
UI_DIR = os.path.join(resource_dir(), "ui")
