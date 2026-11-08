import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatMemberStatus, ChatType

from videl.modules import cplay


class ChannelPlayTargetTests(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_link_channel_when_bot_is_not_admin(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        message = NS(chat=source, command=["channelplay", "@target"])
        bot_member = NS(status=ChatMemberStatus.MEMBER)

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(return_value=bot_member)), \
             patch.object(cplay, "set_linked_channel") as set_linked, \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        set_linked.assert_not_called()
        self.assertIn("admin", send.await_args.args[2].lower())
        self.assertIn("nothing was linked", send.await_args.args[2].lower())

    async def test_links_channel_after_bot_admin_is_verified(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        message = NS(chat=source, command=["channelplay", "@target"])
        bot_member = NS(status=ChatMemberStatus.ADMINISTRATOR)

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(return_value=bot_member)), \
             patch.object(cplay, "set_linked_channel") as set_linked, \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        set_linked.assert_called_once_with(source.id, target.id)
        self.assertIn("Channel linked", send.await_args.args[2])

    async def test_does_not_claim_channel_linked_when_setting_write_fails(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        message = NS(chat=source, command=["channelplay", "@target"])
        bot_member = NS(status=ChatMemberStatus.ADMINISTRATOR)

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(return_value=bot_member)), \
             patch.object(cplay, "set_linked_channel", return_value=False) as set_linked, \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        set_linked.assert_called_once_with(source.id, target.id)
        self.assertNotIn("Channel linked", send.await_args.args[2])
        self.assertIn("couldn’t save", send.await_args.args[2].lower())

    async def test_does_not_claim_unlinked_when_clear_write_fails(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        message = NS(chat=source, command=["channelplay", "unlink"])

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay, "clear_linked_channel", return_value=False) as clear_linked, \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        clear_linked.assert_called_once_with(source.id)
        self.assertNotIn("Channel unlinked", send.await_args.args[2])
        self.assertIn("couldn’t update", send.await_args.args[2].lower())

    async def test_status_explains_link_changes_do_not_move_or_stop_target_queue(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        message = NS(chat=source, command=["channelplay"])

        with patch.object(cplay, "get_linked_channel", return_value=-100202), \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        text = send.await_args.args[2].lower()
        self.assertIn("future /cplay", text)
        self.assertIn("not migrated", text)

    async def test_relink_explains_existing_target_queue_is_not_migrated(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        message = NS(chat=source, command=["channelplay", "@target"])
        bot_member = NS(status=ChatMemberStatus.ADMINISTRATOR)

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(return_value=bot_member)), \
             patch.object(cplay, "set_linked_channel", return_value=True), \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        text = send.await_args.args[2].lower()
        self.assertIn("future /cplay", text)
        self.assertIn("not migrated", text)

    async def test_unlink_explains_existing_target_playback_continues(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        message = NS(chat=source, command=["channelplay", "unlink"])

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay, "clear_linked_channel", return_value=True), \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        text = send.await_args.args[2].lower()
        self.assertIn("future /cplay", text)
        self.assertIn("does not stop", text)

    async def test_cplay_rejects_stale_link_before_downloading_replied_media(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        document = NS(mime_type="audio/mpeg", file_name="track.mp3", file_size=1024)
        reply = NS(video=None, audio=None, voice=None, video_note=None, document=document,
                   chat=NS(id=source.id), id=44)
        message = NS(chat=source, from_user=NS(id=90001, first_name="Listener"),
                     reply_to_message=reply, matches=[])
        bot_member = NS(status=ChatMemberStatus.MEMBER)

        with patch.object(cplay, "_db_track"), \
             patch.object(cplay, "get_linked_channel", return_value=target.id), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(return_value=bot_member)), \
             patch.object(cplay.bot, "get_messages", new=AsyncMock(return_value=reply)) as get_messages, \
             patch.object(cplay.bot, "download_media", new=AsyncMock(return_value="/tmp/stale-link.mp3")) as download, \
             patch("videl.core.queue.add_to_queue", return_value=None), \
             patch("videl.utils.helpers.delete_file"), \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.cplay_handler(cplay.bot, message)

        get_messages.assert_not_awaited()
        download.assert_not_awaited()
        self.assertIn("link", send.await_args.args[2].lower())

    async def test_fails_closed_if_bot_admin_status_cannot_be_verified(self):
        source = NS(id=-100101, type=ChatType.SUPERGROUP)
        target = NS(id=-100202, type=ChatType.CHANNEL, title="Target")
        message = NS(chat=source, command=["channelplay", "@target"])

        with patch.object(cplay, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(cplay.bot, "get_chat", new=AsyncMock(return_value=target)), \
             patch.object(cplay.bot, "get_me", new=AsyncMock(return_value=NS(id=777))), \
             patch.object(cplay.bot, "get_chat_member", new=AsyncMock(side_effect=RuntimeError("unavailable"))), \
             patch.object(cplay, "set_linked_channel") as set_linked, \
             patch.object(cplay, "rich_send", new=AsyncMock()) as send:
            await cplay.channelplay_cmd(cplay.bot, message)

        set_linked.assert_not_called()
        self.assertIn("couldn’t verify", send.await_args.args[2].lower())


if __name__ == "__main__":
    unittest.main()
