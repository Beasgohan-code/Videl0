import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatMemberStatus, ChatType

from videl.app import music_callbacks
from videl.modules import cplay


class ChannelPlayerControlTests(unittest.IsolatedAsyncioTestCase):
    async def _call_target_channel(self, status, callback_id):
        client = NS(me=NS(id=777), get_chat_member=AsyncMock(return_value=NS(status=status)))
        query = NS(
            id=callback_id,
            data="skip",
            message=NS(chat=NS(id=-100202, type=ChatType.CHANNEL)),
            from_user=NS(id=90001),
            answer=AsyncMock(),
        )
        with patch("videl.app.router.blocked_reason", new=AsyncMock(return_value=None)), \
             patch.object(music_callbacks.music, "control", new=AsyncMock(return_value=None)) as control, \
             patch.object(music_callbacks, "rich_reply", new=AsyncMock()):
            await music_callbacks.handle(client, query)
        return query, control

    async def _call_bound(self, *, location_id, source_status, target_status, linked_target, source_id=-100101, target_id=-100202, bot_status=ChatMemberStatus.ADMINISTRATOR):
        actor_id, bot_id = 90001, 777

        async def get_member(chat_id, user_id):
            if chat_id == target_id and user_id == bot_id:
                return NS(status=bot_status)
            if chat_id == source_id and user_id == actor_id:
                return NS(status=source_status)
            if chat_id == target_id and user_id == actor_id:
                return NS(status=target_status)
            return NS(status=ChatMemberStatus.MEMBER)

        message_type = ChatType.SUPERGROUP if location_id == source_id else ChatType.CHANNEL
        client = NS(me=NS(id=bot_id), get_chat_member=AsyncMock(side_effect=get_member))
        query = NS(
            id=f"bound-{location_id}-{source_id}-{target_id}-{source_status}-{target_status}-{linked_target}-{bot_status}",
            data=f"cplayctl:skip:{source_id}:{target_id}",
            message=NS(chat=NS(id=location_id, type=message_type)),
            from_user=NS(id=actor_id),
            answer=AsyncMock(),
        )
        with patch("videl.utils.db.get_linked_channel", return_value=linked_target), \
             patch("videl.app.router.blocked_reason", new=AsyncMock(return_value=None)), \
             patch.object(music_callbacks.music, "control", new=AsyncMock(return_value=None)) as control, \
             patch.object(music_callbacks, "rich_reply", new=AsyncMock()):
            await music_callbacks.handle_bound(client, query, "skip", source_id, target_id)
        return query, control

    async def test_source_controls_encode_both_source_and_target_ids(self):
        keyboard = cplay.cplay_control_keyboard(-100101, -100202)
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        self.assertTrue(buttons)
        self.assertTrue(all(button.callback_data.endswith(":-100101:-100202") for button in buttons))
        self.assertIn("cplayctl:skip:-100101:-100202", {button.callback_data for button in buttons})

    async def test_bound_callback_dispatches_parsed_action_and_ids(self):
        data = "cplayctl:skip:-100101:-100202"
        match = re.fullmatch(
            r"cplayctl:(?P<action>pause|resume|skip|stop|show_queue|show_history|cycle_loop|volume_up|volume_down|replay):(?P<source>-?[0-9]{1,20}):(?P<target>-?[0-9]{1,20})",
            data,
        )
        query = NS(matches=[match], answer=AsyncMock())
        with patch("videl.app.music_callbacks.handle_bound", new=AsyncMock()) as handle_bound:
            await cplay.cplay_control_callback(cplay.bot, query)
        handle_bound.assert_awaited_once_with(cplay.bot, query, "skip", -100101, -100202)

    async def test_linked_source_group_admin_controls_only_its_current_target(self):
        query, control = await self._call_bound(
            location_id=-100101,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100202,
        )
        control.assert_awaited_once()
        self.assertEqual(control.await_args.args[0].message.chat.id, -100202)
        query.answer.assert_awaited_once()

    async def test_second_linked_source_group_admin_can_control_shared_target(self):
        query, control = await self._call_bound(
            location_id=-100303,
            source_id=-100303,
            target_id=-100202,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100202,
        )
        control.assert_awaited_once()
        self.assertEqual(control.await_args.args[0].message.chat.id, -100202)
        query.answer.assert_awaited_once()

    async def test_linked_source_admin_cannot_control_after_bot_loses_target_admin(self):
        query, control = await self._call_bound(
            location_id=-100101,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100202,
            bot_status=ChatMemberStatus.MEMBER,
        )
        control.assert_not_awaited()
        self.assertIn("bot access", query.answer.await_args.args[0].lower())

    async def test_stale_source_target_binding_is_rejected_before_control(self):
        query, control = await self._call_bound(
            location_id=-100101,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100303,
        )
        control.assert_not_awaited()
        self.assertIn("link changed", query.answer.await_args.args[0].lower())

    async def test_source_a_cannot_replay_source_b_controls_for_shared_target(self):
        query, control = await self._call_bound(
            location_id=-100101,
            source_id=-100303,
            target_id=-100202,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100202,
        )
        control.assert_not_awaited()
        self.assertIn("not bound", query.answer.await_args.args[0].lower())

    async def test_control_callback_from_unbound_chat_is_rejected(self):
        query, control = await self._call_bound(
            location_id=-100303,
            source_status=ChatMemberStatus.ADMINISTRATOR,
            target_status=ChatMemberStatus.ADMINISTRATOR,
            linked_target=-100202,
        )
        control.assert_not_awaited()
        self.assertIn("not bound", query.answer.await_args.args[0].lower())

    async def test_unprivileged_source_member_cannot_control_shared_target(self):
        query, control = await self._call_bound(
            location_id=-100101,
            source_status=ChatMemberStatus.MEMBER,
            target_status=ChatMemberStatus.MEMBER,
            linked_target=-100202,
        )
        control.assert_not_awaited()
        self.assertIn("admin", query.answer.await_args.args[0].lower())

    async def test_target_channel_admin_can_control_channel_queue(self):
        query, control = await self._call_target_channel(ChatMemberStatus.ADMINISTRATOR, "channel-admin")

        control.assert_awaited_once()
        ctx = control.await_args.args[0]
        self.assertEqual(ctx.message.chat.id, -100202)
        query.answer.assert_awaited_once()

    async def test_target_channel_admin_cannot_control_after_bot_loses_admin(self):
        async def get_member(_chat_id, user_id):
            status = ChatMemberStatus.ADMINISTRATOR if user_id == 90001 else ChatMemberStatus.MEMBER
            return NS(status=status)

        client = NS(me=NS(id=777), get_chat_member=AsyncMock(side_effect=get_member))
        query = NS(
            id="bot-demoted",
            data="skip",
            message=NS(chat=NS(id=-100202, type=ChatType.CHANNEL)),
            from_user=NS(id=90001),
            answer=AsyncMock(),
        )
        with patch("videl.app.router.blocked_reason", new=AsyncMock(return_value=None)), \
             patch.object(music_callbacks.music, "control", new=AsyncMock(return_value=None)) as control, \
             patch.object(music_callbacks, "rich_reply", new=AsyncMock()):
            await music_callbacks.handle(client, query)

        control.assert_not_awaited()
        self.assertIn("admin", query.answer.await_args.args[0].lower())

    async def test_target_channel_member_cannot_control_channel_queue(self):
        query, control = await self._call_target_channel(ChatMemberStatus.MEMBER, "channel-member")

        control.assert_not_awaited()
        query.answer.assert_awaited_once()
        self.assertIn("admin", query.answer.await_args.args[0].lower())


if __name__ == "__main__":
    unittest.main()
