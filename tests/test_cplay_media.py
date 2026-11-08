import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.modules import cplay


class ChannelPlayMediaValidationTests(unittest.IsolatedAsyncioTestCase):
    async def _invoke_document(self, document):
        reply = NS(
            video=None, audio=None, voice=None, video_note=None, document=document,
            chat=NS(id=-90001), id=44,
        )
        message = NS(
            chat=NS(id=-90001),
            from_user=NS(id=90001, first_name="Listener"),
            reply_to_message=reply,
            matches=[re.match(r"(?P<cmd>cplay)(?:\s+(?P<q>.*))?", "cplay")],
        )
        with patch.object(cplay, "_db_track"), \
             patch.object(cplay, "get_linked_channel", return_value=-90002), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=NS(type=cplay.ChatType.CHANNEL))), \
             patch.object(cplay, "_bot_admin_status", new=AsyncMock(return_value=True)), \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send, \
             patch.object(cplay.bot, "get_messages", new=AsyncMock(return_value=reply)) as get_messages, \
             patch.object(cplay.bot, "download_media", new=AsyncMock(return_value="/tmp/untrusted.bin")) as download:
            await cplay.cplay_handler(cplay.bot, message)
        return send, get_messages, download

    async def test_replying_to_non_media_document_does_not_download_or_queue_it(self):
        document = NS(mime_type="application/pdf", file_name="report.pdf", file_size=1024)
        send, get_messages, download = await self._invoke_document(document)
        get_messages.assert_not_awaited()
        download.assert_not_awaited()
        self.assertIn("Unsupported file", send.await_args.args[2])

    async def test_oversized_document_is_rejected_before_download(self):
        document = NS(mime_type="audio/mpeg", file_name="long.mp3", file_size=201 * 1024 * 1024)
        send, get_messages, download = await self._invoke_document(document)
        get_messages.assert_not_awaited()
        download.assert_not_awaited()
        self.assertIn("File too large", send.await_args.args[2])


if __name__ == "__main__":
    unittest.main()
