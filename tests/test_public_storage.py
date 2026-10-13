import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import config, preferences
from core.session import Session
from core.platform_base import Platform


class PublicStorage(unittest.TestCase):
    def setUp(self):
        self.temp = Path(__file__).resolve().parent / (".test-data-" + uuid.uuid4().hex)
        self.temp.mkdir()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        assert self.temp.parent == Path(__file__).resolve().parent
        shutil.rmtree(self.temp)

    def test_windows_accounts_use_distinct_local_appdata(self):
        for account in ("account-one", "account-two"):
            local = str(self.temp / account)
            with patch.dict(os.environ, {"LOCALAPPDATA": local}, clear=True), patch.object(config.sys, "platform", "win32"):
                self.assertEqual(config.user_data_dir(), os.path.join(local, "UIsername"))

    def test_data_override_must_be_absolute(self):
        with patch.dict(os.environ, {"USERNAMEGEN_DATA_DIR": str(self.temp)}, clear=True):
            self.assertEqual(config.user_data_dir(), str(self.temp))
        with patch.dict(os.environ, {"USERNAMEGEN_DATA_DIR": "relative"}, clear=True):
            with self.assertRaises(ValueError): config.user_data_dir()

    def test_linux_xdg_and_macos_home_are_supported(self):
        home = str(self.temp / "home")
        xdg = str(self.temp / "xdg")
        with patch.dict(os.environ, {"XDG_DATA_HOME": xdg}, clear=True), patch.object(config.sys, "platform", "linux"):
            self.assertEqual(config.user_data_dir(), os.path.join(xdg, "UIsername"))
        with patch.dict(os.environ, {}, clear=True), patch.object(config.sys, "platform", "darwin"), patch.object(config.os.path, "expanduser", return_value=home):
            self.assertEqual(config.user_data_dir(), os.path.join(home, "Library", "Application Support", "UIsername"))

    def test_settings_and_proxies_create_new_user_directories(self):
        settings = self.temp / "new" / "settings.json"
        preferences.save(str(settings), {"language": "es"})
        self.assertEqual(preferences.load(str(settings))["language"], "es")
        proxies = self.temp / "other" / "proxies.txt"
        with patch("core.session.PROXY_FILE", str(proxies)):
            Session.save_proxies("example.invalid:8080")
            self.assertEqual(Session.load_proxies().strip(), "example.invalid:8080")

    def test_proxy_save_errors_are_reported(self):
        with patch("core.session.os.makedirs", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError): Session.save_proxies("example.invalid:8080")

    def test_results_use_user_storage_and_display_no_account_name(self):
        platform = Platform()
        platform.name = "Example"
        with patch("core.platform_base.NAMES_DIR", str(self.temp / "Names")):
            platform.save("example-name")
            self.assertEqual(Path(platform.file).read_text().strip(), "example-name")
            self.assertEqual(platform.meta()["display_file"], os.path.join("UIsername", "Names", "Example", "valids.txt"))

    def test_frozen_ui_resources_stay_separate_from_user_storage(self):
        bundle = str(self.temp / "bundle")
        with patch.object(config.sys, "_MEIPASS", bundle, create=True):
            self.assertEqual(config.resource_dir(), bundle)
            self.assertNotEqual(config.DATA_DIR, config.resource_dir())
