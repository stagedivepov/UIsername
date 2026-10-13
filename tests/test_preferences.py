import json
from pathlib import Path
import re
import shutil
import uuid
import unittest
from unittest.mock import patch

from core import preferences


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parent
        self.temp_path = parent / ('.test-data-' + uuid.uuid4().hex)
        self.temp_path.mkdir()
        self.addCleanup(self.cleanup_files)
        self.path = str(self.temp_path / 'settings.json')

    def cleanup_files(self):
        assert self.temp_path.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(self.temp_path)

    def test_first_launch_has_no_language(self):
        self.assertIsNone(preferences.load(self.path)['language'])

    def test_old_theme_is_preserved_but_language_still_required(self):
        Path(self.path).write_text('{"theme":"light"}', encoding='utf-8')
        settings = preferences.load(self.path)
        self.assertEqual(settings['theme'], 'light')
        self.assertIsNone(settings['language'])

    def test_every_language_survives_reload(self):
        for lang in ('pt-BR', 'en', 'es', 'zh-CN', 'ja', 'ru', 'fr'):
            preferences.save(self.path, {'language': lang})
            self.assertEqual(preferences.load(self.path)['language'], lang)

    def test_all_themes_and_motion_survive_reload(self):
        for theme in ('dark','light','system','sky','dracula','nord','catppuccin','tokyo-night','rose-pine'):
            preferences.save(self.path, {'theme': theme, 'theme_animation': False})
            loaded = preferences.load(self.path)
            self.assertEqual(loaded['theme'], theme)
            self.assertFalse(loaded['theme_animation'])

    def test_partial_patch_preserves_other_preferences(self):
        preferences.save(self.path, {'language': 'ja', 'theme': 'system', 'default_amount': 250,
                                     'compact': True, 'auto_scroll': False, 'confirm_stop': True, 'sidebar_collapsed': True})
        preferences.save(self.path, {'theme': 'light', 'token': 'must-not-be-saved'})
        settings = preferences.load(self.path)
        self.assertEqual(settings['language'], 'ja')
        self.assertEqual(settings['default_amount'], 250)
        self.assertTrue(settings['compact'])
        self.assertFalse(settings['auto_scroll'])
        self.assertTrue(settings['confirm_stop'])
        self.assertTrue(settings['sidebar_collapsed'])
        self.assertNotIn('token', Path(self.path).read_text())

    def test_invalid_preferences_are_rejected_without_overwriting(self):
        preferences.save(self.path, {'language': 'ru'})
        original = Path(self.path).read_bytes()
        for patch_value in ({'language': 'unknown'}, {'theme': 'unknown'}, {'compact': 'false'},
                            {'default_amount': True}, {'default_amount': 0},
                            {'default_amount': 100001}, {'default_amount': 1.5}):
            with self.subTest(patch=patch_value), self.assertRaises(ValueError):
                preferences.save(self.path, patch_value)
            self.assertEqual(Path(self.path).read_bytes(), original)

    def test_corrupt_settings_return_safe_defaults(self):
        Path(self.path).write_text('{broken', encoding='utf-8')
        self.assertEqual(preferences.load(self.path), preferences.DEFAULTS)
        Path(self.path).write_text('{"language":"???","theme":"light","compact":"yes"}', encoding='utf-8')
        settings = preferences.load(self.path)
        self.assertIsNone(settings['language'])
        self.assertEqual(settings['theme'], 'light')
        self.assertFalse(settings['compact'])

    def test_failed_save_keeps_previous_file_and_removes_temporary_file(self):
        preferences.save(self.path, {'language': 'fr'})
        original = Path(self.path).read_bytes()
        with patch('core.preferences.os.replace', side_effect=PermissionError('read-only')):
            with self.assertRaises(PermissionError):
                preferences.save(self.path, {'language': 'ja'})
        self.assertEqual(Path(self.path).read_bytes(), original)
        self.assertEqual(list(self.temp_path.iterdir()), [Path(self.path)])

    def test_catalogs_complete_and_template_parameters_preserved(self):
        source = (Path(__file__).resolve().parents[1] / 'ui/translations.js').read_text(encoding='utf-8')
        catalog = json.loads(source.removeprefix('window.TRANSLATIONS = ').rstrip(';\n'))
        self.assertGreaterEqual(len(catalog), 181)
        for key, entries in catalog.items():
            self.assertEqual(set(entries), {'en', 'es', 'zh-CN', 'ja', 'ru', 'fr'}, key)
            for language, text in entries.items():
                self.assertTrue(text.strip(), (key, language))
                self.assertNotIn('\ufffd', text)
                self.assertEqual(sorted(re.findall(r'\{\d+\}', key)),
                                 sorted(re.findall(r'\{\d+\}', text)), (key, language))


if __name__ == '__main__':
    unittest.main()
