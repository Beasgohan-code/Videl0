import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import mongomock

import config
from pytgcalls.types import AudioQuality
from videl.core import audio_quality
from videl.modules import voice_admin


def message(user_id, command, *, private=True):
    return NS(
        from_user=NS(id=user_id),
        chat=NS(id=user_id if private else -100123, type=NS(value="private" if private else "supergroup")),
        command=command,
    )


class BotSettingStorageTests(unittest.TestCase):
    def test_global_bot_settings_persist_in_the_dedicated_collection(self):
        from videl.utils import db
        database = mongomock.MongoClient().videl
        with patch.object(db, "_db", database):
            self.assertTrue(db.set_bot_setting("voice_audio_quality", "medium"))
            self.assertEqual(db.get_bot_setting("voice_audio_quality"), "medium")
            self.assertEqual(db.get_bot_setting("missing", "fallback"), "fallback")


class VoiceAdminTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        audio_quality.clear_runtime_quality()

    async def test_owner_can_persist_global_quality_from_private_chat(self):
        msg = message(config.OWNER_ID, ["/voicequality", "medium"])
        with patch.object(voice_admin, "set_bot_setting", return_value=True) as save, \
             patch.object(voice_admin, "rich_reply", AsyncMock()) as reply:
            await voice_admin.voice_quality_command(None, msg)
        save.assert_called_once_with("voice_audio_quality", "medium")
        self.assertIs(audio_quality.audio_quality(), AudioQuality.MEDIUM)
        self.assertIn("Saved for future restarts", reply.await_args.args[1])

    async def test_bot_sudo_can_change_quality_in_private_chat(self):
        msg = message(701, ["/voicequality", "low"])
        with patch.object(voice_admin, "is_sudo_user", return_value=True), \
             patch.object(voice_admin, "set_bot_setting", return_value=False), \
             patch.object(voice_admin, "rich_reply", AsyncMock()) as reply:
            await voice_admin.voice_quality_command(None, msg)
        self.assertIs(audio_quality.audio_quality(), AudioQuality.LOW)
        self.assertIn("this process only", reply.await_args.args[1])

    async def test_group_admin_cannot_use_voice_quality_control(self):
        msg = message(701, ["/voicequality", "low"], private=False)
        with patch.object(voice_admin, "is_sudo_user") as sudo, \
             patch.object(voice_admin, "set_bot_setting") as save, \
             patch.object(voice_admin, "rich_reply", AsyncMock()):
            self.assertFalse(await voice_admin._can_manage_voice_settings(msg))
            sudo.assert_not_called()
            save.assert_not_called()

    async def test_voicehealth_omits_secrets_and_reports_audio_diagnostics(self):
        msg = message(config.OWNER_ID, ["/voicehealth"])
        with patch("videl.utils.assistant.assistant_status", return_value={"configured": True, "ready": False, "state": "failed"}), \
             patch("videl.utils.downloader_status.downloader_status", return_value={"shruti": {"state": "needs_api_key"}}), \
             patch.object(voice_admin, "rich_reply", AsyncMock()) as reply:
            await voice_admin.voice_health_command(None, msg)
        rendered = reply.await_args.args[1]
        self.assertIn("PyTgCalls engine", rendered)
        self.assertIn("FFmpeg", rendered)
        self.assertIn("needs api key", rendered.casefold())

    async def test_restart_is_owner_private_and_reexecutes_the_service_entrypoint(self):
        msg = message(config.OWNER_ID, ["/restart"])
        with patch.object(voice_admin.asyncio, "sleep", new=AsyncMock()), \
             patch.object(voice_admin.sys, "argv", ["/app/main.py", "--option"]), \
             patch.object(voice_admin.os, "execv") as execute, \
             patch.object(voice_admin, "rich_reply", AsyncMock()):
            await voice_admin.restart_command(None, msg)
        execute.assert_called_once_with(
            voice_admin.sys.executable,
            [voice_admin.sys.executable, "-m", "videl", "--option"],
        )

    async def test_non_owner_cannot_reexec_service(self):
        msg = message(701, ["/restart"])
        with patch.object(voice_admin.os, "execv") as execute, \
             patch.object(voice_admin, "rich_reply", AsyncMock()) as reply:
            await voice_admin.restart_command(None, msg)
        execute.assert_not_called()
        self.assertIn("Only the owner", reply.await_args.args[1])
