"""Every advertised command must point at an installed, real handler."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyrogram.enums import ChatMemberStatus, ChatType
from videl.app.router import Context, Parsed
from videl.app.routes import router
from videl.modules import ALL_MODULES
from videl.plugins import COMMAND_PLUGINS
from videl.utils.bot_commands import OWNER_COMMANDS
from videl.utils.command_catalog import ROOT, commands


class CommandRegistryAuditTests(unittest.IsolatedAsyncioTestCase):
    def test_each_guide_row_has_a_real_source_and_registered_handler(self):
        app_commands = router.commands
        for entry in commands():
            with self.subTest(command=entry["name"]):
                path = ROOT / entry["source"]
                self.assertTrue(path.is_file(), f"missing source: {entry['source']}")
                if entry["source"].startswith("videl/app/"):
                    self.assertIn(entry["name"], app_commands)
                    self.assertEqual(app_commands[entry["name"]].handler.__name__, entry["handler"])
                else:
                    tree = ast.parse(path.read_text())
                    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                    self.assertIn(entry["handler"], names)
                    if entry["source"].startswith("videl/plugins/"):
                        self.assertIn(entry["name"], app_commands, "plugin command is not mounted in the dispatcher")
                        active = app_commands[entry["name"]].handler
                        self.assertEqual(active.__module__, f"videl.plugins.{path.stem}")
                        self.assertEqual(active.__name__, entry["handler"])
                    elif entry["source"].startswith("videl/modules/"):
                        module = path.stem
                        self.assertIn(module, ALL_MODULES, f"{module} is documented but never loaded at startup")

    def test_every_declared_command_plugin_is_mounted(self):
        mounted = {command.handler.__module__.rsplit(".", 1)[-1] for command in router.commands.values()
                   if command.handler.__module__.startswith("videl.plugins.")}
        self.assertTrue(set(COMMAND_PLUGINS).issubset(mounted))

    def test_telegram_command_menu_contains_only_registered_commands(self):
        registered = {entry["name"] for entry in commands()}
        for name, _description in OWNER_COMMANDS:
            self.assertIn(name, registered, f"Telegram menu command /{name} has no handler")

    def test_setup_is_a_real_read_only_command_not_a_dead_callback_alias(self):
        command = router.commands["setup"]
        self.assertEqual(command.category, "manage")
        self.assertEqual(command.policy, "group")
        self.assertEqual(command.handler.__module__, "videl.plugins.setup")
        self.assertIn("permissions", command.summary.lower())

    async def test_setup_runs_a_live_permission_check_without_changing_group_settings(self):
        command = router.commands["setup"]
        client = SimpleNamespace(
            me=SimpleNamespace(id=900),
            get_me=AsyncMock(return_value=SimpleNamespace(id=900)),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(
                status=ChatMemberStatus.ADMINISTRATOR,
                privileges=SimpleNamespace(
                    can_delete_messages=True, can_restrict_members=True,
                    can_invite_users=True, can_pin_messages=True,
                    can_manage_video_chats=True,
                ),
            )),
        )
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123, type=ChatType.SUPERGROUP),
            from_user=SimpleNamespace(id=501),
        )
        screen = await command.handler(Context(client, message, Parsed("setup", "")))
        self.assertIn("granted", screen.html.lower())
        client.get_chat_member.assert_awaited_once_with(-100123, 900)
