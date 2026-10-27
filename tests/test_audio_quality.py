import unittest
from unittest.mock import patch

from pytgcalls.types import AudioQuality
from videl.core.audio_quality import audio_quality, audio_quality_label


class VoiceAudioQualityTests(unittest.TestCase):
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
