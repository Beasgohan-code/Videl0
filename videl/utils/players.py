"""Arcade identities and ratings, keyed by the Telegram id Telegram signed.

A player is created the first time they open the arcade. There is no password
and no email; the Mini App signature is the whole account. The record holds
only what Telegram published to this bot, never a phone number.
"""
from __future__ import annotations

from datetime import datetime, timezone

START_RATING = 1200
PROVISIONAL_GAMES = 10


def _db():
    from videl.utils.db import get_db
    return get_db()


def collection():
    database = _db()
    return None if database is None else database["players"]


def _now():
    return datetime.now(timezone.utc)


def upsert(user):
    """Create or refresh one player from verified Telegram data."""
    col = collection()
    if col is None:
        raise RuntimeError("Database unavailable")
    stamp = _now()
    fields = {"name": str(user.get("name") or "Player")[:64],
              "username": (str(user.get("username"))[:32] if user.get("username") else None),
              "photo_url": (str(user.get("photo_url"))[:512] if user.get("photo_url") else None),
              "last_seen": stamp}
    col.update_one({"_id": int(user["id"])},
                   {"$set": fields,
                    "$setOnInsert": {"created_at": stamp, "dm_ok": False, "stats": {}}},
                   upsert=True)
    return get(int(user["id"]))


def get(user_id):
    col = collection()
    if col is None:
        return None
    return col.find_one({"_id": int(user_id)})


def touch(user_id, *, dm_ok=None):
    col = collection()
    if col is None:
        return False
    changes = {"last_seen": _now()}
    if dm_ok is not None:
        changes["dm_ok"] = bool(dm_ok)
    col.update_one({"_id": int(user_id)}, {"$set": changes})
    return True


def public(doc):
    if not doc:
        return None
    return {"id": int(doc["_id"]), "name": doc.get("name") or "Player",
            "username": doc.get("username"), "photo_url": doc.get("photo_url"),
            "stats": _stats(doc)}


def _stats(doc):
    stats = doc.get("stats") or {}
    return {key: {"wins": int((value or {}).get("wins", 0)),
                  "losses": int((value or {}).get("losses", 0)),
                  "draws": int((value or {}).get("draws", 0)),
                  "rating": int((value or {}).get("rating", START_RATING)),
                  "games": int((value or {}).get("games", 0))}
            for key, value in stats.items()}


def expected_score(rating, opponent):
    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def record(game, winner_id, loser_id, *, draw=False):
    """Update both ratings and both records for one finished two-player game.

    Ratings are only for the two-player games. A four-player Ludo room awards
    a win but no rating, because an Elo number computed from a multiplayer
    finish order is not comparable with a duel.
    """
    col = collection()
    if col is None:
        return None
    game = str(game or "")
    if game not in {"connect4", "reversi", "tictactoe"}:
        for user_id, won in ((winner_id, not draw), (loser_id, False)):
            _bump(col, user_id, game, won=won, draw=draw, rated=False)
        return None
    first, second = get(winner_id), get(loser_id)
    if not first or not second:
        return None
    a = _stats(first).get(game, {"rating": START_RATING, "games": 0})
    b = _stats(second).get(game, {"rating": START_RATING, "games": 0})
    score = 0.5 if draw else 1.0
    expected = expected_score(a.get("rating", START_RATING), b.get("rating", START_RATING))
    k_first = 32 if int(a.get("games", 0)) < PROVISIONAL_GAMES else 16
    k_second = 32 if int(b.get("games", 0)) < PROVISIONAL_GAMES else 16
    delta_first = round(k_first * (score - expected))
    delta_second = round(k_second * ((1 - score) - (1 - expected)))
    _bump(col, winner_id, game, won=not draw, draw=draw, rated=True,
          rating=max(100, int(a.get("rating", START_RATING)) + delta_first))
    _bump(col, loser_id, game, won=False, draw=draw, rated=True,
          rating=max(100, int(b.get("rating", START_RATING)) + delta_second))
    return {"winner": delta_first, "loser": delta_second}


def _bump(col, user_id, game, *, won, draw, rated, rating=None):
    path = f"stats.{game}"
    # Zeros are written on purpose: a record with only a "wins" field is
    # confusing to read and forces every caller to guess the missing keys.
    inc = {f"{path}.wins": 1 if won and not draw else 0,
           f"{path}.losses": 1 if not won and not draw else 0,
           f"{path}.draws": 1 if draw else 0,
           f"{path}.games": 1}
    change = {"$inc": inc}
    if rated and rating is not None:
        change.setdefault("$set", {})[f"{path}.rating"] = int(rating)
    if not change:
        return
    try:
        col.update_one({"_id": int(user_id)}, change)
    except Exception:
        pass


def leaderboard(game, limit=10):
    col = collection()
    if col is None:
        return []
    key = f"stats.{game}.rating"
    rows = col.find({key: {"$exists": True}}).sort(key, -1).limit(max(1, min(int(limit), 50)))
    return [{"id": int(doc["_id"]), "name": doc.get("name") or "Player",
             "rating": int((doc.get("stats") or {}).get(game, {}).get("rating", START_RATING)),
             "games": int((doc.get("stats") or {}).get(game, {}).get("games", 0))}
            for doc in rows]
