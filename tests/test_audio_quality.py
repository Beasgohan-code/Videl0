import unittest
from unittest.mock import patch

from pytgcalls.types import AudioQuality
from videl.core.audio_quality import audio_quality, audio_quality_label


class VoiceAudioQualityTests(unittest.TestCase):
    def test_studio_is_the_quality_first_default(self):
        with patch("config.VOICE_AUDIO_QUALITY", "studio"):
            self.assertIs(audio_quality(), AudioQuality.STUDIO)
            self.assertEqual(audio_quality_label(), "Studio · 96 kbps stereo")

    def test_lower_presets_are_available_for_weak_connections(self):
        for name, preset in (("high", AudioQuality.HIGH), ("medium", AudioQuality.MEDIUM), ("low", AudioQuality.LOW)):
            with self.subTest(name=name), patch("config.VOICE_AUDIO_QUALITY", name):
                self.assertIs(audio_quality(), preset)

    def test_unknown_preset_safely_falls_back_to_studio(self):
        with patch("config.VOICE_AUDIO_QUALITY", "turbo"):
            self.assertIs(audio_quality(), AudioQuality.STUDIO)
            self.assertIn("Studio", audio_quality_label())
