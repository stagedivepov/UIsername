import math
import queue
import unittest
from unittest.mock import Mock, patch

from core import preferences
from core.generator import generate_username
from core.platform_base import Platform
from core.worker import run_worker
from platforms.bluesky import Bluesky
from platforms.gitlab import GitLab
from platforms.steam import Steam
from platforms.reddit import Reddit
from app import WindowControls


class Dummy(Platform):
    name = "Dummy"
    delay = .2
    direct_delay = .4
    def local_ok(self, name): return True
    def check(self, *args): return "taken", ""
    def batch_limit(self, token=""): return 2
    def check_batch(self, session, names, token="", stop=None):
        return {name: "taken" for name in names}, None


class Features(unittest.TestCase):
    def run_names(self, **options):
        p = Dummy()
        p.check = Mock(wraps=p.check)
        p.check_batch = Mock(wraps=p.check_batch)
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = False
        events = queue.Queue()
        run_worker(p, 2, {"mode": "check", "names": ["alpha", "beta"], **options}, events, stop)
        self.assertEqual([kind for kind, *_ in events.queue], ["invalid", "invalid", "done"])
        return p, stop

    def test_disable_batch_uses_individual_checks_and_custom_delay(self):
        p, stop = self.run_names(batch_enabled=False, username_interval=2.5)
        self.assertEqual(p.check.call_count, 2)
        p.check_batch.assert_not_called()
        self.assertEqual([call.args[0] for call in stop.wait.call_args_list], [2.5, 2.5])

    def test_service_delay_is_preserved(self):
        _, stop = self.run_names(batch_enabled=False, username_interval=0)
        self.assertEqual([call.args[0] for call in stop.wait.call_args_list], [.4, .4])

    def test_batch_delay_scales_with_processed_names(self):
        p, stop = self.run_names(batch_enabled=True, username_interval=2.5)
        p.check.assert_not_called()
        p.check_batch.assert_called_once()
        stop.wait.assert_called_once_with(5.0)

    def test_interval_rejects_boolean_nan_infinity_and_invalid_range(self):
        for value in [True, -1, 601, math.nan, math.inf, "2"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                preferences.validate({"username_interval": value})
        self.assertEqual(preferences.validate({"username_interval": 2.5, "batch_enabled": False}),
                         {"username_interval": 2.5, "batch_enabled": False})

    def test_spanish_verbs_and_name_suffixes(self):
        p = Dummy()
        with patch("core.generator.rng.choice", side_effect=lambda values: values[0]):
            result = generate_username(p, {"mode": "es", "two_words": False, "digits": False, "use_sep": False})
            self.assertEqual(result, "Correr")
        with patch("core.generator.rng.choice", side_effect=lambda values: "suffix" if "suffix" in values else "taller" if "taller" in values else values[0]):
            result = generate_username(p, {"mode": "name", "base_name": "Ana", "suffixes": True,
                                           "digits": False, "name_language": "es"})
            self.assertTrue(result.endswith("taller"))

    def test_new_platforms_never_treat_auth_failures_as_available(self):
        session = Mock()
        session.get.return_value = Mock(status_code=403, headers={})
        for p in [Bluesky(), GitLab(), Steam(), Reddit()]:
            with self.subTest(platform=p.name):
                self.assertEqual(p.check(session, "username", "a" * 32)[0], "ratelimit")

    def test_bluesky_normalizes_and_formats_hosted_handles(self):
        p = Bluesky()
        self.assertEqual(p.normalize(" @Ana.bsky.social "), "ana")
        self.assertEqual(p.format_username("ana"), "ana.bsky.social")
        self.assertFalse(p.local_ok(p.normalize("@ana.example.com")))
        session = Mock()
        session.get.return_value = Mock(status_code=400, headers={})
        session.get.return_value.json.return_value = {"error": "InvalidRequest"}
        with self.assertRaises(RuntimeError): p.check(session, "ana")

    def test_native_window_controls(self):
        api = WindowControls()
        api._window = Mock(fullscreen=False)
        api.maximize(); api._window.maximize.assert_called_once()
        api.maximize(); api._window.restore.assert_called_once()
        self.assertTrue(api.fullscreen()["fullscreen"])
        api._window.toggle_fullscreen.assert_called_once()
        self.assertFalse(api.resize(1000, 700))
        self.assertFalse(api.fullscreen()["fullscreen"])
        api.minimize(); api._window.minimize.assert_called_once()
        api.close(); api._window.destroy.assert_called_once()
        self.assertTrue(api.resize(700, 300))
        api._window.resize.assert_called_once_with(900, 620)
        self.assertFalse(api.resize("1000", 700))
