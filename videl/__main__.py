# Videl — Render backend: Telegram bot + private Flask API.
# Next.js frontend lives on Vercel and calls this backend over HTTPS.
import asyncio
import importlib
import os
import signal
import threading
import re
import time
import logging
import hmac
import requests
from collections import deque
from flask import Flask, g, jsonify, request
from pyrogram import idle
import config
from videl import LOGGER, bot
from videl.modules import ALL_MODULES

BACKEND_PORT = int(os.getenv("PORT", str(config.PORT)))

_flask = Flask(__name__)
_BOT_LOOP = None
_BOT_STATUS = "starting"
# Why the bot is not running, when it failed to start. Shown on /health so the
# owner can diagnose from the panel instead of hunting Render logs. Redacted.
_BOT_ERROR = ""
_BOT_ONLINE_AT = None
# How many start attempts this process has made: 1 means it started first try.
_BOT_ATTEMPTS = 0

# Rolling latency of the server-to-server API calls the panel makes. A single
# /health round-trip is one sample; Settings asks for the distribution instead.
_API_TIMINGS: deque = deque(maxlen=400)
# A ping to Mongo, measured the same way, so the panel can tell a slow API from
# a slow database instead of seeing one number and guessing.
_DB_TIMINGS: deque = deque(maxlen=200)
_TIMING_LOCK = threading.Lock()
_TIMED_PREFIXES = ("/internal/", "/api/")
_KEEPALIVE_THREAD = None
_KEEPALIVE_STATE = {"last_success": None, "consecutive_failures": 0, "last_error": None}


@_flask.before_request
def _start_request_timer():
    g.videl_started = time.perf_counter()


@_flask.after_request
def _record_request_timing(response):
    started = getattr(g, "videl_started", None)
    if started is not None and request.path.startswith(_TIMED_PREFIXES):
        with _TIMING_LOCK:
            _API_TIMINGS.append((time.perf_counter() - started) * 1000.0)
    return response


def _api_latency() -> dict:
    with _TIMING_LOCK:
        samples = list(_API_TIMINGS)
    if not samples:
        return {"p95_ms": None, "samples": 0}
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {"p95_ms": round(ordered[index], 1), "samples": len(ordered)}


def _keepalive_status() -> dict:
    return {
        "running": bool(_KEEPALIVE_THREAD and _KEEPALIVE_THREAD.is_alive()),
        **dict(_KEEPALIVE_STATE),
    }


try:
    from videl.api.eldian_routes import register_eldian_routes
    register_eldian_routes(_flask)
except Exception as _eldian_exc:
    LOGGER.warning("Could not register Eldian routes: %s", _eldian_exc)


def _internal_authorized():
    expected = getattr(config, "WEBAPP_SECRET", "") or ""
    supplied = request.headers.get("X-Videl-Internal", "")
    return bool(expected) and hmac.compare_digest(supplied, expected)


def _bot_api(method, payload, files=None):
    from videl.utils.bot_api import call_bot_api
    return call_bot_api(method, payload, files=files)


from videl.api.group_view_routes import register_group_view_routes
register_group_view_routes(_flask,_internal_authorized,_bot_api)

# Public arcade and the group-manager view. Both trust only a signed actor
# assertion minted by the panel, never a user id supplied by a browser.
from videl.api.manager_routes import register_manager_routes
from videl.games.routes import register_arcade_routes
register_arcade_routes(_flask,_internal_authorized,_bot_api,lambda: getattr(config,'WEBAPP_SECRET','') or '')
register_manager_routes(_flask,_internal_authorized,_bot_api,lambda: getattr(config,'WEBAPP_SECRET','') or '')

# ── Render backend health and service metadata ───────────────────────────
@_flask.route("/")
@_flask.route("/_videl_status")
def _status_json():
    return jsonify({
        "service": "Videl Render backend",
        "status": "running",
        "bot": getattr(config, "BOT_USERNAME", "videlapp"),
        "webapp": getattr(config, "WEBAPP_URL", ""),
        "health": "/health",
        "api_index": "/api",
        "revision": __import__("videl").build_revision,
    }), 200

def _db_latency() -> dict:
    """Median-ish round trip to Mongo, measured now and rolled with history."""
    from videl.utils.db import get_db, is_connected
    if not is_connected():
        return {"p95_ms": None, "samples": len(_DB_TIMINGS), "connected": False}
    try:
        database = get_db()
        started = time.perf_counter()
        database.command("ping")
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        with _TIMING_LOCK:
            _DB_TIMINGS.append(elapsed)
            samples = sorted(_DB_TIMINGS)
        index = max(0, min(len(samples) - 1, int(round(0.95 * len(samples))) - 1))
        return {"p95_ms": samples[index], "samples": len(samples), "connected": True,
                "last_ms": elapsed}
    except Exception:
        LOGGER.debug("database ping failed", exc_info=True)
        return {"p95_ms": None, "samples": len(_DB_TIMINGS), "connected": False}


def _health_text(value) -> str:
    """Error text that is safe to publish: no token, no long credentials."""
    text = str(value or "").strip()
    token = str(getattr(config, "BOT_TOKEN", "") or "")
    if token and token in text:
        text = text.replace(token, "<redacted>")
    # Bot and database errors occasionally echo a secret-looking run of
    # characters. Nothing a human needs to read is 32+ characters long.
    text = re.sub(r"[A-Za-z0-9_-]{32,}", "<redacted>", text)
    return text[:240]


@_flask.route("/health")
def _health():
    from videl import bot_start_time
    from videl.core.watcher import watchdog_status
    maintenance = watchdog_status()
    try:
        from videl.utils.db import is_connected
        database = "connected" if is_connected() else "disconnected"
    except Exception:
        database = "unknown"
    from videl import build_revision
    from videl.utils.assistant import assistant_status
    from videl.utils.downloader_status import downloader_status
    user_assistant = assistant_status()
    media_downloaders = downloader_status()
    # "status" stays "ok" while the HTTP API answers: uptime monitors must not
    # flap because Telegram is down. ``degraded`` names the parts that are not
    # working, so the panel can say what is wrong instead of only that it is.
    reasons = []
    if user_assistant["configured"] and not user_assistant["ready"]:
        reasons.append("Telegram voice assistant is " + user_assistant["state"])
    if _BOT_STATUS != "online":
        reasons.append("Telegram bot is " + _BOT_STATUS)
    if database == "disconnected":
        reasons.append("MongoDB is disconnected")
    if not maintenance.get("running"):
        reasons.append("Maintenance watchdog is not running")
    return jsonify({"status": "ok", "service": "videl-render-backend", "revision": build_revision,
                    "bot_status": _BOT_STATUS, "bot_error": _BOT_ERROR or None,
                    "bot_online_at": _BOT_ONLINE_AT, "bot_attempts": _BOT_ATTEMPTS,
                    "assistant": user_assistant, "media_downloaders": media_downloaders,
                    "degraded": bool(reasons),
                    "degraded_reasons": reasons, "database": database,
                    "uptime": max(0, int(time.time() - bot_start_time)),
                    "api": _api_latency(), "db": _db_latency(),
                    "keepalive": _keepalive_status(),
                    "watchdog": {key: maintenance.get(key) for key in ("running", "healthy", "last_tick", "checks")}}), 200

@_flask.route("/internal/auth", methods=["POST"])
def _internal_auth():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    import hashlib
    import json
    from urllib.parse import parse_qsl
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    token = getattr(config, "BOT_TOKEN", "") or ""
    owner_id = "6265999542"  # Explicit webapp owner; sudo/config overrides do not grant access.
    if not token or not owner_id:
        return jsonify({"ok": False, "error": "Telegram owner authentication is not configured"}), 503
    try:
        init_data = body.get("init_data", "")
        login_widget = body.get("login_widget")
        if isinstance(init_data, str) and init_data and len(init_data) <= 8192:
            pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
            fields = dict(pairs)
            if len(fields) != len(pairs):
                raise ValueError("duplicate authentication fields")
            received = fields.pop("hash", "")
            if len(received) != 64:
                raise ValueError("invalid hash")
            data_check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
            secret_key = hmac.new(b"WebAppData", token.encode(), "sha256").digest()
            expected = hmac.new(secret_key, data_check.encode(), "sha256").hexdigest()
            if not hmac.compare_digest(received.lower(), expected):
                raise ValueError("invalid Mini App signature")
            auth_date = int(fields.get("auth_date", "0"))
            user = json.loads(fields.get("user", "{}"))
        elif isinstance(login_widget, dict) and len(login_widget) <= 20:
            fields = {str(key): str(value) for key, value in login_widget.items() if key != "hash" and value is not None}
            received = str(login_widget.get("hash", ""))
            if len(received) != 64 or not all(c in "0123456789abcdefABCDEF" for c in received):
                raise ValueError("invalid Login Widget hash")
            data_check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
            secret_key = hashlib.sha256(token.encode()).digest()
            expected = hmac.new(secret_key, data_check.encode(), "sha256").hexdigest()
            if not hmac.compare_digest(received.lower(), expected):
                raise ValueError("invalid Login Widget signature")
            auth_date = int(fields.get("auth_date", "0"))
            user = {key: login_widget.get(key) for key in ("id", "first_name", "username") if login_widget.get(key) is not None}
        else:
            return jsonify({"ok": False, "error": "Telegram authentication data is required"}), 400
        now = int(time.time())
        if not auth_date or auth_date > now + 60 or now - auth_date > 86400:
            return jsonify({"ok": False, "error": "Telegram authentication data is expired"}), 401
        if not isinstance(user, dict) or str(user.get("id", "")) != owner_id:
            return jsonify({"ok": False, "error": "This control panel is restricted to the configured bot owner"}), 403
        return jsonify({"ok": True, "user": {key: user.get(key) for key in ("id", "first_name", "username") if user.get(key) is not None}})
    except (ValueError, TypeError, json.JSONDecodeError):
        return jsonify({"ok": False, "error": "Invalid Telegram authentication data"}), 401

@_flask.route("/internal/identity", methods=["POST"])
def _internal_identity():
    """Who Telegram says this is. Not a grant of owner power."""
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    from videl.utils.telegram_auth import AuthError, public_user, verify_init_data, verify_login_widget
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return jsonify({"ok": False, "error": "Telegram authentication is not configured"}), 503
    try:
        if isinstance(body.get("init_data"), str) and body.get("init_data"):
            user = verify_init_data(body["init_data"], token)
        elif isinstance(body.get("login_widget"), dict):
            user = verify_login_widget(body["login_widget"], token)
        else:
            return jsonify({"ok": False, "error": "Telegram authentication data is required"}), 400
    except AuthError as error:
        return jsonify({"ok": False, "error": str(error)}), 401
    player = public_user(user)
    try:
        from videl.utils import players
        if players.upsert(player) is None:
            LOGGER.debug("player record not stored; database unavailable")
    except Exception:
        LOGGER.debug("player record not stored", exc_info=True)
    return jsonify({"ok": True, "player": player})


@_flask.route("/internal/send-message", methods=["POST"])
def _internal_send_message():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    chat_id = str(body.get("chat_id", "")).strip()
    text = body.get("text")
    as_user = body.get("as_user") is True
    if not chat_id or len(chat_id) > 128 or not isinstance(text, str) or not text.strip() or len(text) > 4096:
        return jsonify({"ok": False, "error": "A chat ID and 1–4096 characters of message text are required"}), 400
    if as_user:
        if not getattr(config, "STRING_SESSION", ""):
            return jsonify({"ok": False, "error": "User session is not configured on the Render backend"}), 503
        loop = _BOT_LOOP
        if loop is None or not loop.is_running():
            return jsonify({"ok": False, "error": "Telegram client is not running"}), 503
        try:
            from videl import assistant
            future = asyncio.run_coroutine_threadsafe(assistant.send_message(chat_id, text), loop)
            sent = future.result(timeout=15)
            return jsonify({"ok": True, "chat_id": str(sent.chat.id), "message_id": sent.id, "via": "user"})
        except Exception as exc:
            LOGGER.info("owner user-session message failed: %s", exc)
            return jsonify({"ok": False, "error": "The user session could not send to that Telegram chat"}), 502
    status, result = _bot_api("sendMessage", {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}})
    if not status or not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("description", "Telegram rejected the message")}), 502
    message = result.get("result", {})
    return jsonify({"ok": True, "chat_id": str(message.get("chat", {}).get("id", chat_id)), "message_id": message.get("message_id"), "via": "bot"})

@_flask.route("/internal/scheduled-posts", methods=["GET", "POST", "DELETE"])
def _internal_scheduled_posts():
    if not _internal_authorized():
        return jsonify({"ok":False,"error":"unauthorized"}),403
    if request.method == "POST":
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not body.get("schedule_at"):
            return jsonify({"ok":False,"error":"A scheduled time is required"}),400
        return _internal_channel_post()
    from videl.utils.scheduled_posts import list_jobs, cancel_job
    try:
        if request.method == "GET":
            return jsonify({"ok":True,"jobs":list_jobs()}),200
        body = request.get_json(silent=True)
        if not isinstance(body,dict):
            raise ValueError("A job ID is required")
        cancelled = cancel_job(body.get("id"))
        return jsonify({"ok":cancelled,"error":None if cancelled else "Job is no longer pending; refresh its status."}),200 if cancelled else 409
    except (ValueError,TypeError,AttributeError):
        return jsonify({"ok":False,"error":"Invalid schedule ID"}),400
    except Exception:
        return jsonify({"ok":False,"error":"Schedule queue unavailable"}),503


@_flask.route("/internal/scheduled-posts/retry", methods=["POST"])
def _internal_scheduled_retry():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    from videl.utils.scheduled_posts import retry_job
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("id"):
        return jsonify({"ok": False, "error": "A job ID is required"}), 400
    try:
        return jsonify(retry_job(body.get("id"), body.get("schedule_at"))), 200
    except (ValueError, TypeError, AttributeError) as error:
        return jsonify({"ok": False, "error": str(error)}), 409
    except Exception:
        LOGGER.exception("scheduled retry failed")
        return jsonify({"ok": False, "error": "The schedule could not be requeued"}), 503


@_flask.route("/internal/scheduled-posts/series", methods=["POST"])
def _internal_scheduled_series():
    """Pause, resume or skip one occurrence of a repeating series."""
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    from videl.utils.scheduled_posts import set_paused, skip_next
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("id"):
        return jsonify({"ok": False, "error": "A job ID is required"}), 400
    action = body.get("action")
    try:
        if action == "skip":
            return jsonify(skip_next(body.get("id"))), 200
        if action in {"pause", "resume"}:
            return jsonify(set_paused(body.get("id"), action == "pause")), 200
        return jsonify({"ok": False, "error": "Action must be pause, resume or skip"}), 400
    except (ValueError, TypeError, AttributeError) as error:
        return jsonify({"ok": False, "error": str(error)}), 409
    except Exception:
        LOGGER.exception("scheduled series action failed")
        return jsonify({"ok": False, "error": "The series could not be changed"}), 503


@_flask.route("/internal/scheduled-posts/duplicate", methods=["POST"])
def _internal_scheduled_duplicate():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    from videl.utils.scheduled_posts import duplicate_job
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("id"):
        return jsonify({"ok": False, "error": "A job ID is required"}), 400
    try:
        return jsonify(duplicate_job(body.get("id"), body.get("schedule_at"))), 200
    except (ValueError, TypeError, AttributeError) as error:
        return jsonify({"ok": False, "error": str(error)}), 409
    except Exception:
        LOGGER.exception("scheduled duplicate failed")
        return jsonify({"ok": False, "error": "The copy could not be queued"}), 503


@_flask.route("/internal/channel-post", methods=["POST"])
def _internal_channel_post():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    import json
    from urllib.parse import urlparse
    if request.content_length and request.content_length > 4400000:
        return jsonify({"ok": False, "error": "Image upload is too large (4 MB maximum)"}), 413
    upload = request.files.get("image")
    image_data = None
    image_mime = None
    if upload is not None:
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        image_data = upload.stream.read(4 * 1024 * 1024 + 1)
        if len(image_data) > 4 * 1024 * 1024:
            return jsonify({"ok": False, "error": "Use an image under 4 MB"}), 413
        try:
            with Image.open(BytesIO(image_data)) as image:
                image_mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
                if not image_mime or image.width * image.height > 25000000:
                    raise ValueError("Unsupported image type or dimensions")
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            return jsonify({"ok": False, "error": "Upload a valid PNG, JPEG or WebP under 25 megapixels"}), 400
    body = request.form.to_dict() if request.mimetype == "multipart/form-data" else request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    chat_id = str(body.get("chat_id", "")).strip()
    text = str(body.get("text", "")).strip()
    media_url = str(body.get("media_url", "")).strip()
    if not chat_id or len(chat_id) > 128 or not text and not media_url and image_data is None or len(text) > 65536:
        return jsonify({"ok": False, "error": "A channel ID and post text or media are required"}), 400
    parse_mode = body.get("parse_mode", "HTML")
    if parse_mode not in ("HTML", "Markdown", "MarkdownV2"):
        return jsonify({"ok": False, "error": "Unsupported parse mode"}), 400
    if parse_mode == "HTML" and text:
        # The visual editor can nest marks in ways Telegram rejects (code plus
        # bold on the same characters). Normalize here so a post is delivered
        # instead of failing with "can't parse entities".
        from videl.utils.group_view import normalize_rich
        text, _, used = normalize_rich(text)
        if not used:
            parse_mode = None
    from videl.utils.post_format import post_text_length
    text_length = post_text_length(text, parse_mode)
    if text_length > 4096:
        return jsonify({"ok": False, "error": "Post text is limited to 4096 visible characters"}), 400
    method = "sendMessage"
    payload = {"chat_id": chat_id}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if image_data is not None:
        if text_length > 1024:
            return jsonify({"ok": False, "error": "Image captions allow 1024 visible characters"}), 400
        method = "sendPhoto"
        payload["caption"] = text
    elif media_url:
        parsed = urlparse(media_url)
        if parsed.scheme != "https" or not parsed.netloc or len(media_url) > 2048:
            return jsonify({"ok": False, "error": "Media URL must be a valid HTTPS URL"}), 400
        if text_length > 1024:
            return jsonify({"ok": False, "error": "Photo captions are limited to 1024 characters"}), 400
        method = "sendPhoto"
        payload.update({"photo": media_url, "caption": text})
    else:
        payload["text"] = text
    buttons = body.get("buttons")
    if buttons:
        try:
            if isinstance(buttons, str): buttons = json.loads(buttons)
            rows = buttons if isinstance(buttons, list) else []
            if rows and not isinstance(rows[0], list): rows = [rows]
            if not rows or len(rows) > 8: raise ValueError("invalid keyboard")
            keyboard = []
            for row in rows:
                if not isinstance(row, list) or not row or len(row) > 8: raise ValueError("invalid row")
                normalized = []
                for item in row:
                    if not isinstance(item, dict):
                        raise ValueError("button must be an object")
                    label = str(item.get("text", "")).strip()
                    if not label or len(label) > 64:
                        raise ValueError("button labels allow 1–64 characters")
                    entry = {"text": label}
                    copy_text = item.get("copyText")
                    if copy_text is not None:
                        if not isinstance(copy_text, str) or not 1 <= len(copy_text.encode("utf-16-le")) // 2 <= 256:
                            raise ValueError("copy text allows 1–256 characters")
                        entry["copy_text"] = {"text": copy_text}
                    else:
                        url = str(item.get("url", item.get("href", ""))).strip()
                        parsed = urlparse(url)
                        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or len(url) > 2048:
                            raise ValueError("buttons require a valid HTTPS URL without credentials")
                        entry["url"] = url
                    style = item.get("style", "default")
                    if style not in {"default", "primary", "success", "danger"}:
                        raise ValueError("unsupported button style")
                    if style != "default":
                        entry["style"] = style
                    icon = item.get("iconId")
                    if icon:
                        if not isinstance(icon, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", icon) or int(icon) > 9223372036854775807:
                            raise ValueError("invalid custom emoji ID")
                        entry["icon_custom_emoji_id"] = icon
                    normalized.append(entry)
                keyboard.append(normalized)
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        except (ValueError, TypeError, AttributeError) as exc:
            return jsonify({"ok": False, "error": f"Invalid button layout: {exc}"}), 400
    if "schedule_at" in body:
        if image_data is not None:
            return jsonify({"ok": False, "error": "Scheduled images need a persistent HTTPS URL, not a local upload"}), 400
        try:
            from videl.utils.scheduled_posts import enqueue
            return jsonify(enqueue(method, payload, body["schedule_at"], body.get("request_id"),
                                   body.get("repeat"), body.get("timezone"),
                                   body.get("wall_time"))), 200
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Schedule could not be confirmed. Refresh the queue before retrying."}), 503
    if image_data is not None:
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[image_mime]
        status, result = _bot_api(method, payload, files={"photo": (f"videl-post.{extension}", image_data, image_mime)})
    else:
        status, result = _bot_api(method, payload)
    if not status or not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("description", "Telegram rejected the post")}), 502
    sent = result.get("result", {})
    return jsonify({"ok": True, "chat_id": str(sent.get("chat", {}).get("id", chat_id)), "message_id": sent.get("message_id"), "via": "bot"})

@_flask.route("/internal/stats")
def _internal_stats():
    # Server-to-server only: Next.js forwards the backend secret; never expose
    # database credentials or personal records through this endpoint.
    expected = getattr(config, "WEBAPP_SECRET", "") or ""
    supplied = request.headers.get("X-Videl-Internal", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from videl import bot_start_time
        from videl.utils.db import (get_served_chats_count, get_served_users_count,
                                    get_total_plays, is_connected, read_live_totals)
        if not is_connected():
            return jsonify({"ok": False, "error": "MongoDB is not connected", "database": "disconnected"}), 503
        totals = read_live_totals()
        return jsonify({
            "ok": True,
            "stats": {
                "users": totals["users"],
                "chats": totals["chats"],
                "plays": totals["plays"],
                "uptime": max(0, int(time.time() - bot_start_time)),
                "bot_username": getattr(config, "BOT_USERNAME", "videlapp"),
                "bot_name": getattr(config, "BOT_NAME", "Videl Studio"),
                "owner_username": getattr(config, "OWNER_USERNAME", "Beasgohan"),
                "database": "connected",
                "services": {
                    "bot_token": bool(getattr(config, "BOT_TOKEN", "")),
                    "user_session": bool(getattr(config, "STRING_SESSION", "")),
                    "mongo": True,
                    "music_api": True,
                    "logger_channel": bool(getattr(config, "LOGGER_ID", 0)),
                },
            },
        }), 200
    except Exception as exc:
        LOGGER.exception("internal stats query failed")
        return jsonify({"ok": False, "error": "database query failed"}), 503

@_flask.route("/internal/chats")
def _internal_chats():
    expected = getattr(config, "WEBAPP_SECRET", "") or ""
    supplied = request.headers.get("X-Videl-Internal", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from videl.utils.db import get_db
        from videl.utils.automation import normalize as normalize_automation
        from videl.utils.group_health import evaluate as evaluate_health, summarize as summarize_health
        from videl.utils.group_view import BOOL_SETTINGS, INT_SETTINGS, INT_DEFAULTS, ENUM_SETTINGS, SETTING_DEFAULTS
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        # The fleet list is paged. It used to stop at 200 silently, so a bot in
        # more groups than that hid the rest with no hint at all.
        try:
            limit = int(request.args.get("limit", "200"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit must be a number"}), 400
        if not 20 <= limit <= 1000:
            return jsonify({"ok": False, "error": "limit must be between 20 and 1000"}), 400
        raw_cursor = (request.args.get("cursor") or "").strip()
        # Read the ids in one sorted projection and slice in Python: chat ids are
        # integers, but a stale string id must not make a cursor skip a group.
        every_id = [doc.get("_id") for doc in db["served_chats"].find({}, {"_id": 1}).sort("_id", 1)]
        total = len(every_id)
        start = 0
        if raw_cursor:
            for index, value in enumerate(every_id):
                if str(value) == raw_cursor:
                    start = index + 1
                    break
            else:
                return jsonify({"ok": False, "error": "cursor is not a chat in this list", "total": total}), 400
        page_ids = every_id[start:start + limit]
        ids = page_ids
        has_more = start + len(page_ids) < total
        next_cursor = page_ids[-1] if (page_ids and has_more) else None
        int_ids = []
        for value in ids:
            try:
                int_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        documents = {int(doc["chat_id"]): doc for doc in db["mgmt_chat_settings"].find({"chat_id": {"$in": int_ids}})}
        cached = {int(doc["_id"]): doc for doc in db["mgmt_chat_info"].find({"_id": {"$in": int_ids}})}
        warns_by_chat, notes_by_chat, blacklist_by_chat, approved_by_chat, pending_by_chat = {}, {}, {}, {}, {}
        reports_by_chat = {}
        for name, target, extra in (
            ("mgmt_warnings", warns_by_chat, {}),
            ("mgmt_notes", notes_by_chat, {}),
            ("blacklist", blacklist_by_chat, {}),
            ("approved", approved_by_chat, {}),
            # Only pending requests matter: answered rows are history, not work.
            ("mgmt_join_requests", pending_by_chat, {"status": "pending"}),
            ("mgmt_reports", reports_by_chat, {"status": "open"}),
        ):
            field = "chat" if name in {"blacklist", "approved"} else "chat_id"
            match = {field: {"$in": int_ids}, **extra}
            try:
                for row in db[name].aggregate([{"$match": match}, {"$group": {"_id": f"${field}", "total": {"$sum": 1}}}]):
                    target[int(row["_id"])] = int(row["total"])
            except Exception:
                LOGGER.debug("group summary aggregation failed for %s", name, exc_info=True)

        def settings_for(chat_id):
            document = documents.get(chat_id) or {}
            values = {key: bool(document.get(key, SETTING_DEFAULTS.get(key, False))) for key in BOOL_SETTINGS}
            for key, (low, high) in INT_SETTINGS.items():
                try:
                    value = int(document.get(key, INT_DEFAULTS.get(key, low)))
                except (TypeError, ValueError):
                    value = INT_DEFAULTS.get(key, low)
                values[key] = max(low, min(value, high))
            for key, allowed in ENUM_SETTINGS.items():
                value = document.get(key)
                values[key] = value if value in allowed else "del"
            return values

        from concurrent.futures import ThreadPoolExecutor
        bot_id = None
        if getattr(config, "BOT_TOKEN", ""):
            _, identity = _bot_api("getMe", {})
            if identity and identity.get("ok"):
                bot_id = (identity.get("result") or {}).get("id")
        def enrich(chat_id):
            known = cached.get(chat_id) or {}
            row = {
                "id": chat_id,
                "title": known.get("title") or f"Telegram chat {chat_id}",
                "username": known.get("username"),
                "type": known.get("type", "unknown"),
                "members": known.get("members"),
                "available": bool(known.get("available", False)),
                "bot_admin": known.get("bot_admin"),
            }
            if not getattr(config, "BOT_TOKEN", ""):
                return row
            _, chat = _bot_api("getChat", {"chat_id": chat_id})
            valid_chat = bool(chat and chat.get("ok"))
            result = chat.get("result", {}) if valid_chat else {}
            members = known.get("members")
            bot_admin = known.get("bot_admin")
            if valid_chat:
                _, count = _bot_api("getChatMemberCount", {"chat_id": chat_id})
                members = count.get("result") if count and count.get("ok") else members
                # The bot's own administrator status decides whether any lock can
                # be enforced, so it is read once and cached with the profile.
                if bot_id:
                    _, member = _bot_api("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
                    if member and member.get("ok"):
                        status = str((member.get("result") or {}).get("status") or "")
                        bot_admin = status in {"creator", "administrator"}
            updated = {
                "_id": chat_id,
                "title": result.get("title") or result.get("username") or row["title"],
                "username": result.get("username"),
                "type": result.get("type", row["type"]),
                "members": members,
                "available": valid_chat,
                "bot_admin": bot_admin,
            }
            try:
                db["mgmt_chat_info"].update_one({"_id": chat_id}, {"$set": updated}, upsert=True)
            except Exception:
                LOGGER.debug("chat info cache write failed", exc_info=True)
            row.update({key: updated[key] for key in ("title", "username", "type", "members", "available", "bot_admin")})
            return row

        enrichable = [chat_id for chat_id in int_ids if not (cached.get(chat_id) or {}).get("available")][:25]
        fresh = {}
        if enrichable:
            with ThreadPoolExecutor(max_workers=8) as pool:
                fresh = {row["id"]: row for row in pool.map(enrich, enrichable)}
        rows = []
        for chat_id in int_ids:
            row = fresh.get(chat_id) or {
                "id": chat_id,
                "title": (cached.get(chat_id) or {}).get("title") or f"Telegram chat {chat_id}",
                "username": (cached.get(chat_id) or {}).get("username"),
                "type": (cached.get(chat_id) or {}).get("type", "unknown"),
                "members": (cached.get(chat_id) or {}).get("members"),
                "available": bool((cached.get(chat_id) or {}).get("available", False)),
                "bot_admin": (cached.get(chat_id) or {}).get("bot_admin"),
            }
            row = dict(row)
            row["settings"] = settings_for(chat_id)
            try:
                # The token a panel sends back so it cannot overwrite a newer
                # edit (see videl/utils/settings_store.py).
                row["revision"] = max(0, int((documents.get(chat_id) or {}).get("revision") or 0))
            except (TypeError, ValueError):
                row["revision"] = 0
            row["counts"] = {
                "warns": warns_by_chat.get(chat_id, 0),
                "notes": notes_by_chat.get(chat_id, 0),
                "blacklist": blacklist_by_chat.get(chat_id, 0),
                "approved": approved_by_chat.get(chat_id, 0),
                "pending_joins": pending_by_chat.get(chat_id, 0),
                "reports": reports_by_chat.get(chat_id, 0),
            }
            row["warn_limit"] = row["settings"]["warn_threshold"]
            row["explicit"] = {key: value for key, value in (documents.get(chat_id) or {}).items()
                               if key in BOOL_SETTINGS and type(value) is bool}
            row["automation"] = normalize_automation((documents.get(chat_id) or {}).get("automation"))
            row["health"] = evaluate_health(row)
            rows.append(row)
        summary = summarize_health(rows)
        # The totals in `summary` describe this page. `total` is the fleet, so a
        # caller can say "showing 200 of 743" instead of implying it has them all.
        summary["scope"] = "page"
        return jsonify({"ok": True, "chats": rows, "summary": summary,
                        "total": total, "returned": len(rows), "offset": start,
                        "has_more": has_more, "next_cursor": next_cursor,
                        # Kept for a panel build that predates paging.
                        "truncated": has_more})
    except Exception:
        LOGGER.exception("internal group list query failed")
        return jsonify({"ok": False, "error": "group query failed"}), 503


@_flask.route("/internal/chat/<int(signed=True):chat_id>", methods=["GET", "POST"])
def _internal_chat_detail(chat_id):
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from videl.utils.db import get_db
        from videl.utils.group_view import GroupView, ViewError
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        view = GroupView(db, _bot_api)
        if request.method == "GET":
            return jsonify(view.describe(chat_id))
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "A JSON object is required"}), 400
        payload = dict(body)
        payload["chat_id"] = chat_id
        return jsonify(view.act(payload))
    except ViewError as error:
        answer = {"ok": False, "error": str(error)}
        # A stale edit is not a generic failure: tell the panel which revision
        # to reload from so it can show the current values and let the owner retry.
        if getattr(error, "conflict", False):
            answer["conflict"] = True
            answer["revision"] = getattr(error, "revision", None)
        return jsonify(answer), error.status
    except Exception:
        LOGGER.exception("internal group detail failed")
        return jsonify({"ok": False, "error": "group detail request failed"}), 503


@_flask.route("/internal/chat/<int(signed=True):chat_id>/audit")
def _internal_chat_audit(chat_id):
    """Paginated change history for one group."""
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from videl.utils.db import get_db
        from videl.utils.group_view import GroupView, ViewError
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        kind = request.args.get("kind")
        search = (request.args.get("q") or "").strip()[:60] or None
        raw_actor = (request.args.get("actor") or "").strip()
        actor = None
        if raw_actor:
            try:
                actor = int(raw_actor)
            except ValueError:
                return jsonify({"ok": False, "error": "actor must be a Telegram user id"}), 400
            if actor <= 0:
                return jsonify({"ok": False, "error": "actor must be a Telegram user id"}), 400
        raw_limit = request.args.get("limit", "40")
        before = None
        before_id = request.args.get("before_id") or None
        if before_id:
            from videl.utils.audit import object_id
            if object_id(before_id) is None:
                return jsonify({"ok": False, "error": "before_id must be an audit row id"}), 400
        stamp = request.args.get("before")
        if stamp:
            from datetime import datetime
            try:
                before = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                return jsonify({"ok": False, "error": "before must be an ISO timestamp"}), 400
        try:
            limit = max(1, min(int(raw_limit), 100))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit must be a number"}), 400
        return jsonify(GroupView(db, _bot_api).events(
            chat_id, limit=limit, kind=kind, before=before, before_id=before_id,
            query=search, actor=actor))
    except ViewError as error:
        return jsonify({"ok": False, "error": str(error)}), error.status
    except Exception:
        LOGGER.exception("internal audit query failed")
        return jsonify({"ok": False, "error": "audit query failed"}), 503


@_flask.route("/internal/chat/<int(signed=True):chat_id>/backup")
def _internal_chat_backup(chat_id):
    """Portable configuration export: locks, automation, blacklist, commands."""
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from videl.utils.db import get_db
        from videl.utils.group_view import GroupView, ViewError
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        return jsonify(GroupView(db, _bot_api).export_group(chat_id))
    except ViewError as error:
        return jsonify({"ok": False, "error": str(error)}), error.status
    except Exception:
        LOGGER.exception("internal backup export failed")
        return jsonify({"ok": False, "error": "backup export failed"}), 503


@_flask.route("/internal/federation", methods=["GET"])
def _internal_federation_list():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    from videl.utils.db import get_db
    from videl.utils.federation_view import overview
    db = get_db()
    if db is None:
        return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
    return jsonify(overview(db))


@_flask.route("/internal/federation/<fed_id>", methods=["GET", "POST"])
def _internal_federation_detail(fed_id):
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", str(fed_id)):
        return jsonify({"ok": False, "error": "Invalid federation ID"}), 400
    from videl.utils.db import get_db
    from videl.utils.federation_view import detail, unban
    db = get_db()
    if db is None:
        return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
    if request.method == "GET":
        try:
            return jsonify(detail(db, fed_id))
        except LookupError as error:
            return jsonify({"ok": False, "error": str(error)}), 404
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("action") != "unban":
        return jsonify({"ok": False, "error": "The only federation write here is action=unban"}), 400
    try:
        user_id = int(body.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "A numeric user_id is required"}), 400
    outcome = unban(db, fed_id, user_id)
    LOGGER.info("federation %s: owner lifted the ban on %s", fed_id, user_id)
    return jsonify(outcome)


@_flask.route("/internal/chats/bulk", methods=["POST"])
def _internal_chats_bulk():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    chat_ids = body.get("chat_ids")
    if not isinstance(chat_ids, list) or not chat_ids or len(chat_ids) > 15:
        return jsonify({"ok": False, "error": "Choose between 1 and 15 groups for a bulk change"}), 400
    action = body.get("action")
    if action not in {"preset", "settings"}:
        return jsonify({"ok": False, "error": "Bulk changes support presets and protection settings"}), 400
    try:
        from videl.utils.db import get_db
        from videl.utils.group_view import GroupView, ViewError
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        view = GroupView(db, _bot_api)
        results = []
        for raw in chat_ids:
            try:
                chat_id = int(raw)
            except (TypeError, ValueError):
                results.append({"chat_id": raw, "ok": False, "error": "chat_id must be an integer"})
                continue
            payload = {"chat_id": chat_id, "action": action, "preset": body.get("preset"), "settings": body.get("settings")}
            try:
                outcome = view.act(payload, source="bulk")
                results.append({"chat_id": chat_id, "ok": True, "applied": outcome.get("preset") or "settings"})
            except ViewError as error:
                results.append({"chat_id": chat_id, "ok": False, "error": str(error)})
        return jsonify({"ok": True, "results": results, "updated": sum(1 for item in results if item["ok"])})
    except Exception:
        LOGGER.exception("internal bulk group update failed")
        return jsonify({"ok": False, "error": "bulk update failed"}), 503


@_flask.route("/internal/analytics")
def _internal_analytics():
    expected = getattr(config, "WEBAPP_SECRET", "") or ""
    supplied = request.headers.get("X-Videl-Internal", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        from datetime import datetime, timedelta, timezone
        from collections import Counter
        from videl.utils.db import get_db
        db=get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        now=datetime.now(timezone.utc)
        since=now-timedelta(hours=24)
        event_filter={"at":{"$gte":since}}
        total=db["command_events"].count_documents(event_filter)
        events=list(db["command_events"].find(event_filter,{"_id":0,"at":1,"command":1,"chat_id":1,"user_id":1}).sort("at",1).limit(20000))
        hours=[]
        for offset in range(23,-1,-1):
            hour=(now.replace(minute=0,second=0,microsecond=0)-timedelta(hours=offset))
            hours.append({"time":hour.strftime("%H:%M"),"commands":0})
        by_hour={point["time"]:point for point in hours}
        chats=Counter(); commands=Counter(); users=set()
        for event in events:
            dt=event.get("at")
            if dt is None: continue
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            bucket=dt.astimezone(timezone.utc).strftime("%H:00")
            if bucket in by_hour: by_hour[bucket]["commands"]+=1
            if event.get("chat_id") is not None: chats[str(event["chat_id"])]+=1
            if event.get("command"): commands[event["command"]]+=1
            if event.get("user_id") is not None: users.add(str(event["user_id"]))
        recent_raw = list(db["command_events"].find({}, {"_id": 0, "at": 1, "command": 1, "chat_id": 1}).sort("at", -1).limit(12))
        recent_events = []
        for item in recent_raw:
            dt = item.get("at")
            if dt is not None and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            recent_events.append({
                "command": item.get("command", "command"),
                "chat_id": str(item.get("chat_id", "")),
                "at": dt.isoformat() if dt else None,
            })
        return jsonify({
            "ok":True,
            "window_hours":24,
            "total_commands":total,
            "active_users":len(users),
            "series":hours,
            "top_chats":[{"id":chat_id,"commands":count} for chat_id,count in chats.most_common(10)],
            "top_commands":[{"command":command,"count":count} for command,count in commands.most_common(10)],
            "recent_events":recent_events,
            "truncated":total>len(events),
        })
    except Exception:
        LOGGER.exception("internal analytics query failed")
        return jsonify({"ok":False,"error":"analytics query failed"}),503

@_flask.route("/internal/chat-settings", methods=["POST"])
def _internal_chat_settings():
    expected = getattr(config, "WEBAPP_SECRET", "") or ""
    supplied = request.headers.get("X-Videl-Internal", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    try:
        chat_id = int(body.get("chat_id"))
        settings = body.get("settings")
        from videl.utils.group_view import PROTECTION
        if not isinstance(settings, dict) or not settings or set(settings) - PROTECTION or any(type(value) is not bool for value in settings.values()):
            return jsonify({"ok": False, "error": "Only supported boolean protection and automation settings may be changed"}), 400
        from videl.utils.db import get_db
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        if db["served_chats"].find_one({"_id": chat_id}) is None:
            return jsonify({"ok": False, "error": "Chat is not in Videl's served group list"}), 404
        from videl.utils.group_view import GroupView,ViewError
        try:
            payload={'chat_id':chat_id,'action':'protect','settings':settings}
            # Optional: a panel that read a revision gets the conflict check.
            if 'revision' in body:payload['revision']=body.get('revision')
            return jsonify(GroupView(db,_bot_api).act(payload))
        except ViewError as error:
            answer={'ok':False,'error':str(error)}
            if getattr(error,'conflict',False):
                answer['conflict']=True
                answer['revision']=getattr(error,'revision',None)
            return jsonify(answer),error.status
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "chat_id must be an integer"}), 400
    except Exception:
        LOGGER.exception("internal group settings update failed")
        return jsonify({"ok": False, "error": "settings update failed"}), 503

@_flask.route("/internal/broadcast", methods=["POST"])
def _internal_broadcast():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    text = str(body.get("text", "")).strip()
    scope = str(body.get("scope", "chats")).strip()
    if scope not in ("chats", "users", "all"):
        return jsonify({"ok": False, "error": "Invalid broadcast audience"}), 400
    if not text or len(text) > 4096:
        return jsonify({"ok": False, "error": "Broadcast text (1–4096 chars) is required"}), 400
    try:
        from videl.utils.db import get_db
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        targets = []
        if scope in ("chats", "all"):
            targets.extend(doc.get("_id") for doc in db["served_chats"].find({}, {"_id": 1}).limit(60))
        if scope in ("users", "all"):
            targets.extend(doc.get("_id") for doc in db["served_users"].find({}, {"_id": 1}).limit(60))
        unique_targets = [t for t in dict.fromkeys(targets) if t is not None][:60]
        if not unique_targets:
            return jsonify({"ok": False, "error": "No served recipients recorded in MongoDB yet"}), 404
        sent, failed = 0, 0
        for chat_id in unique_targets:
            status, res = _bot_api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
            if status and res.get("ok"):
                sent += 1
            else:
                failed += 1
        return jsonify({"ok": True, "sent": sent, "failed": failed, "total": len(unique_targets)})
    except Exception:
        LOGGER.exception("internal broadcast failed")
        return jsonify({"ok": False, "error": "broadcast execution failed"}), 503

@_flask.route("/internal/bot-settings", methods=["GET", "POST"])
def _internal_bot_settings():
    if not _internal_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    if request.method == "GET":
        me_status, me_res = _bot_api("getMe", {})
        if not me_status or not me_res.get("ok"):
            return jsonify({"ok": False, "error": "Telegram bot settings could not be verified. Check the backend connection and bot configuration."}), 502
        cmd_status, cmd_res = _bot_api("getMyCommands", {})
        menu_status, menu_res = _bot_api("getChatMenuButton", {})
        warnings = []
        if not cmd_status or not cmd_res.get("ok"):
            warnings.append("Telegram command list is unavailable")
        if not menu_status or not menu_res.get("ok"):
            warnings.append("Telegram menu button is unavailable")
        return jsonify({
            "ok": True,
            "bot": me_res.get("result"),
            "commands": cmd_res.get("result", []) if cmd_status and cmd_res.get("ok") else None,
            "menu_button": menu_res.get("result", {}) if menu_status and menu_res.get("ok") else None,
            "warnings": warnings,
            "webapp_url": getattr(config, "WEBAPP_URL", ""),
        })
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "A JSON object is required"}), 400
    action = str(body.get("action", "")).strip()
    if action == "set_menu_button":
        from urllib.parse import urlparse
        url = str(body.get("webapp_url") or getattr(config, "WEBAPP_URL", "")).strip()
        text = str(body.get("button_text") or "Videl Studio").strip()[:32]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            return jsonify({"ok": False, "error": "WebApp URL must be a valid HTTPS URL"}), 400
        status, res = _bot_api("setChatMenuButton", {
            "menu_button": {"type": "web_app", "text": text, "web_app": {"url": url}}
        })
        if not status or not res.get("ok"):
            return jsonify({"ok": False, "error": res.get("description", "Failed to update menu button")}), 502
        return jsonify({"ok": True, "webapp_url": url, "button_text": text})
    if action == "sync_commands":
        from videl.utils.bot_commands import command_menu
        default_cmds = command_menu()
        status, res = _bot_api("setMyCommands", {"commands": default_cmds})
        if not status or not res.get("ok"):
            return jsonify({"ok": False, "error": res.get("description", "Failed to sync commands")}), 502
        return jsonify({"ok": True, "synced": len(default_cmds)})
    return jsonify({"ok": False, "error": "Unsupported bot-settings action"}), 400

@_flask.route("/api")
@_flask.route("/api/")
def _api_index():
    return jsonify({
        "ok": True,
        "service": "videl-render-backend",
        "health": "/health",
        "webapp": getattr(config, "WEBAPP_URL", ""),
        "note": "Owner operations are available only through the authenticated Vercel control panel.",
    }), 200

def _log_all_urls_console():
    try:
        LOGGER.info("Flask Render backend routes:")
        for rule in _flask.url_map.iter_rules():
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            LOGGER.info("  • %-32s [%s]", rule.rule, methods)
    except Exception:
        LOGGER.debug("Flask route map logging failed", exc_info=True)

def _run_flask():
    from waitress import serve
    LOGGER.info("Videl production WSGI backend listening on 0.0.0.0:%s", BACKEND_PORT)
    _log_all_urls_console()
    serve(_flask, host="0.0.0.0", port=BACKEND_PORT, threads=8, channel_timeout=30, ident="Videl")

def _keep_alive():
    """Ping Render's public health route and publish a secret-free heartbeat."""
    url = os.getenv("RENDER_EXTERNAL_URL", f"http://127.0.0.1:{os.getenv('PORT', config.PORT)}")
    public = os.getenv("RENDER_EXTERNAL_URL", "https://videl0.onrender.com")
    target = public if public.startswith("http") else url
    while True:
        try:
            response = requests.get(target.rstrip("/") + "/health", timeout=10)
            response.raise_for_status()
            _KEEPALIVE_STATE["last_success"] = int(time.time())
            _KEEPALIVE_STATE["consecutive_failures"] = 0
            _KEEPALIVE_STATE["last_error"] = None
        except Exception as error:
            _KEEPALIVE_STATE["consecutive_failures"] += 1
            _KEEPALIVE_STATE["last_error"] = type(error).__name__
            LOGGER.warning("[keepalive] health ping failed (%s)", type(error).__name__)
        time.sleep(300)

if __name__ == "__main__":
    # Mongo
    try:
        from videl.utils.db import start_mongo
        start_mongo()
    except Exception as e:
        LOGGER.warning(f"mongo: {e}")

    threading.Thread(target=_run_flask, daemon=True).start()
    _KEEPALIVE_THREAD = threading.Thread(target=_keep_alive, name="videl-render-keepalive", daemon=True)
    _KEEPALIVE_THREAD.start()
    LOGGER.info(f"Render backend health on {BACKEND_PORT} — Vercel frontend URL: {getattr(config, 'WEBAPP_URL', 'not configured')}")

    missing = [k for k in ("API_ID","API_HASH","BOT_TOKEN","MONGO_DB_URL") if not os.getenv(k)]
    if missing:
        LOGGER.warning(f"Missing env: {missing} — bot in health-only mode, webapp still serves")

    # ── Bot with full logs (start/stop/error/other) ──────────────────────
    async def _boot():
        # setup shutdown/error hooks inside event loop
        import signal as _sig
        from videl.utils.logger import log_startup, log_shutdown, log_error, setup_async_error_handler

        loop = asyncio.get_running_loop()
        global _BOT_LOOP, _BOT_STATUS, _BOT_ERROR, _BOT_ONLINE_AT
        _BOT_LOOP = loop
        setup_async_error_handler(bot, loop)

        # graceful shutdown handler
        _shutting = False
        def _sig_handler(sig, frame):
            nonlocal _shutting
            if _shutting: return
            _shutting = True
            LOGGER.info(f"Signal {sig} — shutting down...")
            try:
                # schedule async log_shutdown
                asyncio.run_coroutine_threadsafe(log_shutdown(bot, f"signal {sig}"), loop)
            except: pass

        try:
            for s in (_sig.SIGINT, _sig.SIGTERM):
                signal.signal(s, _sig_handler)
        except Exception:
            pass  # not in main thread on some runners

        # Keep voice commands from racing the user-client startup. A session
        # string is credentials, not proof that its Client is connected.
        from videl.utils.assistant import assistant_starting, assistant_startup_complete, start_voice_engine
        assistant_starting()

        # Start the bot, retrying. A failed start delivered nothing, so trying
        # again is safe; what is not safe is giving up and waiting for a human.
        from videl.utils import boot as boot_policy
        from videl.utils.alerts import notify

        global _BOT_ATTEMPTS
        previous_kind = None
        while True:
            _BOT_ATTEMPTS += 1
            try:
                await bot.start()
                me = await bot.get_me()
                break
            except Exception as e:
                kind = boot_policy.classify(e)
                delay = boot_policy.retry_delay_for_error(_BOT_ATTEMPTS, e)
                _BOT_STATUS = "failed"
                _BOT_ERROR = _health_text(e) or type(e).__name__
                LOGGER.error("bot.start attempt %s failed (%s): %s — retrying in %ss",
                             _BOT_ATTEMPTS, kind, e, delay)
                try:
                    await log_error(bot, "bot.start", e, "startup")
                except Exception:
                    pass
                if boot_policy.should_alert(_BOT_ATTEMPTS, kind, previous_kind):
                    await asyncio.to_thread(
                        notify,
                        f"The bot could not start: <code>{_BOT_ERROR}</code>\n"
                        f"{boot_policy.describe(kind)}. The panel and API stay up.",
                        title="Bot start failed",
                    )
                previous_kind = kind
                # A half-open client would make the next attempt misleading.
                try:
                    await bot.stop()
                except Exception:
                    pass
                await asyncio.sleep(delay)

        _BOT_STATUS = "online"
        _BOT_ERROR = ""
        _BOT_ONLINE_AT = int(time.time())
        if _BOT_ATTEMPTS > 1:
            LOGGER.info("Bot @%s started after %s attempts", me.username, _BOT_ATTEMPTS)
            await asyncio.to_thread(
                notify,
                f"Bot @{me.username} is back online after {_BOT_ATTEMPTS} start attempts.",
                title="Bot recovered",
            )
        else:
            LOGGER.info(f"Bot @{me.username} started")

        # assistant (userbot) optional
        assistant_username = ""
        try:
            from videl import assistant as _assis
            session_value = config.STRING_SESSION or ""
            if session_value:
                # Confirm the deployment secret is present without ever logging
                # any portion of the Telegram authorization string.
                LOGGER.info(
                    "Assistant STRING_SESSION is present (value masked; %d characters)",
                    len(session_value),
                )
                await _assis.start()
                am = await _assis.get_me()
                assistant_username = am.username or str(am.id)
                # PyTgCalls owns the actual voice-chat engine. Starting only the
                # Telegram user client leaves play() raising ClientNotStarted.
                await start_voice_engine()
                LOGGER.info("PyTgCalls voice engine started")
                assistant_startup_complete(True)
                LOGGER.info(f"Assistant @{assistant_username} started")
            else:
                assistant_startup_complete(False)
                LOGGER.warning("Assistant STRING_SESSION is missing; assistant disabled")
        except Exception as e:
            assistant_startup_complete(False)
            LOGGER.warning(f"assistant fail: {e}")
            try:
                await _assis.stop()
            except Exception:
                pass
            try:
                await log_error(bot, "assistant.start", e)
            except: pass

        # bot commands + WebApp menu button (single Vercel URL)
        try:
            from pyrogram.types import BotCommand, BotCommandScopeChat
            from videl.utils.bot_commands import command_menu
            await bot.set_bot_commands([BotCommand(**item) for item in command_menu()])
            if config.OWNER_ID:
                try:
                    await bot.set_bot_commands([BotCommand(**item) for item in command_menu(owner=True)],
                                               scope=BotCommandScopeChat(chat_id=config.OWNER_ID))
                except Exception:
                    LOGGER.info("Owner command menu will be available after the owner starts the bot")
        except Exception:
            pass
        try:
            webapp_root = (getattr(config, "WEBAPP_URL", "") or "").strip().rstrip("/")
            if webapp_root.startswith("https://"):
                await asyncio.to_thread(_bot_api, "setChatMenuButton", {
                    "menu_button": {"type": "web_app", "text": "👑 Videl Studio", "web_app": {"url": webapp_root}}
                })
        except Exception:
            pass

        # Startup log to LOGGER_ID (Rich)
        try:
            from videl.utils.db import _db
            await log_startup(bot, me, assistant_username=assistant_username, mongo_ok=bool(_db is not None))
        except Exception as e:
            LOGGER.debug(f"log_startup skip: {e}")

        # Load modules
        for mod in ALL_MODULES:
            try:
                importlib.import_module(f"videl.modules.{mod}")
                LOGGER.info(f"Loaded {mod}")
            except Exception as e:
                LOGGER.error(f"Failed {mod}: {e}")
                try:
                    await log_error(bot, f"load {mod}", e)
                except: pass

        from videl.utils.captcha import start_captcha_worker
        start_captcha_worker()
        from videl.core.watcher import start_watchdog
        start_watchdog()

        try:
            from videl.plugins.reminder import restore_pending_reminders
            restored = await restore_pending_reminders()
            LOGGER.info("Restored %s pending MongoDB reminders", restored)
        except Exception:
            LOGGER.exception("Pending reminders could not be restored")

        LOGGER.info("Videl bot + Render API are running; Vercel hosts the web control panel")
        # idle with shutdown log
        try:
            r = idle()
            if hasattr(r, "__await__"):
                await r
        except TypeError:
            await asyncio.Event().wait()
        finally:
            _BOT_STATUS = "stopping"
            from videl.core.watcher import stop_watchdog
            await stop_watchdog()
            from videl.utils.captcha import stop_captcha_worker
            await stop_captcha_worker()
            try:
                await log_shutdown(bot, "idle exit")
            except: pass
            LOGGER.info("Bot idle exited — shutting down")
            try:
                await bot.stop()
            except: pass
            try:
                from videl import assistant as _assis
                await _assis.stop()
            except: pass

    def _run():
        try:
            asyncio.get_event_loop().run_until_complete(_boot())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_boot())
        except Exception as e:
            LOGGER.error(f"boot fail: {e} — health and backend API remain alive")
            try:
                # try log to channel if bot was up
                import asyncio as _a
                _a.run(log_error(bot, "boot", e))
            except: pass
            while True:
                time.sleep(3600)

    _run()
