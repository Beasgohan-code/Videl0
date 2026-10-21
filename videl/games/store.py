"""Mongo persistence for arcade rooms.

Every mutation is a compare-and-set on ``version``. That single rule gives the
whole feature its safety: two tabs cannot both move, a replayed request cannot
move twice, and a chat message that arrives during a move gets a sequence
number that is still unique.

Rooms are cheap: one document per game, one event per move or message, with a
TTL on the events. Nothing here runs on a timer; deadlines are settled lazily
by whoever reads the room next, and by a sweep in the watchdog for rooms nobody
is watching.
"""
from __future__ import annotations

import json
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from . import GAMES
from .registry import GameError

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EVENT_RETENTION = timedelta(days=7)
PUBLIC_PAGE = 30
CODES_TRIED = 6
MAX_CHAT = 400
#: A WebRTC session description is much longer than a message and is written
#: by the server, not typed by a person, so it gets its own ceiling.
MAX_SIGNAL = 3000
TIMEOUTS_BEFORE_FORFEIT = 3
CHAT_WINDOW = (20, 60)          # 20 messages per minute
CHAT_GAP = 1.0                  # and never faster than one per second
#: Trickled ICE candidates arrive in bursts; a peer only needs to be stopped
#: from turning the room into a message bus.
SIGNAL_WINDOW = (240, 60)
# A voice heartbeat is only believable for a moment. Longer than the poll
# interval (about 2 s) by a wide margin, short enough that closing the tab
# takes a seat out of the call instead of leaving a ghost in it.
VOICE_WINDOW = 35
SIGNAL_GAP = 0.05
_LAST_CHAT = defaultdict(deque)
_LAST_SIGNAL = defaultdict(deque)


def now():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _stamp(value):
    return _as_utc(value).isoformat() if isinstance(value, datetime) else None


def _db():
    from videl.utils.db import get_db
    database = get_db()
    if database is None:
        raise GameError("The arcade needs the database; it is reconnecting", 503)
    return database


def rooms():
    return _db()["game_rooms"]


def events():
    return _db()["game_events"]


def ensure_indexes(database=None):
    database = database or _db()
    try:
        database["game_rooms"].create_index([("visibility", 1), ("status", 1), ("updated_at", -1)])
        database["game_rooms"].create_index([("seats.user", 1), ("status", 1)])
        database["game_events"].create_index([("room", 1), ("seq", 1)], unique=True)
        database["game_events"].create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        # An index is an optimisation; the feature works without it.
        pass


def new_code():
    for _ in range(CODES_TRIED):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if rooms().find_one({"_id": code}, {"_id": 1}) is None:
            return code
    raise GameError("The arcade is busy; try again in a moment", 503)


def _game(key):
    game = GAMES.get(str(key or "").lower())
    if game is None:
        raise GameError("Choose one of the arcade games")
    return game


def _seat_of(doc, user):
    for member in doc.get("seats", []):
        if int(member.get("user", 0)) == int(user):
            return int(member["seat"])
    return None


def _member(doc, user):
    for member in doc.get("seats", []):
        if int(member.get("user", 0)) == int(user):
            return member
    return None


PRESENCE_SECONDS = 12


def _seen(code, user):
    doc = _find(code)
    stamp = now()
    for index, member in enumerate(doc.get("seats", [])):
        if int(member.get("user", 0)) == int(user):
            # Presence is not a move. Bumping the version here would let a
            # poll from one player invalidate another player's move.
            previous = _as_utc(member.get("seen_at"))
            # A two-second poll must not become a write every two seconds; the
            # panel only needs to know who is here, to the nearest few seconds.
            if previous is not None and stamp - previous < timedelta(seconds=PRESENCE_SECONDS):
                return
            rooms().update_one({"_id": code},
                               {"$set": {f"seats.{index}.seen_at": stamp}})
            return


def _require_member(doc, user):
    seat = _seat_of(doc, user)
    if seat is None:
        raise GameError("You are not seated in this room", 403)
    return seat


def _require_host(doc, user):
    if int(doc.get("host", 0)) != int(user):
        raise GameError("Only the host can do that", 403)


def view(doc, user=None):
    game = _game(doc["game"])
    seat = _seat_of(doc, user) if user is not None else None
    state = doc.get("state") or {}
    public = game.view(state, seat if seat is not None else 0)
    # Only the player whose turn it is gets move hints; a client cannot learn
    # the opponent's options a turn early.
    legal = (game.legal(state, seat)
             if (seat is not None and doc.get("status") == "playing"
                 and int(state.get("turn", 0)) == int(seat)) else [])
    return {
        "code": doc["_id"],
        "game": game.key,
        "game_name": game.name,
        "visibility": doc.get("visibility", "private"),
        "status": doc.get("status", "open"),
        "host": doc.get("host"),
        "seat_count": int(doc.get("seat_count", 2)),
        "seats": [{"user": m.get("user"), "name": m.get("name") or "Player",
                   "seat": m.get("seat"), "online": _online(m.get("seen_at"))}
                  for m in doc.get("seats", [])],
        "turn": int((doc.get("state") or {}).get("turn", 0)),
        "you": {"seat": seat, "is_host": int(doc.get("host", 0)) == int(user or 0),
                "member": seat is not None},
        "state": public,
        "legal": legal if seat is not None else [],
        "deadline_at": _stamp(doc.get("deadline_at")),
        "server_time": now().isoformat(),
        "version": int(doc.get("version", 0)),
        "seq": int(doc.get("seq", 0)),
        "winner": doc.get("winner"),
        "end_reason": doc.get("end_reason"),
        # null, or the seat whose offer is waiting for an answer.
        "draw_offer": doc.get("draw_offer"),
        # Who is in the voice call right now, as user ids. The panel draws a
        # badge from this and the dock decides whether joining is worth it.
        "voice": _voice_users(doc),
        "chat_id": doc.get("chat_id"),
        "title": doc.get("title") or "",
        # The panel draws a clock ring from this, so it must not have to guess
        # the game's turn length from a list that may be a version behind.
        "turn_seconds": game.turn_seconds,
    }


def _online(seen):
    seen = _as_utc(seen)
    return bool(seen and now() - seen < timedelta(seconds=45))


def profile_view(user, name):
    return {"id": int(user), "name": name or "Player"}


# ── room lifecycle ───────────────────────────────────────────────────────────

def create(user, name, game_key, *, seat_count=None, visibility="private", chat_id=None, title=""):
    game = _game(game_key)
    seats = int(seat_count or game.seats[0])
    if seats not in game.seats:
        raise GameError(f"{game.name} seats " + ", ".join(str(value) for value in game.seats) + " players")
    if visibility not in {"private", "public"}:
        raise GameError("Choose a private or public room")
    ensure_indexes()
    code = new_code()
    stamp = now()
    doc = {"_id": code, "game": game.key, "visibility": visibility, "host": int(user),
           "seat_count": seats, "status": "open", "turn": 0, "state": game.new(seats),
           "version": 0, "seq": 0, "timeouts": [0] * seats,
           "seats": [{"user": int(user), "name": str(name or "Player")[:40], "seat": 0,
                      "seen_at": stamp}],
           "chat_id": int(chat_id) if chat_id else None, "title": str(title or "")[:60],
           "created_at": stamp, "updated_at": stamp, "deadline_at": None}
    rooms().insert_one(doc)
    _event(code, "system", None, f"{doc['seats'][0]['name']} opened the room", seq=0)
    return view(doc, user)


def join(code, user, name):
    doc = _find(code)
    if _member(doc, user):
        _seen(code, user)
        return view(_find(code), user)
    if doc.get("status") != "open":
        raise GameError("This room has already started", 409)
    if len(doc.get("seats", [])) >= int(doc.get("seat_count", 2)):
        raise GameError("This room is full", 409)
    seat = len(doc["seats"])
    stamp = now()
    updates = {"$push": {"seats": {"user": int(user), "name": str(name or "Player")[:40],
                                   "seat": seat, "seen_at": stamp}},
               "$inc": {"version": 1}, "$set": {"updated_at": stamp}}
    started = seat + 1 >= int(doc["seat_count"])
    if started:
        updates["$set"].update({"status": "playing",
                                "deadline_at": stamp + timedelta(seconds=_game(doc["game"]).turn_seconds)})
    changed = rooms().update_one({"_id": code, "version": int(doc["version"])}, updates)
    if not changed.modified_count:
        raise GameError("The room changed while joining; try again", 409)
    _event(code, "join", int(user), f"{str(name or 'Player')[:40]} joined", seq=_next_seq(code))
    return view(_find(code), user)


def start(code, user):
    doc = _find(code)
    _require_host(doc, user)
    if doc.get("status") == "playing":
        return view(doc, user)
    if doc.get("status") != "open":
        raise GameError("This room has already finished", 409)
    if len(doc.get("seats", [])) < 2:
        raise GameError("At least two players are needed", 409)
    game = _game(doc["game"])
    stamp = now()
    changed = rooms().update_one({"_id": code, "version": int(doc["version"])}, {
        "$set": {"status": "playing", "updated_at": stamp,
                 "deadline_at": stamp + timedelta(seconds=game.turn_seconds),
                 "state.turn": 0}, "$inc": {"version": 1}})
    if not changed.modified_count:
        raise GameError("The room changed while starting; try again", 409)
    _event(code, "system", int(user), "Game started", seq=_next_seq(code))
    return view(_find(code), user)


def leave(code, user):
    doc = _find(code)
    seat = _seat_of(doc, user)
    if seat is None:
        raise GameError("You are not seated in this room", 403)
    stamp = now()
    if doc.get("status") == "playing":
        winner = _opponent(doc, seat)
        changed = rooms().update_one({"_id": code, "version": int(doc["version"])}, {
            "$set": {"status": "done", "winner": winner, "finished_at": stamp,
                     "updated_at": stamp, "end_reason": "left"}, "$inc": {"version": 1}})
        if not changed.modified_count:
            raise GameError("The room changed while leaving; try again", 409)
        _event(code, "system", int(user), "Opponent left; game over", seq=_next_seq(code))
        _finish(_find(code))
        return {"ok": True, "left": True}
    remaining = [member for member in doc["seats"] if int(member["seat"]) != int(seat)]
    for index, member in enumerate(remaining):
        member["seat"] = index
    changed = rooms().update_one({"_id": code, "version": int(doc["version"])}, {
        "$set": {"seats": remaining, "status": "open" if remaining else "abandoned",
                 "updated_at": stamp}, "$inc": {"version": 1}})
    if not changed.modified_count:
        raise GameError("The room changed while leaving; try again", 409)
    return {"ok": True, "left": True}


def kick(code, user, target):
    doc = _find(code)
    _require_host(doc, user)
    if doc.get("status") != "open":
        raise GameError("You can only remove a player before the game starts", 409)
    seat = _seat_of(doc, target)
    if seat is None or seat == 0:
        raise GameError("That player is not in this room", 404)
    remaining = [member for member in doc["seats"] if int(member["seat"]) != int(seat)]
    for index, member in enumerate(remaining):
        member["seat"] = index
    changed = rooms().update_one({"_id": code, "version": int(doc["version"])}, {
        "$set": {"seats": remaining, "updated_at": now()}, "$inc": {"version": 1}})
    if not changed.modified_count:
        raise GameError("The room changed; try again", 409)
    return view(_find(code), user)


def rematch(code, user):
    doc = _find(code)
    _require_host(doc, user)
    if doc.get("status") not in {"done", "abandoned"}:
        raise GameError("Finish the current game first", 409)
    fresh = create(user, _member(doc, user).get("name", "Player"), doc["game"],
                   seat_count=doc["seat_count"], visibility=doc.get("visibility", "private"),
                   chat_id=doc.get("chat_id"), title=doc.get("title", ""))
    for member in doc.get("seats", [])[1:]:
        try:
            join(fresh["code"], member["user"], member.get("name"))
        except GameError:
            continue
    return view(_find(fresh["code"]), user)


# ── play ─────────────────────────────────────────────────────────────────────

def act(code, user, payload):
    action = str(payload.get("action") or "move").lower()
    if action == "move":
        return move(code, user, payload.get("move") if isinstance(payload.get("move"), dict) else payload)
    if action == "start":
        return start(code, user)
    if action == "leave":
        return leave(code, user)
    if action == "kick":
        return kick(code, user, payload.get("user"))
    if action == "rematch":
        return rematch(code, user)
    if action == "resign":
        return resign(code, user)
    if action == "draw":
        return draw(code, user, bool(payload.get("accept")))
    if action == "chat":
        return chat(code, user, payload.get("text"))
    if action == "rtc":
        return rtc(code, user, payload)
    if action == "voice":
        return voice_presence(code, user, bool(payload.get("on", True)))
    if action == "seen":
        touch(code, user)
        return {"ok": True}
    raise GameError("Unknown room action")


def touch(code, user):
    _seen(code, user)


def move(code, user, move):
    settle(code)
    doc = _find(code)
    seat = _require_member(doc, user)
    if doc.get("status") != "playing":
        raise GameError("This room is not in play", 409)
    game = _game(doc["game"])
    state = game.apply(doc.get("state") or {}, seat, move or {})
    stamp = now()
    winner = game.result(state)
    timeouts = list(doc.get("timeouts") or [0] * int(doc["seat_count"]))
    timeouts[seat] = 0
    updates = {"state": state, "turn": int(state.get("turn", 0)), "timeouts": timeouts,
               "updated_at": stamp, "last_move_at": stamp}
    if winner is not None:
        updates.update({"status": "done", "winner": winner, "finished_at": stamp,
                        "deadline_at": None, "end_reason": "played"})
    else:
        updates["deadline_at"] = stamp + timedelta(seconds=game.turn_seconds)
    changed = rooms().update_one({"_id": code, "version": int(doc["version"]), "status": "playing"},
                                 {"$set": updates, "$inc": {"version": 1, "seq": 1}})
    if not changed.modified_count:
        raise GameError("The room moved without you; refresh before moving again", 409)
    fresh = _find(code)
    _event(code, "move", int(user), _describe(game, state, seat, move),
           seq=int(fresh.get("seq", 0)))
    if winner is not None:
        _finish(fresh)
    return view(fresh, user)


def voice_presence(code, user, on=True):
    """Say "I am in the call" — and keep saying it.

    Presence is a heartbeat, not a flag: the room only shows the seats whose
    last word is younger than VOICE_WINDOW, so a phone that sleeps or a tab
    that closes leaves the call without anybody having to clean up. This never
    bumps the move version — a heartbeat must not make a player's next move
    look stale.
    """
    doc = _find(code)
    seat = _require_member(doc, user)
    stamp = now()
    current = {}
    for key, value in (doc.get("voice") or {}).items():
        beat = _as_utc(value)
        if beat is not None and stamp - beat < timedelta(seconds=VOICE_WINDOW):
            current[str(key)] = value
    if on:
        # A real datetime, not an ISO string: every reader here compares
        # datetimes, and a string would silently look like "never".
        current[str(seat)] = stamp
    else:
        current.pop(str(seat), None)
    rooms().update_one({"_id": code}, {"$set": {"voice": current}})
    return {"ok": True, "voice": [int(member["user"]) for member in doc.get("seats", [])
                                  if str(member.get("seat")) in current]}


def _voice_users(doc):
    """The seats currently in the call, as user ids."""
    stamp = now()
    holding = set()
    for key, value in (doc.get("voice") or {}).items():
        beat = _as_utc(value)
        if beat is not None and stamp - beat < timedelta(seconds=VOICE_WINDOW):
            holding.add(str(key))
    return [int(member["user"]) for member in doc.get("seats", [])
            if str(member.get("seat")) in holding]


def resign(code, user):
    """Give the game away on purpose. A timed-out player already forfeits;
    this is the same ending without waiting out the clock."""
    doc = _find(code)
    seat = _require_member(doc, user)
    if doc.get("status") != "playing":
        raise GameError("This room is not in play", 409)
    if int(doc.get("seat_count", 2)) != 2:
        raise GameError("Only a two-player game can be resigned", 409)
    stamp = now()
    changed = rooms().update_one(
        {"_id": code, "version": int(doc["version"]), "status": "playing"},
        {"$set": {"status": "done", "winner": 1 - seat, "finished_at": stamp,
                  "deadline_at": None, "end_reason": "resign", "draw_offer": None},
         "$inc": {"version": 1, "seq": 1}})
    if not changed.modified_count:
        raise GameError("The room moved without you; refresh before resigning", 409)
    fresh = _find(code)
    _event(code, "system", int(user), "resigned", seq=int(fresh.get("seq", 0)))
    _finish(fresh)
    return view(fresh, user)


def draw(code, user, accept):
    """Offer a draw, or answer the one already on the table.

    An offer is not a move: the clock keeps running and the game keeps going
    until the other seat answers, so a stalling player cannot freeze a losing
    position by never replying.
    """
    doc = _find(code)
    seat = _require_member(doc, user)
    if doc.get("status") != "playing":
        raise GameError("This room is not in play", 409)
    if int(doc.get("seat_count", 2)) != 2:
        raise GameError("Draws are offered in two-player games only", 409)
    offered = doc.get("draw_offer")
    stamp = now()
    if accept and offered is not None and int(offered) != seat:
        changed = rooms().update_one(
            {"_id": code, "version": int(doc["version"]), "status": "playing"},
            {"$set": {"status": "done", "winner": "draw", "finished_at": stamp,
                      "deadline_at": None, "end_reason": "agreement",
                      "draw_offer": None},
             "$inc": {"version": 1, "seq": 1}})
        if not changed.modified_count:
            raise GameError("The room changed; try again", 409)
        fresh = _find(code)
        _event(code, "system", int(user), "agreed to a draw",
               seq=int(fresh.get("seq", 0)))
        _finish(fresh)
        return view(fresh, user)
    if offered is not None and int(offered) == seat:
        raise GameError("You already offered a draw", 409)
    if accept and offered is None:
        raise GameError("There is no draw offer to accept", 409)
    changed = rooms().update_one(
        {"_id": code, "version": int(doc["version"]), "status": "playing"},
        {"$set": {"draw_offer": None if offered is not None else seat,
                  "updated_at": stamp},
         "$inc": {"version": 1, "seq": 1}})
    if not changed.modified_count:
        raise GameError("The room changed; try again", 409)
    fresh = _find(code)
    _event(code, "system", int(user),
           "declined the draw" if offered is not None else "offered a draw",
           seq=int(fresh.get("seq", 0)))
    return view(fresh, user)


def _describe(game, state, seat, move):
    if game.key == "ludo":
        return f"moved token {int(move.get('token', 0)) + 1}"
    if game.key == "chess":
        return f"played {(state.get('last') or {}).get('san') or 'a move'}"
    if game.key == "checkers":
        last = state.get("last") or {}
        jumps = int(last.get("captures") or 0)
        if last.get("crowned"):
            return "crowned a king" if not jumps else f"crowned a king taking {jumps}"
        return f"took {jumps} piece{'s' if jumps != 1 else ''}" if jumps else "made a move"
    if game.key == "gomoku":
        cell = int(move.get("cell") or 0)
        return f"placed a stone at {chr(97 + cell % 15)}{cell // 15 + 1}"
    return "made a move"


def _finish(doc):
    """Record a rating exactly once, guarded by the room's own version write."""
    winner = doc.get("winner")
    if doc.get("recorded") or doc.get("status") != "done":
        return
    rooms().update_one({"_id": doc["_id"], "recorded": {"$ne": True}}, {"$set": {"recorded": True}})
    if winner in (None, "draw"):
        return
    seats = doc.get("seats") or []
    if len(seats) != 2:
        return
    loser = 1 - int(winner)
    try:
        from videl.utils import players
        players.record(doc["game"], int(seats[int(winner)]["user"]), int(seats[loser]["user"]))
    except Exception:
        pass


def _opponent(doc, seat):
    seats = doc.get("seats") or []
    for member in seats:
        if int(member["seat"]) != int(seat):
            return int(member["seat"])
    return None


def settle(code):
    """Apply a missed turn, at most a few at a time, whoever asks first."""
    for _ in range(3):
        doc = _find(code)
        if doc.get("status") != "playing":
            return doc
        deadline = _as_utc(doc.get("deadline_at"))
        if deadline is None or deadline > now():
            return doc
        game = _game(doc["game"])
        state = doc.get("state") or {}
        seat = int(state.get("turn", 0))
        try:
            state = game.auto(state)
        except GameError:
            return doc
        stamp = now()
        timeouts = list(doc.get("timeouts") or [0] * int(doc.get("seat_count", 2)))
        if seat < len(timeouts):
            timeouts[seat] += 1
        winner = game.result(state)
        updates = {"state": state, "turn": int(state.get("turn", 0)),
                   "timeouts": timeouts, "updated_at": stamp, "deadline_at": None}
        if winner is not None:
            updates.update({"status": "done", "winner": winner, "finished_at": stamp,
                            "end_reason": "played"})
        elif timeouts[seat] >= TIMEOUTS_BEFORE_FORFEIT and game.key != "ludo":
            updates.update({"status": "done", "winner": 1 - seat, "finished_at": stamp,
                            "end_reason": "forfeit"})
        else:
            updates["deadline_at"] = stamp + timedelta(seconds=game.turn_seconds)
        changed = rooms().update_one({"_id": code, "version": int(doc["version"]),
                                      "status": "playing"},
                                     {"$set": updates, "$inc": {"version": 1, "seq": 1}})
        if not changed.modified_count:
            continue
        fresh = _find(code)
        _event(code, "system", None,
               "Time ran out; the move was played for the absent player", seq=int(fresh.get("seq", 0)))
        if fresh.get("status") == "done":
            _finish(fresh)
        return fresh
    return _find(code)


# ── chat ─────────────────────────────────────────────────────────────────────

def chat(code, user, text):
    doc = _find(code)
    _require_member(doc, user)
    body = "".join(character for character in str(text or "") if character.isprintable() or character == " ").strip()
    if not body:
        raise GameError("Write a message first")
    if len(body) > MAX_CHAT:
        raise GameError(f"Keep messages under {MAX_CHAT} characters")
    _rate_limit(code, user)
    seq = _next_seq(code)
    _event(code, "chat", int(user), body, seq=seq)
    return {"ok": True, "seq": seq}


def rtc(code, user, payload):
    """Relay one WebRTC signal to a seated peer.

    Voice never touches the board: the media is peer-to-peer, and this is only
    the introduction — an offer, an answer, or one trickled candidate. The
    signal is addressed (`to`) so it can be dropped by everyone else, and it is
    written to the same event stream the room already polls, which is why voice
    needs no second connection.
    """
    doc = _find(code)
    _require_member(doc, user)
    kind = str(payload.get("kind") or "").lower()
    if kind not in {"offer", "answer", "ice", "bye"}:
        raise GameError("Unknown voice signal")
    try:
        target = int(payload.get("to"))
    except (TypeError, ValueError):
        raise GameError("Choose who the signal is for") from None
    if target == int(user):
        raise GameError("A signal needs a peer")
    seats = {int(member.get("user")) for member in doc.get("seats", [])}
    if target not in seats:
        raise GameError("That player is not at this table", 403)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise GameError("A signal needs a payload")
    body = json.dumps({"to": target, "kind": kind, "data": data},
                      separators=(",", ":"), sort_keys=True)
    if len(body) > MAX_SIGNAL:
        raise GameError("That signal is too large", 413)
    _signal_limit(code, user)
    seq = _next_seq(code)
    _event(code, "rtc", int(user), body, seq=seq)
    return {"ok": True, "seq": seq}


def _signal_limit(code, user):
    key = (code, int(user))
    times = _LAST_SIGNAL[key]
    stamp = datetime.now().timestamp()
    while times and stamp - times[0] > SIGNAL_WINDOW[1]:
        times.popleft()
    if times and stamp - times[-1] < SIGNAL_GAP:
        raise GameError("Slow down for a moment", 429)
    if len(times) >= SIGNAL_WINDOW[0]:
        raise GameError("Too many voice signals; try again shortly", 429)
    times.append(stamp)


def _rate_limit(code, user):
    key = (code, int(user))
    times = _LAST_CHAT[key]
    stamp = datetime.now().timestamp()
    while times and stamp - times[0] > CHAT_WINDOW[1]:
        times.popleft()
    if times and stamp - times[-1] < CHAT_GAP:
        raise GameError("Slow down for a moment", 429)
    if len(times) >= CHAT_WINDOW[0]:
        raise GameError("You have sent a lot; wait a minute", 429)
    times.append(stamp)


def _next_seq(code):
    fresh = rooms().find_one_and_update({"_id": code},
                                        {"$inc": {"seq": 1}, "$set": {"updated_at": now()}},
                                        return_document=True)
    return int((fresh or {}).get("seq", 0))


def _event(code, kind, user, text, seq=None):
    if seq is None:
        seq = _next_seq(code)
    ceiling = MAX_SIGNAL if kind == "rtc" else MAX_CHAT
    events().insert_one({"room": code, "seq": int(seq), "kind": kind,
                         "user": int(user) if user else None,
                         "text": str(text or "")[:ceiling],
                         "at": now(),
                         "expires_at": now() + EVENT_RETENTION})


def timeline(code, user, after=0):
    doc = settle(code)
    seat = _seat_of(doc, user)
    if seat is None:
        # A shared public room can be watched without taking a seat. A private
        # room's code is its invitation, so an unseated reader is refused until
        # they actually join; nothing about the board leaks either way.
        if doc.get("visibility") != "public":
            raise GameError("You are not seated in this room", 403)
        query = {"room": code, "seq": {"$gt": int(after or 0)}}
        rows = list(events().find(query).sort("seq", 1).limit(200))
        return {"room": view(doc, None),
                "events": [{"seq": int(row.get("seq", 0)), "kind": row.get("kind"),
                            "user": row.get("user"), "text": row.get("text", ""),
                            "at": _stamp(row.get("at"))} for row in rows],
                "server_time": now().isoformat()}
    touch(code, user)
    query = {"room": code, "seq": {"$gt": int(after or 0)}}
    rows = list(events().find(query).sort("seq", 1).limit(200))
    return {"room": view(doc, user),
            "events": [{"seq": int(row.get("seq", 0)), "kind": row.get("kind"),
                        "user": row.get("user"), "text": row.get("text", ""),
                        "at": _stamp(row.get("at"))} for row in rows],
            "server_time": now().isoformat()}


def lobby(user):
    ensure_indexes()
    public = list(rooms().find({"visibility": "public", "status": {"$in": ["open", "playing"]}})
                  .sort("updated_at", -1).limit(PUBLIC_PAGE))
    mine = list(rooms().find({"seats.user": int(user), "status": {"$in": ["open", "playing"]}})
                .sort("updated_at", -1).limit(20))
    return {"games": [game.describe() for game in GAMES.values()],
            "public": [_row(doc) for doc in public],
            "mine": [_row(doc) for doc in mine]}


def _row(doc):
    game = GAMES.get(doc.get("game"))
    return {"code": doc["_id"], "game": doc.get("game"),
            "game_name": game.name if game else doc.get("game"),
            "status": doc.get("status"), "visibility": doc.get("visibility"),
            "seat_count": int(doc.get("seat_count", 2)),
            "players": [member.get("name") for member in doc.get("seats", [])],
            "host": doc.get("host"), "updated_at": _stamp(doc.get("updated_at")),
            "turn_seconds": game.turn_seconds if game else 60}


def sweep(max_age_hours=24):
    """Abandon rooms nobody came back to. Called from the watchdog."""
    cutoff = now() - timedelta(hours=max_age_hours)
    open_cutoff = now() - timedelta(hours=2)
    try:
        stale = rooms().update_many({"status": "playing", "updated_at": {"$lt": cutoff}},
                                    {"$set": {"status": "abandoned", "updated_at": now(),
                                              "end_reason": "abandoned"}})
        empty = rooms().update_many({"status": "open", "updated_at": {"$lt": open_cutoff}},
                                    {"$set": {"status": "abandoned", "updated_at": now(),
                                              "end_reason": "never started"}})
        return {"ok": True, "abandoned": stale.modified_count + empty.modified_count}
    except Exception:
        return {"ok": False, "abandoned": 0}


def _find(code):
    code = str(code or "").strip().upper()
    if not 4 <= len(code) <= 8 or not all(character in CODE_ALPHABET for character in code):
        raise GameError("That room code is not valid", 404)
    doc = rooms().find_one({"_id": code})
    if doc is None:
        raise GameError("No room has that code", 404)
    return doc
