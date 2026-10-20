"""Callback routing: every button that ships must land somewhere real."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app.navigation import navigate
from videl.plugins import help as help_plugin


def query(data, *, private=True, uid=42):
    chat = SimpleNamespace(id=1 if private else -100123, type=SimpleNamespace(name="private" if private else "supergroup"))
    return SimpleNamespace(
        data=data,
        message=SimpleNamespace(chat=chat, from_user=SimpleNamespace(id=uid, first_name="Tester"), id=10),
        from_user=SimpleNamespace(id=uid, first_name="Tester"),
        answer=AsyncMock(),
    )


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    def client(self):
        return SimpleNamespace(me=SimpleNamespace(username="Videl0Bot"))

    async def run_callback(self, data, *, private=True):
        edited = AsyncMock()
        with patch("videl.app.navigation.rich_edit", new=edited):
            await navigate(self.client(), query(data, private=private))
        self.assertTrue(edited.called, f"{data} did not render anything")
        return edited.call_args.args[1]

    async def test_section_shortcuts_open_their_section(self):
        for data, marker in (("v2:section:music", "Mᴜsɪᴄ"), ("v2:section:tools", "Tᴇʟᴇɢʀᴀᴍ ᴛᴏᴏʟs"),
                             ("v2:section:protect", "Gʀᴏᴜᴘ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ")):
            text = await self.run_callback(data)
            self.assertIn(marker, text, data)

    async def test_unknown_section_falls_back_to_help_home(self):
        text = await self.run_callback("v2:section:nowhere")
        self.assertIn("Hᴇʟᴘ ᴄᴇɴᴛᴇʀ", text)

    async def test_help_start_renders_the_start_card(self):
        text = await self.run_callback("help:start")
        self.assertIn("Vɪᴅᴇʟ Sᴛᴜᴅɪᴏ", text)

    async def test_help_home_and_sections_render(self):
        for data in ("help:home", "help:music", "help:manage", "help:tools", "help:about", "cmds:all:0"):
            self.assertTrue(await self.run_callback(data))

    async def test_owner_page_is_refused_for_members(self):
        event = query("help:owner:0")
        edited = AsyncMock()
        with patch("videl.app.navigation.rich_edit", new=edited):
            await navigate(self.client(), event)
        self.assertFalse(edited.called, "member saw the owner help page")
        event.answer.assert_awaited()
        self.assertTrue(event.answer.call_args.kwargs.get("show_alert"))
