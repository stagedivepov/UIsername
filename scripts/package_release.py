"""Package only public release files; never include runtime user data."""
from pathlib import Path
from shutil import copy2
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import APP_VERSION


def main():
    version = APP_VERSION
    executable = ROOT / "dist" / "UIsername.exe"
    if not executable.is_file():
        raise SystemExit("Build dist/UIsername.exe first")
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    exe = output / executable.name
    copy2(executable, exe)
    guide = ("UIsername " + version + " — Windows x64\n\n"
             "Double-click UIsername.exe. Python is included. Choose your language on first launch.\n"
             "Settings and results: %LOCALAPPDATA%\\UIsername\n"
             "Some platforms require your own API credentials. Internet is required for checks.\n"
             "If the native window cannot start, the app attempts to use your default browser.\n")
    package = output / ("UIsername-Windows-x64-" + version + ".zip")
    with ZipFile(package, "w", ZIP_DEFLATED) as archive:
        archive.write(exe, "UIsername.exe")
        archive.writestr("START-HERE.txt", guide)
        vocabulary_notice = ROOT / "ui" / "third-party-vocabulary.txt"
        if vocabulary_notice.is_file():
            archive.write(vocabulary_notice, "THIRD-PARTY-VOCABULARY.txt")
    lines = [hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name for path in (exe, package)]
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Release files ready: " + str(output))


if __name__ == "__main__":
    main()
