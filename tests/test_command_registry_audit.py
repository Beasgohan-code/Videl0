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

    def test_broad_group_text_listener_runs_after_the_command_router(self):
        path = Path(__file__).parents[1] / "videl/plugins/settings.py"
        tree = ast.parse(path.read_text())
        handler = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "blocklist_prompt_reply")
        calls = [decorator for decorator in handler.decorator_list if isinstance(decorator, ast.Call)
                 and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "on_message"]
        self.assertEqual(len(calls), 1)
        group = next((keyword.value for keyword in calls[0].keywords if keyword.arg == "group"), None)
        self.assertIsInstance(group, ast.Constant)
        self.assertGreater(group.value, 0, "broad group text listeners must run after the group-0 command router")

    def test_settings_and_setup_open_the_same_group_control_center(self):
        self.assertIn("settings", router.commands)
        self.assertIn("setup", router.commands)
        self.assertIs(router.commands["settings"].handler, router.commands["setup"].handler)
        self.assertEqual(router.commands["settings"].policy, "group")
        self.assertEqual(router.commands["setup"].policy, "group")

    def test_group_command_manager_uses_the_existing_disable_store(self):
        path = Path(__file__).parents[1] / "videl/plugins/settings.py"
        source = path.read_text()
        tree = ast.parse(source)
        screen = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_screen")
        callback = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "settings_callback")
        self.assertIn('section=="commands"', ast.get_source_segment(source, screen))
        self.assertIn("disabled_cmds", ast.get_source_segment(source, screen))
        callback_source = ast.get_source_segment(source, callback)
        self.assertIn("disable_cmd", callback_source)
        self.assertIn("enable_cmd", callback_source)
        self.assertIn("record_bot", callback_source)

    def test_every_declared_command_plugin_is_mounted(self):
        mounted = {command.handler.__module__.rsplit(".", 1)[-1] for command in router.commands.values()
                   if command.handler.__module__.startswith("videl.plugins.")}
        self.assertTrue(set(COMMAND_PLUGINS).issubset(mounted))

    def test_telegram_command_menu_contains_only_registered_commands(self):
        registered = {entry["name"] for entry in commands()}
        for name, _description in OWNER_COMMANDS:
            self.assertIn(name, registered, f"Telegram menu command /{name} has no handler")

    def test_setup_alias_and_rose_style_adminlist_alias_are_registered(self):
        registered = {entry["name"] for entry in commands()}
        self.assertIn("setup", router.commands)
        self.assertIn("setup", registered)
        self.assertNotIn("modernhelp", registered)
        self.assertIn("adminlist", registered)
        self.assertEqual(router.commands["adminlist"].handler.__name__, "admins")
        self.assertEqual(router.commands["adminlist"].policy, "group")
