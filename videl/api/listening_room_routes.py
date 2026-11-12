"""Authenticated internal routes for browser shared-listening rooms."""
import threading
import time
from collections import OrderedDict, deque

from flask import jsonify, request

from videl.api.actor import ActorError, require_actor
from videl.web_music_rooms import ListeningRoomError, normalize_code
from videl import listening_room_store as store

MAX_BODY = 16_384
_RATE_LOCK = threading.RLock()
_RATE_BUCKETS = OrderedDict()
MAX_RATE_KEYS = 10_000


def _rate_limit(actor, operation, *, maximum, window=60):
    """Process-local bounded sliding window; callers fail closed at capacity."""
    now = time.monotonic()
    key = (int(actor), operation)
    with _RATE_LOCK:
        while _RATE_BUCKETS:
            _, times = next(iter(_RATE_BUCKETS.items()))
            if times and now - times[-1] <= window:
                break
            _RATE_BUCKETS.popitem(last=False)
        times = _RATE_BUCKETS.get(key)
        if times is None:
            if len(_RATE_BUCKETS) >= MAX_RATE_KEYS:
                raise ListeningRoomError("Room requests are temporarily rate-limited", 429)
            times = deque()
            _RATE_BUCKETS[key] = times
        while times and now - times[0] > window:
            times.popleft()
        if len(times) >= maximum:
            raise ListeningRoomError("Too many room requests; wait a little and try again", 429)
        times.append(now)
        _RATE_BUCKETS.move_to_end(key)


def _error(error):
    return jsonify({"ok": False, "error": str(error)}), getattr(error, "status", 400)


def _actor(secret):
    return require_actor(secret() if callable(secret) else secret)


def register_listening_room_routes(app, authorized, secret):
    @app.route("/internal/listening-rooms", methods=["POST"])
    def listening_rooms_create():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            actor = _actor(secret)
            _rate_limit(actor, "create", maximum=3)
            if request.content_length is not None and request.content_length > MAX_BODY:
                return jsonify({"ok": False, "error": "That request is too large"}), 413
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise ListeningRoomError("A JSON object is required")
            room = store.create(actor, body.get("name"))
            return jsonify({"ok": True, "room": room}), 201
        except (ActorError, ListeningRoomError) as error:
            return _error(error)
        except Exception:
            return jsonify({"ok": False, "error": "The listening room could not be created"}), 503

    @app.route("/internal/listening-rooms/join", methods=["POST"])
    def listening_rooms_join():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            actor = _actor(secret)
            _rate_limit(actor, "join", maximum=10)
            if request.content_length is not None and request.content_length > MAX_BODY:
                return jsonify({"ok": False, "error": "That request is too large"}), 413
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise ListeningRoomError("An invite code is required")
            code = normalize_code(body.get("code"))
            room = store.join(code, actor, body.get("name"))
            return jsonify({"ok": True, "room": room})
        except (ActorError, ListeningRoomError) as error:
            return _error(error)
        except Exception:
            return jsonify({"ok": False, "error": "That listening room could not be joined"}), 503

    @app.route("/internal/listening-rooms/<code>", methods=["GET", "POST"])
    def listening_room(code):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            actor = _actor(secret)
            code = normalize_code(code)
            if request.method == "GET":
                _rate_limit(actor, "read", maximum=30)
                return jsonify({"ok": True, "room": store.read(code, actor)})
            _rate_limit(actor, "mutate", maximum=30)
            if request.content_length is not None and request.content_length > MAX_BODY:
                return jsonify({"ok": False, "error": "That request is too large"}), 413
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise ListeningRoomError("A room action is required")
            if body.get("action") == "leave":
                return jsonify({"ok": True, **store.leave(code, actor)})
            return jsonify({"ok": True, "room": store.mutate(code, actor, body)})
        except (ActorError, ListeningRoomError) as error:
            return _error(error)
        except Exception:
            return jsonify({"ok": False, "error": "The listening room is unavailable"}), 503
