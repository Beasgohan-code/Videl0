import unittest
from types import SimpleNamespace

from pyrogram import filters
import config
from videl.app.router import parse


class CommandPrefixTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_pyrogram_handlers_accept_each_configured_prefix(self):
        handler_filter = filters.command("ping", prefixes=config.COMMAND_PREFIX_LIST)
        client = SimpleNamespace(me=SimpleNamespace(username="VidelBot"))
        for prefix in config.COMMAND_PREFIX_LIST:
            message = SimpleNamespace(text=f"{prefix}ping hello", caption=None, command=None)
            with self.subTest(prefix=prefix):
                self.assertTrue(await handler_filter(client, message))
                self.assertEqual(message.command, ["ping", "hello"])

    def test_application_router_accepts_each_configured_prefix(self):
        for prefix in config.COMMAND_PREFIX_LIST:
            with self.subTest(prefix=prefix):
                parsed = parse(f"{prefix}help", "VidelBot")
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.name, "help")

    def test_prefix_list_is_characterwise_not_one_combined_prefix(self):
        self.assertEqual(config.COMMAND_PREFIX_LIST, list(config.COMMAND_PREFIXES))
