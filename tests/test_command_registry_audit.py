"""Every advertised command must point at an installed, real handler."""
import ast
import unittest
from pathlib import Path
from videl.app.routes import COMMANDS as MANIFEST, router
from videl.modules import ALL_MODULES
from videl.plugins import COMMAND_PLUGINS
from videl.utils.bot_commands import OWNER_COMMANDS, PUBLIC_COMMANDS
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

    def test_settings_is_the_registered_group_control_center_command(self):
        self.assertIn("settings", router.commands)
        self.assertNotIn("setup", router.commands)
        self.assertEqual(router.commands["settings"].policy, "group")

    def test_downloader_commands_are_catalogued_for_groups_and_private_chats(self):
        contexts = {entry["name"]: entry["context"] for entry in commands()}
        for name in ("song", "vsong", "download"):
            with self.subTest(command=name):
                self.assertEqual(contexts[name], "group_private")

    def test_private_only_tool_handlers_are_not_advertised_as_any_chat(self):
        contexts = {entry["name"]: entry["context"] for entry in commands()}
        from scripts.build_webapp_commands import command_rows
        web_contexts = {entry["name"]: entry["context"] for entry in command_rows()}
        for name in ("feedback", "inbox", "mydata", "preferences", "reminders", "sudohelp"):
            with self.subTest(command=name):
                self.assertEqual(contexts[name], "private")
                self.assertEqual(web_contexts[name], "private")

    def test_webapp_guide_is_generated_with_dual_context_labels(self):
        from scripts.build_webapp_commands import command_rows, render

        rows = {entry["name"]: entry for entry in command_rows()}
        for name in ("song", "vsong", "download"):
            with self.subTest(command=name):
                self.assertEqual(rows[name]["context"], "group_private")
        self.assertNotIn("setup", rows)
        self.assertNotIn("modernhelp", rows)
        self.assertEqual(
            Path("webapp/src/lib/commands.ts").read_text(),
            render(command_rows()),
        )
        self.assertIn('"summary": "Schedule a daily private admin digest in UTC"',
                      Path("webapp/src/lib/commands.ts").read_text())

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

    def test_ai_commands_are_unregistered_but_ordinary_faq_and_safety_remain(self):
        removed = {"faqassist", "faqcancel", "guardianai", "guardianjoin", "guardiansummary", "safetycheck"}
        registered = {entry["name"] for entry in commands()}
        self.assertTrue(removed.isdisjoint(registered))
        self.assertTrue(removed.isdisjoint(router.commands))
        self.assertTrue(removed.isdisjoint(name for name, _ in OWNER_COMMANDS))
        from videl.utils.bot_commands import PUBLIC_COMMANDS
        self.assertTrue(removed.isdisjoint(name for name, _ in PUBLIC_COMMANDS))
        self.assertNotIn("guardian", COMMAND_PLUGINS)
        self.assertIn("faq", router.commands)
        self.assertIn("setfaq", router.commands)
        self.assertIn("antispam", router.commands)
        self.assertIn("raidmode", router.commands)
        self.assertIn("safetystats", router.commands)
        self.assertIn("rulefeedback", router.commands)

    def test_provider_runtime_configuration_and_generated_commands_are_absent(self):
        import config
        from scripts.build_webapp_commands import command_rows
        self.assertFalse((ROOT / "videl/utils/gemini.py").exists())
        self.assertFalse(hasattr(config, "GEMINI_API_KEY"))
        names = {entry["name"] for entry in command_rows()}
        self.assertTrue({"faqassist", "faqcancel", "guardianai", "guardianjoin", "guardiansummary", "safetycheck"}.isdisjoint(names))
        guest_source = (ROOT / "videl/modules/telegram_features.py").read_text()
        self.assertNotIn("videl.utils.gemini", guest_source)
        self.assertNotIn("Gemini", guest_source)

    def test_command_audit_inventory_matches_the_live_registry_plus_retired_history(self):
        import csv
        with (ROOT / "docs/COMMAND_INVENTORY_AUDIT.csv").open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        retired = {row["command"] for row in rows if row["disposition"].startswith("Removed in Stage A")}
        inventory = {row["command"] for row in rows}
        live = {entry["name"] for entry in commands()}
        self.assertEqual(len(rows), 215)
        self.assertEqual(len(retired), 6)
        self.assertEqual(inventory - retired, live)
        current = {row["command"]: row for row in rows if row.get("registry_status") == "live"}
        self.assertEqual(set(current), live)
        for entry in commands():
            with self.subTest(runtime_inventory=entry["name"]):
                row = current[entry["name"]]
                self.assertEqual(row["runtime_category"], entry["category"])
                self.assertEqual(row["catalog_context_hint"], entry["context"])
                self.assertEqual(row["runtime_source"], entry["source"])
                self.assertEqual(row["runtime_handler"], entry["handler"])
                self.assertEqual(row["runtime_summary"], entry["summary"])
                menu_scopes = []
                if entry["name"] in {name for name, _ in PUBLIC_COMMANDS}:
                    menu_scopes.append("public")
                if entry["name"] in {name for name, _ in OWNER_COMMANDS}:
                    menu_scopes.append("owner")
                self.assertEqual(row["bot_command_menu_scopes"],
                                 ",".join(menu_scopes) or "not in curated BotCommand menu")
                manifest = {item.name: item for item in MANIFEST}.get(entry["name"])
                if manifest is not None:
                    self.assertEqual(row["runtime_auth_policy"], manifest.policy)
                    self.assertEqual(row["runtime_required_telegram_rights"],
                                     ",".join(manifest.rights) or "none declared")
                    self.assertEqual(row["runtime_block_policy"], manifest.block_policy)
        plan = (ROOT / "docs/STAGE_C_COMMAND_IMPROVEMENT_PLAN.md").read_text()
        self.assertIn("209 live commands", plan)
        self.assertIn("All 27 live `tools` commands", plan)

    async def test_removed_ai_commands_cannot_be_invoked_by_router(self):
        from types import SimpleNamespace
        client = SimpleNamespace(me=SimpleNamespace(username="Videl0Bot"))
        for name in ("faqassist", "faqcancel", "guardianai", "guardianjoin", "guardiansummary", "safetycheck"):
            with self.subTest(command=name):
                message = SimpleNamespace(
                    text=f"/{name} test", from_user=SimpleNamespace(id=42),
                    chat=SimpleNamespace(id=-100123, type="supergroup"), id=12,
                )
                self.assertFalse(await router.dispatch(client, message))

    def test_retired_setup_and_modernhelp_commands_stay_hidden(self):
        registered = {entry["name"] for entry in commands()}
        self.assertNotIn("setup", router.commands)
        self.assertNotIn("setup", registered)
        self.assertNotIn("modernhelp", registered)
        self.assertIn("adminlist", registered)
        self.assertEqual(router.commands["adminlist"].handler.__name__, "admins")
        self.assertEqual(router.commands["adminlist"].policy, "group")
