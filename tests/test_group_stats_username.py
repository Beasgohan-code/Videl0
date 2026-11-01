import unittest
from types import SimpleNamespace
from unittest.mock import patch

from videl.plugins import group


class _Collection:
    def count_documents(self, _query):
        return 3


class _Database:
    def __getitem__(self, _name):
        return _Collection()


class GroupStatsUsernameTests(unittest.IsolatedAsyncioTestCase):
    async def test_stats_prefers_live_telegram_username_over_stale_config(self):
        client = SimpleNamespace(me=SimpleNamespace(username="Videlapp"))
        context = SimpleNamespace(client=client, owner=False)
        with patch.object(group.base, "db", return_value=_Database()), \
             patch.object(group.config, "BOT_USERNAME", "ZoroOPappbot"):
            result = await group.stats(context)
        self.assertIn("@Videlapp", result.html)
        self.assertNotIn("@ZoroOPappbot", result.html)

    async def test_stats_falls_back_to_current_name_if_live_lookup_fails(self):
        client = SimpleNamespace(me=None)
        async def get_me():
            raise RuntimeError("Telegram unavailable")
        client.get_me = get_me
        context = SimpleNamespace(client=client, owner=False)
        with patch.object(group.base, "db", return_value=_Database()), \
             patch.object(group.config, "BOT_USERNAME", "ZoroOPappbot"):
            result = await group.stats(context)
        self.assertIn("@Videlapp", result.html)
        self.assertNotIn("@ZoroOPappbot", result.html)

    async def test_stats_resolves_live_username_when_client_me_is_unavailable(self):
        client = SimpleNamespace(me=None)
        async def get_me():
            return SimpleNamespace(username="Videlapp")
        client.get_me = get_me
        context = SimpleNamespace(client=client, owner=False)
        with patch.object(group.base, "db", return_value=_Database()), \
             patch.object(group.config, "BOT_USERNAME", "ZoroOPappbot"):
            result = await group.stats(context)
        self.assertIn("@Videlapp", result.html)
        self.assertNotIn("@ZoroOPappbot", result.html)


if __name__ == "__main__":
    unittest.main()
