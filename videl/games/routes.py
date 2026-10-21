"""Internal arcade API. The panel reaches it through its own authenticated proxy.

Every route requires the shared internal secret *and* a signed actor assertion,
so the backend never has to trust a user id chosen by a browser.
"""
from flask import jsonify, request

from videl.api.actor import ActorError, require_actor
from videl.games import GAMES, store
from videl.games.registry import GameError
from videl.utils import players
from videl.utils.chat_admins import check as admin_check
from videl.utils.db import get_db


def _answer(error):
    return jsonify({"ok": False, "error": str(error)}), getattr(error, "status", 400)


def _player(actor):
    doc = players.get(actor)
    if doc is None:
        raise GameError("Open the arcade once to create your player", 401)
    return doc


def register_arcade_routes(app, authorized, api, secret):
    def actor():
        # Read at request time: a rotated secret must not need a restart, and a
        # test can install its own without re-importing the application.
        return require_actor(secret() if callable(secret) else secret)

    @app.route("/internal/arcade", methods=["GET", "POST"])
    def arcade_lobby():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            if request.method == "GET":
                players.touch(user)
                payload = store.lobby(user)
                payload["ok"] = True
                payload["me"] = players.public(players.get(user))
                payload["leaderboards"] = {
                    game.key: players.leaderboard(game.key, 5)
                    for game in GAMES.values() if game.seats == (2,)
                }
                return jsonify(payload)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise GameError("A JSON object is required")
            chat_id = body.get("chat_id")
            if chat_id not in (None, ""):
                # A room may only be bound to a group the actor really
                # administers; otherwise the bot would post into a stranger's
                # group on request.
                try:
                    chat_id = int(chat_id)
                except (TypeError, ValueError):
                    raise GameError("Choose a group you administer") from None
                if not admin_check(get_db(), api, chat_id, user)["admin"]:
                    raise GameError("You are not an administrator of that group", 403)
            else:
                chat_id = None
            doc = _player(user)
            room = store.create(user, doc.get("name"), body.get("game"),
                                seat_count=body.get("seats"),
                                visibility=body.get("visibility", "private"),
                                chat_id=chat_id, title=body.get("title"))
            return jsonify({"ok": True, "room": room})
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "The arcade is unavailable; no game was changed"}), 503

    @app.route("/internal/arcade/join", methods=["POST"])
    def arcade_join():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise GameError("A JSON object is required")
            doc = _player(user)
            room = store.join(str(body.get("code") or ""), user, doc.get("name"))
            return jsonify({"ok": True, "room": room})
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "The arcade is unavailable; nothing joined"}), 503

    @app.route("/internal/arcade/room/<code>", methods=["GET", "POST"])
    def arcade_room(code):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            if request.method == "GET":
                try:
                    after = int(request.args.get("after", "0"))
                except (TypeError, ValueError):
                    raise GameError("after must be a number") from None
                payload = store.timeline(code, user, after)
                payload["ok"] = True
                return jsonify(payload)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise GameError("A JSON object is required")
            if len(str(body.get("text") or "")) > 600:
                raise GameError("That message is too long")
            result = store.act(code, user, body)
            if isinstance(result, dict) and "ok" not in result:
                result = {"ok": True, "room": result}
            return jsonify(result)
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "The room is unavailable; refresh before moving"}), 503

    @app.route("/internal/arcade/clip/<clip_id>", methods=["GET"])
    def arcade_clip(clip_id):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            return jsonify(store.clip(clip_id, actor()))
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "That voice note is unavailable"}), 503

    @app.route("/internal/arcade/me", methods=["GET"])
    def arcade_me():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            players.touch(user)
            return jsonify({"ok": True, "me": players.public(players.get(user))})
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "Your player record is unavailable"}), 503
