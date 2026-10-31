from unittest import TestCase
from unittest.mock import patch

from videl.utils import custom_commands


class _Cursor(list):
    def sort(self, key, direction):
        return _Cursor(sorted(self, key=lambda row: row.get(key, ""), reverse=direction < 0))

    def limit(self, count):
        return _Cursor(self[:count])


class _Collection:
    def __init__(self):
        self.rows = []

    def update_one(self, query, update, upsert=False):
        row = next((item for item in self.rows if item["chat_id"] == query["chat_id"] and item["name"] == query["name"]), None)
        if row is None:
            row = dict(query)
            self.rows.append(row)
        row.update(update["$set"])

    def find_one(self, query, projection=None):
        row = next((item for item in self.rows if item["chat_id"] == query["chat_id"] and item["name"] == query["name"]), None)
        return dict(row) if row else None

    def count_documents(self, query):
        return sum(1 for row in self.rows if row["chat_id"] == query["chat_id"])

    def find(self, query, projection):
        return _Cursor([dict(row) for row in self.rows if row["chat_id"] == query["chat_id"]])

    def delete_one(self, query):
        self.rows = [row for row in self.rows if not (row["chat_id"] == query["chat_id"] and row["name"] == query["name"])]


class _DB:
    def __init__(self):
        self.commands = _Collection()

    def __getitem__(self, name):
        assert name == "mgmt_custom_commands"
        return self.commands


class CustomCommandTests(TestCase):
    def test_template_substitution_is_literal_and_limited_to_known_tokens(self):
        source = "Hi {name}, {args} · {mention}"
        self.assertEqual(custom_commands.render(source, {"name": "Ari", "args": "/help", "mention": "@ari"}), "Hi Ari, /help · @ari")
        with self.assertRaisesRegex(custom_commands.CustomCommandError, "Unknown placeholder"):
            custom_commands.validate_reply("{eval(1+1)}")
        with self.assertRaisesRegex(custom_commands.CustomCommandError, "braces"):
            custom_commands.validate_reply("unclosed {name")

    def test_native_commands_cannot_be_shadowed(self):
        catalog = [{"name": "start"}, {"name": "help"}, {"name": "ban"}]
        with patch("videl.utils.command_catalog.commands", return_value=catalog):
            with self.assertRaisesRegex(custom_commands.CustomCommandError, "already a Videl command"):
                custom_commands.validate_name("/ban")
            self.assertEqual(custom_commands.validate_name("welcome_note"), "welcome_note")

    def test_cooldown_is_per_user_and_per_group(self):
        allowed, retry = custom_commands.allow_use(-100, "hello_custom", 91, 10, now=100.0)
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)
        allowed, retry = custom_commands.allow_use(-100, "hello_custom", 91, 10, now=103.0)
        self.assertFalse(allowed)
        self.assertEqual(retry, 7)
        self.assertTrue(custom_commands.allow_use(-100, "hello_custom", 92, 10, now=103.0)[0])
        self.assertTrue(custom_commands.allow_use(-200, "hello_custom", 91, 10, now=103.0)[0])

    def test_create_update_list_and_delete_are_chat_scoped(self):
        catalog = []
        db = _DB()
        with patch("videl.utils.command_catalog.commands", return_value=catalog):
            custom_commands.save(db, -100, "welcome_note", "Hello {name}")
            custom_commands.save(db, -200, "welcome_note", "Different group")
            custom_commands.save(db, -100, "welcome_note", "Updated {chat}")
        self.assertEqual(custom_commands.list_for(db, -100), [{"name": "welcome_note", "response": "Updated {chat}", "cooldown_seconds": 0}])
        self.assertEqual(custom_commands.list_for(db, -200), [{"name": "welcome_note", "response": "Different group", "cooldown_seconds": 0}])
        custom_commands.delete(db, -100, "welcome_note")
        self.assertEqual(custom_commands.list_for(db, -100), [])
        self.assertEqual(len(custom_commands.list_for(db, -200)), 1)
