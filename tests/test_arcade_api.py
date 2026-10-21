"""The arcade over HTTP: the same rules, reached the way the panel reaches them.

The store tests prove the engine; these prove the door. Every route must refuse
a request without the internal secret or without a signed actor, and must never
let a caller name someone else.
"""
import importlib
import time
import unittest
from unittest.mock import patch

import mongomock

from videl.games import store
from videl.utils import players
from videl.utils.telegram_auth import sign_actor

SECRET = "offline-secret"


class ArcadeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def setUp(self):
        db = mongomock.MongoClient().videl
        self.db = db
        patcher = patch.multiple(self.api.config, WEBAPP_SECRET=SECRET, BOT_TOKEN="1:token")
        patcher.start()
        self.addCleanup(patcher.stop)
        dbpatcher = patch("videl.utils.db.get_db", lambda: db)
        dbpatcher.start()
        self.addCleanup(dbpatcher.stop)
        for user, name in ((1, "Ada"), (2, "Grace"), (3, "Linus")):
            players.upsert({"id": user, "name": name})
        self.db["served_chats"].insert_one({"_id": -1001})
        store._LAST_CHAT.clear()

    def headers(self, user, *, secret=SECRET, ttl=50):
        assertion = sign_actor(user, SECRET, expires=int(time.time()) + ttl)
        return {"X-Videl-Internal": secret, "X-Videl-Actor": assertion["actor"],
                "X-Videl-Actor-Exp": str(assertion["expires"]),
                "X-Videl-Actor-Sig": assertion["signature"]}

    def room(self, user=1, game="connect4", seats=None, **extra):
        body = {"game": game, "seats": seats, **extra}
        response = self.client.post("/internal/arcade", headers=self.headers(user), json=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["room"]

    # ── the door ─────────────────────────────────────────────────────────────
    def test_every_route_needs_the_internal_secret(self):
        for path in ("/internal/arcade", "/internal/arcade/join"):
            response = self.client.post(path, json={})
            self.assertEqual(response.status_code, 403, path)

    def test_an_unsigned_actor_is_refused(self):
        response = self.client.get("/internal/arcade",
                                   headers={"X-Videl-Internal": SECRET})
        self.assertEqual(response.status_code, 401)

    def test_an_actor_cannot_be_renamed(self):
        headers = self.headers(1)
        headers["X-Videl-Actor"] = "2"
        self.assertEqual(self.client.get("/internal/arcade", headers=headers).status_code, 401)

    def test_an_expired_actor_is_refused(self):
        headers = self.headers(1, ttl=-120)
        self.assertEqual(self.client.get("/internal/arcade", headers=headers).status_code, 401)

    # ── the lobby ────────────────────────────────────────────────────────────
    def test_the_lobby_lists_games_and_only_public_rooms(self):
        self.room(1, visibility="public")
        self.room(1, game="ludo", seats=4, visibility="private")
        body = self.client.get("/internal/arcade", headers=self.headers(2)).get_json()
        self.assertEqual(body["ok"], True)
        self.assertEqual({game["key"] for game in body["games"]},
                         {"checkers", "connect4", "reversi", "tictactoe", "ludo"})
        self.assertEqual(len(body["public"]), 1)
        self.assertEqual(body["public"][0]["game"], "connect4")
        self.assertEqual(body["me"]["id"], 2)

    def test_a_group_binding_is_refused_without_admin_rights(self):
        response = self.client.post("/internal/arcade",
                                    headers=self.headers(1),
                                    json={"game": "connect4", "chat_id": -1001})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.db["game_rooms"].count_documents({}))

    def test_an_unknown_game_is_a_400_not_a_crash(self):
        response = self.client.post("/internal/arcade", headers=self.headers(1),
                                    json={"game": "chess"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    # ── playing ──────────────────────────────────────────────────────────────
    def test_two_players_can_finish_a_tictactoe_game_over_http(self):
        room = self.room(1, game="tictactoe")
        code = room["code"]
        joined = self.client.post("/internal/arcade/join", headers=self.headers(2),
                                  json={"code": code})
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.get_json()["room"]["status"], "playing")

        # (who moves, square): Ada takes the top row while Grace blocks.
        moves = [(1, 0), (2, 1), (1, 4), (2, 3), (1, 8)]
        for user, cell in moves:
            response = self.client.post(f"/internal/arcade/room/{code}",
                                        headers=self.headers(user),
                                        json={"action": "move", "move": {"cell": cell}})
            self.assertEqual(response.status_code, 200, response.get_json())

        final = self.client.get(f"/internal/arcade/room/{code}?after=0",
                                headers=self.headers(1)).get_json()
        self.assertEqual(final["room"]["status"], "done")
        self.assertEqual(final["room"]["winner"], 0)
        self.assertEqual(final["room"]["legal"], [])

    def test_a_move_from_the_wrong_account_is_refused(self):
        room = self.room(1, game="tictactoe")
        code = room["code"]
        self.client.post("/internal/arcade/join", headers=self.headers(2), json={"code": code})
        response = self.client.post(f"/internal/arcade/room/{code}",
                                    headers=self.headers(2),
                                    json={"action": "move", "move": {"cell": 4}})
        self.assertEqual(response.status_code, 409)
        self.assertIn("turn", response.get_json()["error"].lower())

    def test_an_outsider_cannot_read_a_private_room(self):
        code = self.room(1)["code"]
        response = self.client.get(f"/internal/arcade/room/{code}", headers=self.headers(3))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("state", response.get_json())

    def test_a_shared_public_link_is_watchable_before_joining(self):
        room = self.room(1, visibility="public")
        code = room["code"]
        self.client.post("/internal/arcade/join", headers=self.headers(2), json={"code": code})
        watched = self.client.get(f"/internal/arcade/room/{code}", headers=self.headers(3))
        self.assertEqual(watched.status_code, 200)
        body = watched.get_json()
        self.assertIsNone(body["room"]["you"]["seat"])
        self.assertEqual(body["room"]["legal"], [])
        refused = self.client.post(f"/internal/arcade/room/{code}", headers=self.headers(3),
                                   json={"action": "move", "move": {"column": 3}})
        self.assertEqual(refused.status_code, 403)

    def test_a_bad_room_code_is_a_404(self):
        response = self.client.get("/internal/arcade/room/ZZZZZZ", headers=self.headers(1))
        self.assertEqual(response.status_code, 404)

    def test_chat_and_the_timeline_share_one_cursor(self):
        room = self.room(1, game="tictactoe")
        code = room["code"]
        self.client.post("/internal/arcade/join", headers=self.headers(2), json={"code": code})
        sent = self.client.post(f"/internal/arcade/room/{code}", headers=self.headers(1),
                                json={"action": "chat", "text": "good luck"})
        self.assertEqual(sent.status_code, 200)
        body = self.client.get(f"/internal/arcade/room/{code}?after=0",
                               headers=self.headers(2)).get_json()
        kinds = [event["kind"] for event in body["events"]]
        self.assertIn("chat", kinds)
        cursor = body["room"]["seq"]
        after = self.client.get(f"/internal/arcade/room/{code}?after={cursor}",
                                headers=self.headers(2)).get_json()
        self.assertEqual(after["events"], [], "a caught-up cursor returns no duplicates")

    def test_a_long_message_is_refused_before_it_is_stored(self):
        room = self.room(1)
        code = room["code"]
        response = self.client.post(f"/internal/arcade/room/{code}", headers=self.headers(1),
                                    json={"action": "chat", "text": "x" * 700})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.db["game_events"].count_documents({"kind": "chat"}))


if __name__ == "__main__":
    unittest.main()
