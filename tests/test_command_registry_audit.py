"""Every advertised command must point at an installed, real handler."""
import ast
import unittest
from pathlib import Path
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

    def test_retired_aliases_are_gone_and_rose_style_adminlist_alias_is_registered(self):
        registered = {entry["name"] for entry in commands()}
        self.assertNotIn("setup", router.commands)
        self.assertNotIn("modernhelp", registered)
        self.assertIn("adminlist", registered)
        self.assertEqual(router.commands["adminlist"].handler.__name__, "admins")
        self.assertEqual(router.commands["adminlist"].policy, "group")
