# Videl — Render backend: Telegram bot + private Flask API.
# Next.js frontend lives on Vercel and calls this backend over HTTPS.
import asyncio
import importlib
import os
import signal
import threading
import time
import logging
import hmac
import requests
from flask import Flask, jsonify, request
from pyrogram import idle
import config
from videl import LOGGER, bot
from videl.modules import ALL_MODULES

BACKEND_PORT = int(os.getenv("PORT", str(config.PORT)))

_flask = Flask(__name__)
_BOT_LOOP = None
_BOT_STATUS = "starting"

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


# ── Render backend health and service metadata ───────────────────────────
@_flask.route("/")
@_flask.route("/_videl_status")
def _status_json():
    return jsonify({
        "service": "Videl Render backend",
        "status": "running",
        "bot": getattr(config, "BOT_USERNAME", "Videl0Bot"),
        "webapp": getattr(config, "WEBAPP_URL", ""),
        "health": "/health",
        "api_index": "/api",
    }), 200

@_flask.route("/health")
def _health():
    from videl import bot_start_time
    return jsonify({"status": "ok", "service": "videl-render-backend", "bot_status": _BOT_STATUS, "uptime": max(0, int(time.time() - bot_start_time))}), 200

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
    owner_id = str(getattr(config, "OWNER_ID", "") or "")
    if not token or not owner_id:
        return jsonify({"ok": False, "error": "Telegram owner authentication is not configured"}), 503
    try:
        init_data = body.get("init_data", "")
        login_widget = body.get("login_widget")
        if isinstance(init_data, str) and init_data and len(init_data) <= 8192:
            fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
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
        if str(user.get("id", "")) != owner_id:
            return jsonify({"ok": False, "error": "This control panel is restricted to the configured bot owner"}), 403
        return jsonify({"ok": True, "user": {key: user.get(key) for key in ("id", "first_name", "username") if user.get(key) is not None}})
    except (ValueError, TypeError, json.JSONDecodeError):
        return jsonify({"ok": False, "error": "Invalid Telegram authentication data"}), 401

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
    from videl.utils.post_format import post_text_length
    text_length = post_text_length(text, parse_mode)
    if text_length > 4096:
        return jsonify({"ok": False, "error": "Post text is limited to 4096 visible characters"}), 400
    method = "sendMessage"
    payload = {"chat_id": chat_id, "parse_mode": parse_mode}
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
                    label = str(item.get("text", "")).strip()
                    url = str(item.get("url", item.get("href", ""))).strip()
                    parsed = urlparse(url)
                    if not label or len(label) > 64 or parsed.scheme not in ("https", "http") or not parsed.netloc:
                        raise ValueError("buttons need a label and valid http(s) URL")
                    normalized.append({"text": label, "url": url})
                keyboard.append(normalized)
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        except (ValueError, TypeError, AttributeError) as exc:
            return jsonify({"ok": False, "error": f"Invalid button layout: {exc}"}), 400
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
                "bot_username": getattr(config, "BOT_USERNAME", "Videl0Bot"),
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
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        ids = [doc.get("_id") for doc in db["served_chats"].find({}, {"_id": 1}).limit(100)]
        setting_keys = ("lock_links", "lock_media", "lock_stickers", "antispam", "lock_forwards", "welcome_enabled")
        settings = {int(doc["chat_id"]): {k: bool(doc.get(k, False)) for k in setting_keys}
                    for doc in db["mgmt_chat_settings"].find({"chat_id": {"$in": ids}})}
        from concurrent.futures import ThreadPoolExecutor
        def enrich(chat_id):
            if not getattr(config, "BOT_TOKEN", ""):
                return {"id": chat_id, "title": f"Telegram chat {chat_id}", "type": "unknown", "members": None, "available": False}
            _, chat = _bot_api("getChat", {"chat_id": chat_id})
            _, members = _bot_api("getChatMemberCount", {"chat_id": chat_id})
            valid_chat = bool(chat and chat.get("ok"))
            result = chat.get("result", {}) if valid_chat else {}
            return {
                "id": chat_id,
                "title": result.get("title") or result.get("username") or f"Telegram chat {chat_id}",
                "username": result.get("username"),
                "type": result.get("type", "unknown"),
                "members": members.get("result") if members and members.get("ok") else None,
                "available": valid_chat,
            }
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(enrich, ids[:25]))
        for row in rows:
            try: row["settings"] = settings.get(int(row["id"]), {})
            except (TypeError, ValueError): row["settings"] = {}
        return jsonify({"ok": True, "chats": rows, "truncated": len(ids) > 25})
    except Exception:
        LOGGER.exception("internal group list query failed")
        return jsonify({"ok": False, "error": "group query failed"}), 503

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
        allowed = {"lock_links", "lock_media", "lock_stickers", "antispam", "lock_forwards", "welcome_enabled"}
        if not isinstance(settings, dict) or not settings or set(settings) - allowed or any(not isinstance(v, bool) for v in settings.values()):
            return jsonify({"ok": False, "error": "Only boolean protection and automation settings may be changed"}), 400
        from videl.utils.db import get_db
        db = get_db()
        if db is None:
            return jsonify({"ok": False, "error": "MongoDB is not connected"}), 503
        if db["served_chats"].find_one({"_id": chat_id}) is None:
            return jsonify({"ok": False, "error": "Chat is not in Videl's served group list"}), 404
        db["mgmt_chat_settings"].update_one({"chat_id": chat_id}, {"$set": settings}, upsert=True)
        return jsonify({"ok": True, "chat_id": chat_id, "settings": settings})
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
    LOGGER.info("Videl Render backend listening on 0.0.0.0:%s", BACKEND_PORT)
    _log_all_urls_console()
    _flask.run(host="0.0.0.0", port=BACKEND_PORT, use_reloader=False, threaded=True)

def _keep_alive():
    # keep-alive ping self (Render free tier sleep prevention)
    url = os.getenv("RENDER_EXTERNAL_URL", f"http://127.0.0.1:{os.getenv('PORT', config.PORT)}")
    # use public URL if available, else localhost
    public = os.getenv("RENDER_EXTERNAL_URL", "https://videl0.onrender.com")
    target = public if public.startswith("http") else url
    while True:
        try:
            requests.get(target + "/health", timeout=10)
        except: pass
        time.sleep(300)

if __name__ == "__main__":
    # Mongo
    try:
        from videl.utils.db import start_mongo
        start_mongo()
    except Exception as e:
        LOGGER.warning(f"mongo: {e}")

    threading.Thread(target=_run_flask, daemon=True).start()
    threading.Thread(target=_keep_alive, daemon=True).start()
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
        global _BOT_LOOP, _BOT_STATUS
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

        # Start bot
        try:
            await bot.start()
        except Exception as e:
            _BOT_STATUS = "failed"
            LOGGER.error(f"bot.start fail: {e}")
            try:
                await log_error(bot, "bot.start", e, "startup")
            except: pass
            # keep Flask backend alive even if the bot client fails
            LOGGER.info("Bot failed — health and backend API remain available")
            while True:
                await asyncio.sleep(3600)
            return

        me = await bot.get_me()
        _BOT_STATUS = "online"
        LOGGER.info(f"Bot @{me.username} started")

        # assistant (userbot) optional
        assistant_username = ""
        try:
            from videl import assistant as _assis
            if config.STRING_SESSION:
                await _assis.start()
                am = await _assis.get_me()
                assistant_username = am.username or str(am.id)
                LOGGER.info(f"Assistant @{assistant_username} started")
            else:
                LOGGER.info("No STRING_SESSION — assistant disabled")
        except Exception as e:
            LOGGER.warning(f"assistant fail: {e}")
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

        try:
            from videl.plugins.runtime import restore_pending_reminders
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
