import unittest
from unittest.mock import AsyncMock, patch

from videl.modules import effects


class PlaybackEffectsFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_settings_lookup_falls_back_to_original_audio(self):
        with patch.object(effects, "_cache", {}), \
             patch.object(effects.asyncio, "to_thread", new=AsyncMock(side_effect=TimeoutError())), \
             patch.object(effects, "_process_file", new=AsyncMock()) as process:
            result = await effects.maybe_apply_effects(-100123, "/tmp/source.mp3")

        self.assertEqual(result, "/tmp/source.mp3")
        process.assert_not_awaited()

    async def test_disabled_effects_leave_original_audio_untouched(self):
        with patch.object(effects, "_cache", {-100123: {"enabled": False, "speed": 1.0, "bass": 0}}), \
             patch.object(effects, "_process_file", new=AsyncMock()) as process:
            result = await effects.maybe_apply_effects(-100123, "/tmp/source.mp3")

        self.assertEqual(result, "/tmp/source.mp3")
        process.assert_not_awaited()

    async def test_enabled_effects_process_audio_and_return_the_processed_path(self):
        with patch.object(effects, "_cache", {-100123: {"enabled": True, "speed": 1.25, "bass": 0}}), \
             patch.object(effects, "_process_file", new=AsyncMock(return_value="/tmp/processed.mp3")) as process:
            result = await effects.maybe_apply_effects(-100123, "/tmp/source.mp3")

        self.assertEqual(result, "/tmp/processed.mp3")
        process.assert_awaited_once_with("/tmp/source.mp3", 1.25, 0)
