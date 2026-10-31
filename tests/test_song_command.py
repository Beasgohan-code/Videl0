"""Handler-boundary tests for /song without Telegram or provider network calls."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.modules import downloader


class TelegramBadRequest(Exception):
    """Stand-in for a definite Telegram payload rejection."""


class SongCommandTests(unittest.IsolatedAsyncioTestCase):
    def _message(self, *, chat_type="group", query="sample track", reply=None):
        return SimpleNamespace(
            command=["song", *query.split()] if query else ["song"],
            chat=SimpleNamespace(id=-100123, type=chat_type),
            id=77,
            from_user=SimpleNamespace(id=456, first_name="Test user"),
            reply_to_message=reply,
        )

    async def _run_success(self, chat_type):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.mp3"
            path.write_bytes(b"audio data")
            status = SimpleNamespace(delete=AsyncMock())
            message = self._message(chat_type=chat_type)
            with (
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(path, {"title": "Track", "artist": "Artist", "duration": 65}))) as download,
                patch.object(downloader.bot, "send_audio", new=AsyncMock()) as send_audio,
                patch.object(downloader.bot, "send_document", new=AsyncMock()) as send_document,
            ):
                async def send_via_visual_call(function, **kwargs):
                    return await function(**kwargs)

                with patch.object(downloader, "visual_call", new=AsyncMock(side_effect=send_via_visual_call)):
                    await downloader.song_cmd(None, message)

            download.assert_awaited_once()
            self.assertTrue(download.await_args.kwargs["audio_only"])
            self.assertTrue(download.await_args.kwargs["include_info"])
            send_audio.assert_awaited_once()
            self.assertEqual(send_audio.await_args.kwargs["chat_id"], message.chat.id)
            self.assertEqual(send_audio.await_args.kwargs["reply_to_message_id"], message.id)
            send_document.assert_not_awaited()
            status.delete.assert_awaited_once()
            edit.assert_not_awaited()
            self.assertFalse(path.exists(), "successful delivery must clean up its temporary audio")

    async def test_successful_audio_delivery_in_group_and_private_chat(self):
        for chat_type in ("group", "private"):
            with self.subTest(chat_type=chat_type):
                await self._run_success(chat_type)

    async def test_reply_text_is_used_when_command_has_no_query(self):
        reply = SimpleNamespace(text="Reply-requested track", caption=None)
        message = self._message(query="", reply=reply)
        status = SimpleNamespace(delete=AsyncMock())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.mp3"
            path.write_bytes(b"audio data")
            with (
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()),
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(path, {"title": "Track", "duration": 1}))) as download,
                patch.object(downloader.bot, "send_audio", new=AsyncMock()),
                patch.object(downloader.bot, "send_document", new=AsyncMock()),
                patch.object(downloader, "visual_call", new=AsyncMock()),
            ):
                await downloader.song_cmd(None, message)
        self.assertEqual(download.await_args.args[0], "Reply-requested track")
        self.assertFalse(path.exists())

    async def test_blocked_query_does_not_start_download(self):
        message = self._message(query="porn track")
        with (
            patch.object(downloader, "rich_send", new=AsyncMock(return_value=SimpleNamespace())),
            patch.object(downloader, "_download_media", new=AsyncMock()) as download,
        ):
            await downloader.song_cmd(None, message)
        download.assert_not_awaited()

    async def test_provider_error_is_reported_without_upload(self):
        status = SimpleNamespace(delete=AsyncMock())
        with (
            patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
            patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
            patch.object(downloader, "_download_media", new=AsyncMock(side_effect=RuntimeError("provider unavailable"))),
            patch.object(downloader.bot, "send_audio", new=AsyncMock()) as send_audio,
            patch.object(downloader.bot, "send_document", new=AsyncMock()) as send_document,
        ):
            await downloader.song_cmd(None, self._message())
        edit.assert_awaited_once()
        send_audio.assert_not_awaited()
        send_document.assert_not_awaited()

    async def test_oversized_audio_is_not_sent_and_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.mp3"
            with path.open("wb") as file:
                file.truncate(50 * 1024 * 1024 + 1)
            status = SimpleNamespace(delete=AsyncMock())
            with (
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(path, {"title": "Large", "duration": 10}))),
                patch.object(downloader.bot, "send_audio", new=AsyncMock()) as send_audio,
            ):
                await downloader.song_cmd(None, self._message())
            send_audio.assert_not_awaited()
            self.assertIn("Audio file is too large", edit.await_args.args[1])
            self.assertFalse(path.exists())

    async def test_definite_audio_payload_rejection_falls_back_to_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.mp3"
            path.write_bytes(b"audio data")
            status = SimpleNamespace(delete=AsyncMock())
            with (
                patch.object(downloader, "BadRequest", TelegramBadRequest),
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(path, {"title": "Track", "duration": 10}))),
                patch.object(downloader.bot, "send_audio", new=AsyncMock()),
                patch.object(downloader.bot, "send_document", new=AsyncMock()) as send_document,
                patch.object(downloader, "visual_call", new=AsyncMock(side_effect=TelegramBadRequest("rejected payload"))),
            ):
                await downloader.song_cmd(None, self._message())
            send_document.assert_awaited_once()
            edit.assert_not_awaited()
            self.assertFalse(path.exists())

    async def test_ambiguous_send_failure_is_not_retried_as_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.mp3"
            path.write_bytes(b"audio data")
            status = SimpleNamespace(delete=AsyncMock())
            with (
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(path, {"title": "Track", "duration": 10}))),
                patch.object(downloader.bot, "send_audio", new=AsyncMock()),
                patch.object(downloader.bot, "send_document", new=AsyncMock()) as send_document,
                patch.object(downloader, "visual_call", new=AsyncMock(side_effect=TimeoutError("delivery uncertain"))),
            ):
                await downloader.song_cmd(None, self._message())
            send_document.assert_not_awaited()
            edit.assert_awaited_once()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
