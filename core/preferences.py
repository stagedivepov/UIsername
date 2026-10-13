"""Validated, atomic preferences; never store platform credentials here."""
import json
import math
import os
import tempfile
import threading

DEFAULTS = {"startup_mode": "window", "theme": "dark", "theme_animation": True, "language": None, "compact": False,
            "auto_scroll": True, "confirm_stop": True, "cancel_confirmation_version": 1, "default_amount": 100,
            "username_interval": 0.0, "batch_enabled": True, "sidebar_collapsed": False, "use_proxies": False}
_lock = threading.RLock()


def validate(patch):
    clean = {}
    for key, value in patch.items():
        if key not in DEFAULTS:
            continue
        valid = ((key == "cancel_confirmation_version" and type(value) is int and value == 1)
                 or (key == "startup_mode" and value in ("window", "fullscreen"))
                 or (key == "theme" and value in ("dark", "light", "system", "sky", "dracula", "nord", "catppuccin", "tokyo-night", "rose-pine"))
                 or (key == "language" and value in ("pt-BR", "en", "es", "zh-CN", "ja", "ru", "fr"))
                 or (key in ("theme_animation", "compact", "auto_scroll", "confirm_stop", "batch_enabled", "sidebar_collapsed", "use_proxies") and type(value) is bool)
                 or (key == "username_interval" and type(value) in (int, float)
                     and math.isfinite(value) and 0 <= value <= 600)
                 or (key == "default_amount" and type(value) is int and 1 <= value <= 100000))
        if not valid:
            raise ValueError("Preferência inválida: " + key)
        clean[key] = value
    return clean


def load(path):
    with _lock:
        result = dict(DEFAULTS)
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                for key, value in data.items():
                    try:
                        result.update(validate({key: value}))
                    except ValueError:
                        pass
                # Enable the new shared confirmation once when upgrading older settings.
                # Explicit changes made after this revision keep the user's choice.
                if data.get("cancel_confirmation_version") != 1:
                    result["confirm_stop"] = True
        except (OSError, ValueError, UnicodeError):
            pass
        return result


def save(path, patch):
    clean = validate(patch)
    with _lock:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {**load(path), **clean}
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(path),
                                             prefix=".preferences-", suffix=".tmp", delete=False) as file:
                name = file.name
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        return data
