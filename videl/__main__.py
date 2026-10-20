# Videl — Unified Server — Bot + WebApp on ONE Render URL
# https://videl0.onrender.com        → bot + webapp
# https://videl0.onrender.com/api    → API index
# https://videl0.onrender.com/dashboard → dashboard
# https://videl0.onrender.com/chat   → web chat (chat as bot)
# https://videl0.onrender.com/post   → channel post maker
# All on single PORT (Render $PORT = 10000), Flask owns $PORT, proxies to Next.js :3000
import asyncio
import importlib
import os
import signal
import subprocess
import threading
import time
import logging
import requests
from flask import Flask, jsonify, request, Response, redirect
from pyrogram import idle
import config
from videl import LOGGER, bot
from videl.modules import ALL_MODULES

NEXT_PORT = int(os.getenv("NEXT_PORT", "3000"))
NEXT_URL = f"http://127.0.0.1:{NEXT_PORT}"

_flask = Flask(__name__)
_next_proc = None

# ── Bot health + API index ───────────────────────────────────────────────
# FIXED: "/" now serves Telegram Mini App (Next.js), NOT JSON — perfect for BotFather
@_flask.route("/_videl_status")
def _status_json():
    return jsonify({
        "service": "Videl Unified",
        "status": "running",
        "bot": getattr(config, "BOT_USERNAME", "Videl0Bot"),
        "webapp": f"{request.host_url.rstrip('/')}/",
        "miniapp_url": f"{request.host_url.rstrip('/')}/",
        "dashboard": f"{request.host_url.rstrip('/')}/dashboard",
        "endpoints": {
            "health": "/health",
            "api": "/api",
            "dashboard": "/dashboard",
        }
    }), 200

@_flask.route("/health")
def _health():
    return jsonify({"status": "ok", "service": "videl-unified", "uptime": int(time.time())}), 200

@_flask.route("/api")
@_flask.route("/api/")
def _api_index():
    return jsonify({
        "ok": True,
        "service": "videl-api",
        "endpoints": {
            "/api/health": "health check",
            "/api/stats": "bot stats (MongoDB)",
            "/api/channel": "POST {chat_id,text,parse_mode,media_url,buttons} → send to TG channel",
            "/api/chat": "POST {chat_id,text,as_user} → send as bot/userbot",
            "/api/auth": "POST TG login verify owner",
            "/api/gbans": "global bans",
            "/api/queue": "music queue",
            "/api/analytics": "analytics series",
        },
        "webapp": ["/", "/dashboard", "/dashboard/channel", "/dashboard/chat", "/chat", "/post"],
        "miniapp": "/  ← USE THIS FOR BOTFATHER MINI APP URL",
        "note": "All on ONE Render URL — https://videl0.onrender.com"
    }), 200

@_flask.route("/api/health")
def _api_health_proxy():
    return _health()

# ── Aliases — unified, no redirect visible (proxy direct to Next.js) ─────
@_flask.route("/chat")
@_flask.route("/chat/")
def _chat_page():
    proxied = _proxy_to_next("/chat")
    if proxied is not None:
        return proxied
    return redirect("/dashboard/chat", 302)

@_flask.route("/post")
@_flask.route("/post/")
def _post_page():
    proxied = _proxy_to_next("/post")
    if proxied is not None:
        return proxied
    return redirect("/dashboard/channel", 302)

# ── Proxy to Next.js for webapp ─────────────────────────────────────────
def _is_next_available():
    try:
        requests.get(f"{NEXT_URL}/api/health", timeout=1.5)
        return True
    except:
        return False

def _proxy_to_next(path: str):
    """Proxy any request to Next.js standalone server."""
    if not _is_next_available():
        return None
    try:
        url = f"{NEXT_URL}{path}"
        # forward query string
        if request.query_string:
            url += f"?{request.query_string.decode()}"
        headers = {k: v for k, v in request.headers if k.lower() not in ("host", "connection", "content-length")}
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=15,
        )
        # Build Flask response
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        hdrs = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        return Response(resp.content, status=resp.status_code, headers=dict(hdrs))
    except Exception as e:
        LOGGER.warning(f"proxy fail {path}: {e}")
        return None

# Catch-all proxy for Next.js assets & pages
# Must be after explicit bot routes to avoid shadowing /health
@_flask.route("/dashboard", defaults={"path": ""})
@_flask.route("/dashboard/<path:path>")
@_flask.route("/auth", defaults={"path": ""})
@_flask.route("/auth/<path:path>")
@_flask.route("/_next/<path:path>")
@_flask.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def _proxy_catchall(path=""):
    # /api/* should try Next.js first, else Flask fallback
    full = request.path
    proxied = _proxy_to_next(full)
    if proxied is not None:
        return proxied
    # Flask fallback for /api if Next.js not running
    if full.startswith("/api/"):
        return jsonify({"ok": False, "error": "API via Next.js not available — Next.js building/starting. Try /health or check logs.", "path": full}), 503
    if full.startswith("/dashboard") or full.startswith("/auth") or full.startswith("/_next"):
        return jsonify({"ok": False, "error": "Webapp starting — Next.js on :3000 not ready yet", "hint": "wait 20s, refresh /dashboard"}), 503
    return jsonify({"ok": False, "error": "not found", "path": full}), 404

# ── MINI APP ROOT — THE MOST IMPORTANT FIX FOR TELEGRAM ───────────────────
# This is what BotFather should point to — serves Next.js Home as Mini App
@_flask.route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def _home_miniapp():
    proxied = _proxy_to_next("/")
    if proxied is not None:
        return proxied
    # Fallback while Next.js boots
    return jsonify({
        "ok": True,
        "service": "Videl Mini App",
        "message": "WebApp building — refresh in 15s",
        "miniapp_url": f"{request.host_url.rstrip('/')}/",
        "dashboard": f"{request.host_url.rstrip('/')}/dashboard",
        "health": f"{request.host_url.rstrip('/')}/health",
        "note": "If you see this JSON, Next.js is still building. Wait 20s and refresh."
    }), 503

# Also proxy bare /api subpaths that Flask didn't match (already above)
@_flask.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def _fallback_proxy(path):
    # Proxy ALL webapp paths — including "/" already handled above
    # Prioritize Next.js for these prefixes
    if path.startswith(("_next/", "dashboard/", "auth/", "api/", "chat", "post", "groups", "analytics", "automation", "settings")):
        proxied = _proxy_to_next(f"/{path}")
        if proxied is not None:
            return proxied
        # if Next not ready yet
        if path.startswith(("chat", "post", "dashboard", "_next", "groups", "analytics")):
            return jsonify({"ok": False, "error": "Webapp starting — Next.js on :3000 booting", "hint": "refresh in 15s"}), 503
    # Also try to proxy unknown paths to Next.js (for client-side routing)
    proxied = _proxy_to_next(f"/{path}")
    if proxied is not None:
        return proxied
    return jsonify({"ok": False, "error": "not found", "path": f"/{path}", "see": "/api", "hint": "Try / or /dashboard for Mini App"}), 404

def _log_all_urls_console():
    """Log ALL URLs to console on startup"""
    try:
        from videl.utils.url_logger import log_urls_sync
        log_urls_sync()
    except Exception as e:
        LOGGER.warning(f"URL console log fail: {e}")
    # Also detailed Flask URL map
    try:
        LOGGER.info("◎ Flask URL Map — All Registered Routes:")
        for rule in _flask.url_map.iter_rules():
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            LOGGER.info(f"  • {rule.rule:<30} → [{methods}]")
    except Exception as e:
        LOGGER.debug(f"Flask URL map log fail: {e}")

def _run_flask():
    port = int(os.getenv("PORT", str(config.PORT)))
    LOGGER.info(f"◎ Flask Unified — ALL URLs startup logger armed")
    _log_all_urls_console()
    LOGGER.info(f"Flask unified on 0.0.0.0:{port} → proxy → Next.js :{NEXT_PORT}")
    _flask.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)

def _start_nextjs():
    global _next_proc
    # Only if webapp built
    webapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")
    standalone = os.path.join(webapp_dir, ".next/standalone/server.js")
    standalone_alt = os.path.join(webapp_dir, "server.js")
    pkg = os.path.join(webapp_dir, "package.json")
    if not os.path.exists(pkg):
        LOGGER.info("webapp not present — skipping Next.js")
        return
    # Build if not built
    next_built = os.path.join(webapp_dir, ".next/BUILD_ID")
    if not os.path.exists(next_built):
        LOGGER.info("webapp not built — building Next.js (this takes 30s)...")
        try:
            subprocess.run(["npm", "ci"], cwd=webapp_dir, timeout=120, check=False)
            subprocess.run(["npm", "run", "build"], cwd=webapp_dir, timeout=180, check=False)
        except Exception as e:
            LOGGER.warning(f"Next build fail: {e}")
    # Try standalone first
    cmd = None
    if os.path.exists(standalone):
        cmd = ["node", standalone]
        cwd = os.path.join(webapp_dir, ".next/standalone")
    elif os.path.exists(standalone_alt):
        cmd = ["node", standalone_alt]
        cwd = webapp_dir
    else:
        # fallback next start
        cmd = ["npx", "next", "start", "-p", str(NEXT_PORT), "-H", "0.0.0.0"]
        cwd = webapp_dir
    try:
        env = os.environ.copy()
        env["PORT"] = str(NEXT_PORT)
        env["NEXT_PORT"] = str(NEXT_PORT)
        env["HOSTNAME"] = "0.0.0.0"
        LOGGER.info(f"Starting Next.js: {' '.join(cmd)} in {cwd}")
        _next_proc = subprocess.Popen(cmd, cwd=cwd, env=env)
        LOGGER.info(f"Next.js pid {_next_proc.pid} on :{NEXT_PORT}")
        # wait briefly to confirm
        for _ in range(15):
            time.sleep(1)
            if _is_next_available():
                LOGGER.info("Next.js ready ✅")
                break
        else:
            LOGGER.warning("Next.js not responding yet — will retry via proxy")
    except Exception as e:
        LOGGER.warning(f"Next.js start fail: {e}")

def _keep_alive():
    # keep-alive ping self (Render free tier sleep prevention)
    url = os.getenv("RENDER_EXTERNAL_URL", f"http://127.0.0.1:{os.getenv('PORT', config.PORT)}")
    # use public URL if available, else localhost
    public = os.getenv("RENDER_EXTERNAL_URL", "https://videl0.onrender.com")
    target = public if public.startswith("http") else url
    while True:
        try:
            requests.get(target + "/health", timeout=10)
            # also tickle Next.js via proxy path
            try:
                requests.get(target + "/api/health", timeout=10)
            except: pass
        except: pass
        time.sleep(300)

if __name__ == "__main__":
    # Mongo
    try:
        from videl.utils.db import start_mongo
        start_mongo()
    except Exception as e:
        LOGGER.warning(f"mongo: {e}")

    # Start Next.js in background thread (non-blocking) if webapp present
    threading.Thread(target=_start_nextjs, daemon=True).start()
    threading.Thread(target=_run_flask, daemon=True).start()
    threading.Thread(target=_keep_alive, daemon=True).start()
    LOGGER.info(f"Unified health on {config.PORT} — /health OK, proxy to :{NEXT_PORT}")

    missing = [k for k in ("API_ID","API_HASH","BOT_TOKEN","MONGO_DB_URL") if not os.getenv(k)]
    if missing:
        LOGGER.warning(f"Missing env: {missing} — bot in health-only mode, webapp still serves")

    # ── Bot with full logs (start/stop/error/other) ──────────────────────
    async def _boot():
        # setup shutdown/error hooks inside event loop
        import signal as _sig
        from videl.utils.logger import log_startup, log_shutdown, log_error, setup_async_error_handler

        loop = asyncio.get_running_loop()
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
            LOGGER.error(f"bot.start fail: {e}")
            try:
                await log_error(bot, "bot.start", e, "startup")
            except: pass
            # keep Flask + Next.js alive even if bot fails
            LOGGER.info("Bot failed — health+webapp still running")
            while True:
                await asyncio.sleep(3600)
            return

        me = await bot.get_me()
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

        # bot commands (include logs + unified)
        try:
            from pyrogram.types import BotCommand
            await bot.set_bot_commands([
                BotCommand("start","Start"),
                BotCommand("help","Help"),
                BotCommand("ping","Ping"),
                BotCommand("logs","Owner logs (start/stop/error)"),
                BotCommand("sysinfo","System info"),
                BotCommand("uptime","Uptime"),
            ])
        except: pass

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

        LOGGER.info("Videl unified running — bot + webapp + Flask idle")
        # idle with shutdown log
        try:
            r = idle()
            if hasattr(r, "__await__"):
                await r
        except TypeError:
            await asyncio.Event().wait()
        finally:
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
            LOGGER.error(f"boot fail: {e} — health+webapp still alive")
            try:
                # try log to channel if bot was up
                import asyncio as _a
                _a.run(log_error(bot, "boot", e))
            except: pass
            while True:
                time.sleep(3600)

    _run()
