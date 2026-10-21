"""Rooms, turns, chat and timeouts for the public arcade.

The store is the only writer. These tests pin the two things that make it safe:
a move belongs to exactly one seat and exactly one version, and a room that
nobody is watching still resolves.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import mongomock

from videl.games import store
from videl.games.registry import GameError
from videl.utils import players

UTC = timezone.utc


class ArcadeRoomTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.patch = patch("videl.utils.db.get_db", lambda: self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db["served_chats"].insert_one({"_id": -1001})
        store._LAST_CHAT.clear()
        store._LAST_SIGNAL.clear()
        players.upsert({"id": 1, "name": "Ada"})
        players.upsert({"id": 2, "name": "Grace"})

    def joined(self, game="connect4", seats=None, second=2, visibility="private"):
        room = store.create(1, "Ada", game, seat_count=seats, visibility=visibility)
        store.join(room["code"], second, "Grace")
        return room["code"]

    def row(self, code):
        return self.db["game_rooms"].find_one({"_id": code})

    # ── lifecycle ────────────────────────────────────────────────────────────
    def test_a_new_room_seats_its_host_and_waits(self):
        room = store.create(1, "Ada", "connect4")
        # The panel draws its clock ring from this, so the view must carry it.
        self.assertEqual(room["turn_seconds"], 60)
        self.assertEqual(len(room["code"]), 6)
        self.assertTrue(room["code"].isalnum())
        self.assertEqual(room["status"], "open")
        self.assertEqual(room["seats"][0]["user"], 1)
        self.assertTrue(room["you"]["is_host"])
        self.assertEqual(room["legal"], [], "a room that has not started has no moves")

    def test_the_second_player_starts_the_room(self):
        code = self.joined()
        self.assertEqual(self.row(code)["status"], "playing")
        self.assertIsNotNone(self.row(code)["deadline_at"])

    def test_presence_polls_do_not_write_on_every_request(self):
        code = self.joined()
        before = self.row(code)["seats"][0]["seen_at"]
        store.touch(code, 1)
        store.touch(code, 1)
        self.assertEqual(self.row(code)["seats"][0]["seen_at"], before,
                         "a two-second poll must not become a write per poll")
        self.assertEqual(self.row(code)["version"], 1,
                         "presence never bumps the move version")

    def test_a_full_room_refuses_a_third_player(self):
        code = self.joined()
        with self.assertRaises(GameError) as caught:
            store.join(code, 3, "Linus")
        self.assertEqual(caught.exception.status, 409)

    def test_only_the_host_can_start_early(self):
        room = store.create(1, "Ada", "ludo", seat_count=4)
        store.join(room["code"], 2, "Grace")
        with self.assertRaises(GameError):
            store.start(room["code"], 2)
        started = store.start(room["code"], 1)
        self.assertEqual(started["status"], "playing")

    def test_ludo_takes_three_or_four(self):
        with self.assertRaises(GameError):
            store.create(1, "Ada", "ludo", seat_count=5)
        room = store.create(1, "Ada", "ludo", seat_count=3)
        self.assertEqual(room["seat_count"], 3)
        self.assertEqual(len(room["state"]["starts"]), 3)

    def test_an_unknown_game_is_refused(self):
        with self.assertRaises(GameError):
            store.create(1, "Ada", "poker")

    # ── turns ────────────────────────────────────────────────────────────────
    def test_a_move_belongs_to_the_player_whose_turn_it_is(self):
        code = self.joined()
        moved = store.move(code, 1, {"column": 0})
        self.assertEqual(moved["state"]["board"][35], 1)
        self.assertEqual(moved["turn"], 1)
        with self.assertRaises(GameError) as caught:
            store.move(code, 1, {"column": 1})
        self.assertEqual(caught.exception.status, 409)
        store.move(code, 2, {"column": 1})
        self.assertEqual(self.row(code)["version"], 3, "two moves on top of the join")

    def test_a_stale_version_is_refused_rather_than_merged(self):
        code = self.joined()
        doc = self.row(code)
        stale = Mock()
        stale.find_one.return_value = doc
        stale.update_one.return_value = Mock(modified_count=0)
        with patch.object(store, "rooms", return_value=stale):
            with self.assertRaises(GameError) as caught:
                store.move(code, 1, {"column": 0})
        self.assertEqual(caught.exception.status, 409)
        self.assertIn("refresh", str(caught.exception))

    def test_a_legal_move_is_not_offered_to_the_other_seat(self):
        code = self.joined()
        self.assertTrue(store.timeline(code, 1)["room"]["legal"])
        self.assertEqual(store.timeline(code, 2)["room"]["legal"], [])

    def test_an_outsider_cannot_move_or_read_a_private_room(self):
        code = self.joined()
        for attempt in (lambda: store.move(code, 3, {"column": 0}),
                        lambda: store.timeline(code, 3)):
            with self.assertRaises(GameError) as caught:
                attempt()
            self.assertEqual(caught.exception.status, 403)

    def test_a_public_room_can_be_watched_but_not_played(self):
        code = self.joined(visibility="public")
        seen = store.timeline(code, 3)
        self.assertEqual(seen["room"]["code"], code)
        self.assertIsNone(seen["room"]["you"]["seat"])
        self.assertEqual(seen["room"]["legal"], [], "a spectator gets no move hints")
        self.assertIn("board", seen["room"]["state"])
        with self.assertRaises(GameError) as caught:
            store.move(code, 3, {"column": 0})
        self.assertEqual(caught.exception.status, 403)

    # ── timeouts ─────────────────────────────────────────────────────────────
    def test_a_missed_turn_is_played_for_the_absent_player(self):
        code = self.joined()
        self.db["game_rooms"].update_one({"_id": code}, {
            "$set": {"deadline_at": datetime.now(UTC) - timedelta(seconds=5)}})
        before = self.row(code)["version"]
        room = store.timeline(code, 2)["room"]
        self.assertEqual(room["state"]["board"][35], 1, "a move was played")
        self.assertEqual(self.row(code)["version"], before + 1)
        self.assertGreater(self.row(code)["deadline_at"].replace(tzinfo=UTC), datetime.now(UTC))

    def test_three_missed_turns_forfeit_the_game(self):
        code = self.joined()
        self.db["game_rooms"].update_one({"_id": code}, {"$set": {
            "timeouts": [2, 0], "state.turn": 0,
            "deadline_at": datetime.now(UTC) - timedelta(seconds=5)}})
        room = store.timeline(code, 2)["room"]
        self.assertEqual(room["status"], "done")
        self.assertEqual(room["winner"], 1, "the seat that kept timing out loses")

    # ── chat ─────────────────────────────────────────────────────────────────
    def test_chat_is_ordered_with_moves_in_one_cursor(self):
        code = self.joined()
        first = store.chat(code, 1, "good luck")
        store.move(code, 1, {"column": 0})
        second = store.chat(code, 2, "you too")
        self.assertLess(first["seq"], second["seq"])
        feed = store.timeline(code, 1, after=first["seq"])
        kinds = [event["kind"] for event in feed["events"]]
        self.assertIn("move", kinds)
        self.assertIn("chat", kinds)
        self.assertTrue(all(event["seq"] > first["seq"] for event in feed["events"]))

    def test_chat_has_a_length_limit_and_a_rate_limit(self):
        code = self.joined()
        with self.assertRaises(GameError) as caught:
            store.chat(code, 1, "x" * 401)
        self.assertIn("400", str(caught.exception))
        with self.assertRaises(GameError) as caught:
            store.chat(code, 1, "first")
            store.chat(code, 1, "second")
        self.assertEqual(caught.exception.status, 429)

    def test_control_characters_are_stripped_from_chat(self):
        code = self.joined()
        store.chat(code, 1, "hello\x00\x07 there")
        latest = self.db["game_events"].find({"room": code, "kind": "chat"}).sort("seq", -1)[0]
        self.assertEqual(latest["text"], "hello there")

    # ── rating and rematch ───────────────────────────────────────────────────
    def test_a_finished_game_moves_both_ratings_once(self):
        code = self.joined("tictactoe")
        for seat, cell in ((1, 0), (2, 1), (1, 4), (2, 2), (1, 8)):
            store.move(code, seat, {"cell": cell})
        room = store.timeline(code, 1)["room"]
        self.assertEqual(room["winner"], 0)
        ada = players.get(1)["stats"]["tictactoe"]
        grace = players.get(2)["stats"]["tictactoe"]
        self.assertEqual((ada["wins"], ada["losses"]), (1, 0))
        self.assertEqual((grace["wins"], grace["losses"]), (0, 1))
        self.assertGreater(ada["rating"], 1200)
        self.assertLess(grace["rating"], 1200)
        # Reading the room again must not award a second win.
        store.timeline(code, 1)
        self.assertEqual(players.get(1)["stats"]["tictactoe"]["games"], 1)

    def test_rematch_reuses_the_players_not_the_room(self):
        code = self.joined("tictactoe")
        for seat, cell in ((1, 0), (2, 1), (1, 4), (2, 2), (1, 8)):
            store.move(code, seat, {"cell": cell})
        fresh = store.rematch(code, 1)
        self.assertNotEqual(fresh["code"], code)
        self.assertEqual(fresh["status"], "playing")
        self.assertEqual({member["user"] for member in fresh["seats"]}, {1, 2})

    def test_a_public_room_is_listed_and_a_private_one_is_not(self):
        store.create(1, "Ada", "connect4", visibility="public")
        private = store.create(1, "Ada", "reversi")
        lobby = store.lobby(2)
        codes = [room["code"] for room in lobby["public"]]
        self.assertEqual(len(codes), 1)
        self.assertNotIn(private["code"], codes)
        self.assertEqual(private["visibility"], "private")

    def test_a_room_bound_to_a_chat_remembers_it(self):
        room = store.create(1, "Ada", "connect4", chat_id=-1001)
        self.assertEqual(room["chat_id"], -1001)

    # ── voice ────────────────────────────────────────────────────────────────
    def test_a_voice_signal_reaches_only_the_seat_it_names(self):
        code = self.joined()
        store.start(code, 1)
        result = store.act(code, 1, {"action": "rtc", "kind": "offer", "to": 2,
                                     "data": {"sdp": "v=0", "type": "offer"}})
        self.assertTrue(result["ok"])
        row = self.db["game_events"].find_one({"room": code, "kind": "rtc"})
        payload = json.loads(row["text"])
        self.assertEqual(payload["to"], 2)
        self.assertEqual(payload["kind"], "offer")
        self.assertEqual(payload["data"]["sdp"], "v=0")

        feed = store.timeline(code, 2, 0)
        kinds = {event["kind"] for event in feed["events"]}
        self.assertIn("rtc", kinds, "voice arrives on the stream the room already polls")

    def test_voice_refuses_a_signal_to_a_stranger_or_a_made_up_kind(self):
        code = self.joined()
        store.start(code, 1)
        with self.assertRaises(GameError) as caught:
            store.act(code, 1, {"action": "rtc", "kind": "offer", "to": 99, "data": {}})
        self.assertEqual(caught.exception.status, 403)
        with self.assertRaises(GameError):
            store.act(code, 1, {"action": "rtc", "kind": "sing", "to": 2, "data": {}})
        with self.assertRaises(GameError):
            store.act(code, 1, {"action": "rtc", "kind": "offer", "to": 2, "data": []})
        with self.assertRaises(GameError):
            store.act(code, 1, {"action": "rtc", "kind": "offer", "to": 1, "data": {}})

    def test_voice_needs_a_seat_and_cannot_carry_a_huge_payload(self):
        code = self.joined()
        store.start(code, 1)
        with self.assertRaises(GameError) as caught:
            store.act(code, 3, {"action": "rtc", "kind": "ice", "to": 1, "data": {}})
        self.assertIn(caught.exception.status, (403, 400))
        with self.assertRaises(GameError) as huge:
            store.act(code, 1, {"action": "rtc", "kind": "ice", "to": 2,
                                "data": {"candidate": "x" * 4000}})
        self.assertEqual(huge.exception.status, 413)

    # ── ending on purpose ────────────────────────────────────────────────────
    def test_resigning_hands_the_game_to_the_other_seat(self):
        code = self.joined("chess")
        done = store.act(code, 2, {"action": "resign"})
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["winner"], 0)
        self.assertEqual(done["end_reason"], "resign")
        self.assertIsNone(done["deadline_at"], "a finished game has no clock")
        events = store.timeline(code, 1)["events"]
        self.assertTrue(any("resigned" in (event.get("text") or "") for event in events))

    def test_a_resigned_room_refuses_further_moves(self):
        code = self.joined("chess")
        store.act(code, 1, {"action": "resign"})
        with self.assertRaises(GameError) as caught:
            store.act(code, 2, {"action": "resign"})
        self.assertEqual(caught.exception.status, 409)

    def test_only_a_seated_player_can_resign(self):
        code = self.joined("chess")
        with self.assertRaises(GameError):
            store.act(code, 9, {"action": "resign"})

    def test_a_draw_needs_both_seats(self):
        code = self.joined("chess")
        offered = store.act(code, 1, {"action": "draw"})
        self.assertEqual(offered["status"], "playing", "an offer is not an ending")
        self.assertEqual(offered["draw_offer"], 0)
        with self.assertRaises(GameError):
            # One seat cannot stack offers on itself.
            store.act(code, 1, {"action": "draw"})
        drawn = store.act(code, 2, {"action": "draw", "accept": True})
        self.assertEqual(drawn["status"], "done")
        self.assertEqual(drawn["winner"], "draw")
        self.assertEqual(drawn["end_reason"], "agreement")
        self.assertIsNone(drawn["draw_offer"])

    def test_declining_a_draw_clears_the_table(self):
        code = self.joined("chess")
        store.act(code, 1, {"action": "draw"})
        answer = store.act(code, 2, {"action": "draw", "accept": False})
        self.assertEqual(answer["status"], "playing")
        self.assertIsNone(answer["draw_offer"])
        events = store.timeline(code, 1)["events"]
        self.assertTrue(any("declined" in (event.get("text") or "") for event in events))

    def test_accepting_when_nothing_is_offered_is_refused(self):
        code = self.joined("chess")
        with self.assertRaises(GameError):
            store.act(code, 2, {"action": "draw", "accept": True})

    def test_a_four_seat_table_cannot_resign_or_draw(self):
        room = store.create(1, "Ada", "ludo", seat_count=4)
        store.join(room["code"], 2, "Grace")
        store.start(room["code"], 1)
        for payload in ({"action": "resign"}, {"action": "draw"}):
            with self.assertRaises(GameError) as caught:
                store.act(room["code"], 1, payload)
            self.assertEqual(caught.exception.status, 409)

    # ── voice presence ───────────────────────────────────────────────────────
    def test_voice_presence_is_a_heartbeat_not_a_flag(self):
        code = self.joined("chess")
        self.assertEqual(store.view(self.row(code), 1)["voice"], [])
        store.act(code, 1, {"action": "voice", "on": True})
        store.act(code, 2, {"action": "voice", "on": True})
        # The second seat sees the first one without polling anything new.
        self.assertEqual(sorted(store.view(self.row(code), 2)["voice"]), [1, 2])
        store.act(code, 2, {"action": "voice", "on": False})
        self.assertEqual(store.view(self.row(code), 1)["voice"], [1])

    def test_a_stale_heartbeat_leaves_the_call_on_its_own(self):
        code = self.joined("chess")
        store.act(code, 1, {"action": "voice", "on": True})
        stale = datetime.now(UTC) - timedelta(seconds=store.VOICE_WINDOW + 5)
        self.db["game_rooms"].update_one({"_id": code},
                                         {"$set": {"voice": {"0": stale}}})
        self.assertEqual(store.view(self.row(code), 1)["voice"], [],
                         "a sleeping phone must not haunt the call")

    def test_voice_presence_never_bumps_the_move_version(self):
        code = self.joined("chess")
        before = self.row(code)["version"]
        store.act(code, 1, {"action": "voice", "on": True})
        store.act(code, 1, {"action": "voice", "on": True})
        self.assertEqual(self.row(code)["version"], before,
                         "a heartbeat is not a move and must not invalidate one")

    def test_only_a_seated_player_can_join_the_call(self):
        code = self.joined("chess")
        with self.assertRaises(GameError):
            store.act(code, 99, {"action": "voice", "on": True})

if __name__ == "__main__":
    unittest.main()
