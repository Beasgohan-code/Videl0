import unittest
from unittest.mock import patch

from pytgcalls.types import AudioQuality
from videl.core.audio_quality import (
    audio_quality, audio_quality_label, clear_runtime_quality,
    current_quality, set_runtime_quality,
)


class VoiceAudioQualityTests(unittest.TestCase):
    def tearDown(self):
        clear_runtime_quality()

    def test_hosted_stream_default_uses_high_stereo_quality(self):
        with patch("config.VOICE_AUDIO_QUALITY", "high"):
            self.assertIs(audio_quality(), AudioQuality.HIGH)
            self.assertEqual(audio_quality_label(), "High · 48 kbps stereo")

    def test_lower_presets_are_available_for_weak_connections(self):
        for name, preset in (("high", AudioQuality.HIGH), ("medium", AudioQuality.MEDIUM), ("low", AudioQuality.LOW)):
            with self.subTest(name=name), patch("config.VOICE_AUDIO_QUALITY", name):
                self.assertIs(audio_quality(), preset)

    def test_unknown_preset_safely_falls_back_to_high_stereo(self):
        with patch("config.VOICE_AUDIO_QUALITY", "turbo"):
            self.assertIs(audio_quality(), AudioQuality.HIGH)
            self.assertIn("High", audio_quality_label())

    def test_runtime_preset_overrides_environment_for_new_streams(self):
        with patch("config.VOICE_AUDIO_QUALITY", "high"):
            self.assertTrue(set_runtime_quality("medium"))
            self.assertEqual(current_quality(), "medium")
            self.assertIs(audio_quality(), AudioQuality.MEDIUM)
            self.assertEqual(audio_quality_label(), "Medium · 36 kbps mono")
            self.assertFalse(set_runtime_quality("turbo"))
            self.assertEqual(current_quality(), "medium")

    def test_saved_preset_is_loaded_after_startup(self):
        from videl.core.audio_quality import load_saved_quality
        clear_runtime_quality()
        with patch("videl.utils.db.get_bot_setting", return_value="low"):
            self.assertEqual(load_saved_quality(), "low")
            self.assertIs(audio_quality(), AudioQuality.LOW)
