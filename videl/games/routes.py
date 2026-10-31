"""Internal arcade API. The panel reaches it through its own authenticated proxy.

Every route requires the shared internal secret *and* a signed actor assertion,
so the backend never has to trust a user id chosen by a browser.
"""
import base64

from flask import jsonify, request

from videl.api.actor import ActorError, require_actor
from videl.games import GAMES, community_events, store
from videl.games.registry import GameError
from videl.utils import avatars, players
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
        except (GameError, ActorError, community_events.EventError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "The arcade is unavailable; no game was changed"}), 503

    @app.route("/internal/arcade/event-groups", methods=["GET"])
    def arcade_event_groups():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            from videl.utils.chat_admins import my_groups
            groups = my_groups(get_db(), api, user, refresh=True, limit=25)
            return jsonify({"ok": True, "groups": groups})
        except ActorError as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "Your admin groups could not be loaded"}), 503

    @app.route("/internal/arcade/events", methods=["GET", "POST"])
    def arcade_events():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            if request.method == "GET":
                return jsonify({"ok": True, "events": community_events.list_for(user)})
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise GameError("A JSON object is required")
            try:
                chat_id = int(body.get("chat_id"))
            except (TypeError, ValueError):
                raise community_events.EventError("Choose a Telegram group you administer") from None
            admin = admin_check(get_db(), api, chat_id, user, force=True)
            if not admin["admin"]:
                raise community_events.EventError("Only a current group administrator can create an event", 403)
            status, chat = api("getChat", {"chat_id": chat_id})
            if status != 200 or not isinstance(chat, dict) or not chat.get("ok"):
                raise community_events.EventError("Telegram could not confirm that group", 400)
            info = chat.get("result") or {}
            if info.get("type") not in {"group", "supergroup"}:
                raise community_events.EventError("Events can only be hosted in a Telegram group")
            if body.get("game_room"):
                store.validate_event_link(body.get("game_room"), user, chat_id)
            event = community_events.create(user, _player(user).get("name"), body, chat_id,
                                            info.get("title") or info.get("username"))
            # Publishing is intentionally an ordinary group message; the event
            # is still usable in Videl if Telegram delivery is temporarily down.
            from config import WEBAPP_URL
            link = f"{str(WEBAPP_URL).rstrip('/')}/?tab=arcade&event={event['id']}"
            from datetime import datetime, timezone
            starts = datetime.fromisoformat(event["starts_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            text = (f"📅 {event['title']}\n{starts.strftime('%a, %d %b %Y · %H:%M UTC')}\n\n"
                    f"{event['description']}\n\nRSVP and join the room: {link}").strip()
            sent, result = api("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})
            event["announcement_sent"] = bool(sent == 200 and isinstance(result, dict) and result.get("ok"))
            return jsonify({"ok": True, "event": event})
        except (GameError, ActorError, community_events.EventError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "The event room could not be created"}), 503

    @app.route("/internal/arcade/events/<event_id>", methods=["GET", "POST"])
    def arcade_event(event_id):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            if request.method == "GET":
                return jsonify({"ok": True, "event": community_events.get(event_id, user)})
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise GameError("An RSVP choice is required")
            if body.get("action") in {"cancel", "edit"}:
                current = community_events.get(event_id, user)
                admin = admin_check(get_db(), api, int(current["chat_id"]), user, force=True)
                if not admin["admin"]:
                    verb = "edit" if body.get("action") == "edit" else "cancel"
                    raise community_events.EventError(f"Only a current group administrator can {verb} this event", 403)
                if body.get("action") == "cancel":
                    event = community_events.cancel(event_id, user)
                    notice = f"Event cancelled: {event['title']}"
                    key = "cancellation_sent"
                else:
                    if body.get("game_room"):
                        store.validate_event_link(body.get("game_room"), user, int(current["chat_id"]))
                    event = community_events.update(event_id, user, body)
                    notice = f"Event updated: {event['title']}\nStarts: {event['starts_at']}"
                    key = "update_notice_sent"
                sent, result = api("sendMessage", {"chat_id": int(event["chat_id"]), "text": notice})
                event[key] = bool(sent == 200 and isinstance(result, dict) and result.get("ok"))
                return jsonify({"ok": True, "event": event})
            event = community_events.rsvp(event_id, user, _player(user).get("name"), body.get("status"))
            return jsonify({"ok": True, "event": event})
        except (GameError, ActorError, community_events.EventError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "That event room is unavailable"}), 503

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

    @app.route("/internal/arcade/avatar/<int:user_id>", methods=["GET"])
    def arcade_avatar(user_id):
        """The player's Telegram photo, or a 404 the panel can fall back from."""
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            actor()
            doc = players.get(user_id)
            if doc is None:
                raise GameError("That player is not in the arcade", 404)
            mime, payload = avatars.fetch(doc, api)
            return jsonify({"ok": True, "mime": mime,
                            "data": base64.b64encode(payload).decode("ascii")})
        except (GameError, ActorError, avatars.AvatarError) as error:
            return _answer(error)

    @app.route("/internal/arcade/player/<int:user_id>", methods=["GET"])
    def arcade_player(user_id):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            actor()
            doc = players.get(user_id)
            if doc is None:
                raise GameError("That player is not in the arcade", 404)
            public = players.public(doc)
            # The panel needs the name and record; a provider URL is never
            # handed to the browser. Profile images go through our byte proxy.
            safe = {key: public.get(key) for key in ("id", "name", "username", "stats")}
            return jsonify({"ok": True, "player": safe})
        except (GameError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "That profile is unavailable"}), 503

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
