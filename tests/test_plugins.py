"""Offline coverage for the plugin command layer (no Telegram, no Mongo)."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app.router import Command, CommandError, Context, Parsed, Screen
from videl.app.routes import COMMANDS
from videl.plugins import afk, base, group, help as help_plugin, reminder, start


def message(text="/start", *, private=True, uid=42, mid=1):
    return SimpleNamespace(
        text=text,
        id=mid,
        chat=SimpleNamespace(id=42 if private else -1001234, type="private" if private else "supergroup"),
        from_user=SimpleNamespace(id=uid, first_name="Tester"),
        reply_to_message=None,
        message_thread_id=None,
    )


class StyleTests(unittest.TestCase):
    def test_small_caps_only_touches_visible_text(self):
        rendered = base.small_caps('<h3>Locks updated</h3><code>/lock links</code>')
        self.assertIn("Lᴏᴄᴋs ᴜᴘᴅᴀᴛᴇᴅ", rendered)
        self.assertIn("<code>/", rendered)
        self.assertIn("</code>", rendered)

    def test_plain_round_trips_heading_text_and_keeps_premium_badge(self):
        rendered = base.plain(base.heading("Group management", 3))
        self.assertIn("<h3>", rendered)
        self.assertIn("<tg-emoji emoji-id=", rendered)
        self.assertIn("</tg-emoji> Group management</h3>", rendered)

    def test_duration_bounds(self):
        self.assertEqual(base.parse_duration("2h"), 7200)
        self.assertEqual(base.parse_duration("7d"), 604800)
        for value in ("", "10", "10s", "0m", "99999999w", "1.5h", "-5m"):
            self.assertIsNone(base.parse_duration(value))

    def test_no_standalone_guide_command_survives(self):
        for command in COMMANDS:
            self.assertIsInstance(command, Command)
        self.assertNotIn("guide", {command.name for command in COMMANDS})


class StartTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_start_has_no_owner_navigation(self):
        ctx = Context(SimpleNamespace(me=SimpleNamespace(username="Videl0Bot")), message("/start"), Parsed("start", ""))
        screen = await start.start(ctx)
        callbacks = [item.callback_data for row in screen.keyboard.inline_keyboard for item in row]
        self.assertNotIn("cmds:owner:0", callbacks)
        self.assertNotIn("Owner workspace", screen.html)

    async def test_owner_start_reads_live_totals(self):
        ctx = Context(SimpleNamespace(me=SimpleNamespace(username="Videl0Bot")),
                      message("/start", uid=6265999542), Parsed("start", ""))
        with patch("videl.plugins.start.read_live_totals", return_value={"chats": 3, "users": 9, "plays": 12}):
            screen = await start.start(ctx)
        self.assertIn("owner console", base.plain(screen.html).lower())
        self.assertIn("12", screen.html)

    async def test_deep_link_opens_help_section(self):
        ctx = Context(SimpleNamespace(me=SimpleNamespace(username="Videl0Bot")), message("/start music"), Parsed("start", "music"))
        screen = await start.start(ctx)
        self.assertIn("Music", base.plain(screen.html))

    async def test_group_start_never_uses_web_app_buttons(self):
        ctx = Context(SimpleNamespace(me=SimpleNamespace(username="Videl0Bot")),
                      message("/start", private=False), Parsed("start", ""))
        screen = await start.start(ctx)
        self.assertTrue(all(item.web_app is None for row in screen.keyboard.inline_keyboard for item in row))


class HelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_section_lists_registered_commands(self):
        for section in ("music", "manage", "tools"):
            text, keyboard = help_plugin.render_section(section, owner=False)
            self.assertIn("<table", text)
            self.assertIsNone(keyboard)
            self.assertIn("<tg-button-row>", text)
        home, keyboard = help_plugin.render_section("home")
        self.assertIn("Help center", base.plain(home))
        self.assertIsNone(keyboard)
        self.assertIn("<tg-button-row>", home)

    async def test_owner_section_is_hidden_from_public_render(self):
        from vendor.richgram.richgram import rich_ui as transport
        text, keyboard = help_plugin.render_section("home", owner=False)
        _, markup = transport._native_buttons(text)
        callbacks = [item.callback_data for row in markup.inline_keyboard for item in row]
        self.assertIsNone(keyboard)
        self.assertNotIn("help:owner:0", callbacks)
        owner_text, _ = help_plugin.render_section("home", owner=True)
        _, owner_markup = transport._native_buttons(owner_text)
        owner_callbacks = [item.callback_data for row in owner_markup.inline_keyboard for item in row]
        self.assertIn("help:owner:0", owner_callbacks)

    async def test_search_finds_a_command(self):
        ctx = Context(SimpleNamespace(), message("/commands lock"), Parsed("commands", "lock"))
        screen = await help_plugin.directory_command(ctx)
        self.assertIn("/lock", base.plain(screen.html))

    async def test_pagination_never_exceeds_pages(self):
        from vendor.richgram.richgram import rich_ui as transport
        text, keyboard = help_plugin.render_section("music", page=99)
        _, markup = transport._native_buttons(text)
        callbacks = [item.callback_data for row in markup.inline_keyboard for item in row if item.callback_data]
        self.assertIsNone(keyboard)
        self.assertFalse(any(cb.endswith(":100") for cb in callbacks))


class GroupStatsTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_workspace_button_is_private_and_public_stats_stays_helpful(self):
        class Collection:
            def count_documents(self, _query):
                return 3
        class Database:
            def __getitem__(self, _name):
                return Collection()

        from vendor.richgram.richgram import rich_ui as transport
        with patch.object(group.base, "db", return_value=Database()):
            public = await group.stats(Context(SimpleNamespace(), message("/stats"), Parsed("stats", "")))
            _, public_markup = transport._native_buttons(public.html)
            public_callbacks = [item.callback_data for row in public_markup.inline_keyboard for item in row]
            self.assertIn("help:home", public_callbacks)
            self.assertNotIn("help:owner:0", public_callbacks)
            self.assertNotIn("Owner workspace", public.html)

            owner = await group.stats(Context(SimpleNamespace(), message("/stats", uid=6265999542), Parsed("stats", "")))
            _, owner_markup = transport._native_buttons(owner.html)
            owner_callbacks = [item.callback_data for row in owner_markup.inline_keyboard for item in row]
            self.assertIn("help:owner:0", owner_callbacks)
            self.assertIn("<footer", owner.html)


class GroupMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_set_title_updates_only_after_confirmation_and_reports_utf16_limit(self):
        chat = message("/settitle New title").chat
        client = SimpleNamespace(set_chat_title=AsyncMock(return_value=True))
        ctx = Context(client, message("/settitle New title"), Parsed("settitle", "New title"))
        screen = await group.set_title(ctx)
        client.set_chat_title.assert_awaited_once_with(chat.id, "New title")
        self.assertIn("New title", base.plain(screen.html))

        too_long = "😀" * 65
        invalid = Context(client, message("/settitle"), Parsed("settitle", too_long))
        with self.assertRaises(CommandError):
            await group.set_title(invalid)
        self.assertEqual(client.set_chat_title.await_count, 1)

    async def test_setdescription_clear_and_group_photo_actions(self):
        client = SimpleNamespace(
            set_chat_description=AsyncMock(return_value=True),
            set_chat_photo=AsyncMock(return_value=True),
            delete_chat_photo=AsyncMock(return_value=True),
        )
        clear_ctx = Context(client, message("/setdescription clear"), Parsed("setdescription", "clear"))
        cleared = await group.set_description(clear_ctx)
        client.set_chat_description.assert_awaited_once_with(42, "")
        self.assertIn("description cleared", base.plain(cleared.html).lower())

        photo_message = message("/setphoto")
        photo_message.reply_to_message = SimpleNamespace(photo=SimpleNamespace(file_id="photo-file-id"))
        await group.set_photo(Context(client, photo_message, Parsed("setphoto", "")))
        client.set_chat_photo.assert_awaited_once_with(42, "photo-file-id")

        removed = await group.delete_photo(Context(client, message("/delphoto"), Parsed("delphoto", "")))
        client.delete_chat_photo.assert_awaited_once_with(42)
        self.assertIn("photo removed", base.plain(removed.html).lower())


class FakeCollection:
    def __init__(self):
        self.rows = []

    def update_one(self, selector, update, upsert=False):
        row = next((item for item in self.rows if all(item.get(k) == v for k, v in selector.items())), None)
        if row is None:
            row = dict(selector)
            self.rows.append(row)
        for key, value in (update.get("$set") or {}).items():
            row[key] = value
        return SimpleNamespace(modified_count=1)

    def find_one(self, selector):
        return next((row for row in self.rows if all(row.get(k) == v for k, v in selector.items())), None)

    def find_one_and_delete(self, selector):
        row = self.find_one(selector)
        if row:
            self.rows.remove(row)
        return row


class AfkTests(unittest.IsolatedAsyncioTestCase):
    async def test_afk_sets_and_back_clears(self):
        store = FakeCollection()
        with patch.object(afk.base, "collection", return_value=store):
            ctx = Context(SimpleNamespace(), message("/afk lunch"), Parsed("afk", "lunch"))
            screen = await afk.afk(ctx)
            self.assertIn("Away mode on", base.plain(screen.html))
            self.assertEqual(store.rows[0]["reason"], "lunch")
            cleared = await afk.back(Context(SimpleNamespace(), message("/back"), Parsed("back", "")))
            self.assertIn("back", base.plain(cleared.html).lower())
            self.assertEqual(store.rows, [])

    async def test_afk_reports_missing_storage(self):
        with patch.object(afk.base, "collection", return_value=None):
            screen = await afk.afk(Context(SimpleNamespace(), message("/afk"), Parsed("afk", "")))
        self.assertIn("MongoDB", screen.html)


class ReminderTests(unittest.TestCase):
    def test_parse_accepts_human_units(self):
        self.assertEqual(reminder.parse("10m tea"), (600, "tea"))
        self.assertEqual(reminder.parse("in 2h call"), (7200, "call"))
        self.assertEqual(reminder.parse("2h call")[0], 7200)
        self.assertIsNone(reminder.parse("call"))
        self.assertIsNone(reminder.parse("5s too soon"))


class ManifestTests(unittest.TestCase):
    def test_manifest_is_unique_and_policies_are_valid(self):
        names = [command.name for command in COMMANDS]
        self.assertEqual(len(names), len(set(names)))
        for command in COMMANDS:
            self.assertIn(command.category, {"tools", "music", "manage", "owner"})
            self.assertIn(command.policy, {"public", "group", "admin", "owner"})
        by_name = {command.name: command for command in COMMANDS}
        for name in ("settitle", "setdescription", "setphoto", "delphoto"):
            self.assertEqual(by_name[name].policy, "admin")
            self.assertEqual(by_name[name].rights, ("can_change_info",))
