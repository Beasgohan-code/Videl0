"""
Videl0 • Keep-Alive Server — FastAPI
Provides /health, /ping, /stats, /webhook for aiogram.
Runs on 0.0.0.0:PORT for Render/Koyeb/Vercel compat.
"""
import os, time, asyncio, logging
from pathlib import Path
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).parent.parent
start_time = time.time()
log=logging.getLogger("videl.server")

app = FastAPI(title="Videl0 • Keep-Alive & Webhook", version="2.0.0", docs_url="/docs", redoc_url="/redoc")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# bot lazy init for webhook
_bot=None; _dp=None
def _get_bot_dp():
    global _bot, _dp
    if _bot and _dp: return _bot, _dp
    try:
        from bot.main import create_bot, create_dispatcher
        _bot=create_bot(); _dp=create_dispatcher()
        return _bot, _dp
    except Exception as e:
        log.warning(f"bot init fail: {e}")
        return None, None

@app.get("/", response_class=HTMLResponse)
async def root():
    uptime=int(time.time()-start_time)
    h,rem=divmod(uptime,3600); m,s=divmod(rem,60)
    return f"""
    <html><head><title>Videl0 — Online</title><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      body{{font-family:ui-sans-serif,system-ui;background:#0a0a0a;color:#eee;padding:40px;max-width:700px;margin:auto}}
      .card{{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;padding:24px;margin:16px 0}}
      a{{color:#60a5fa}} code{{background:#222;padding:2px 6px;border-radius:6px}}
      h1{{background:linear-gradient(90deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    </style></head><body>
    <h1>✨ Videl0 — Telegram Bot API 10.3</h1>
    <p>aiogram 3.31 • Richgram • ShizuMusic • Supabase • Dropbox • Vercel</p>
    <div class="card">
      <h3>✅ Bot is Online</h3>
      <p>Uptime: <code>{h}h {m}m {s}s</code></p>
      <p>Health: <a href="/health">/health</a> • Ping: <a href="/ping">/ping</a> • Stats: <a href="/stats">/stats</a> • Docs: <a href="/docs">/docs</a></p>
      <p>Webhook: <code>/webhook</code> (POST) — set via WEBHOOK_URL in .env</p>
      <p>Dashboard: <a href="https://hosting-bot-dashboard.vercel.app">Vercel Dashboard</a></p>
    </div>
    <div class="card">
      <h3>🎵 Features</h3>
      <ul>
        <li>🎶 Music — VC streaming via pytgcalls + yt-dlp queue</li>
        <li>🤖 AI Chat — OpenAI / Groq / Gemini with history</li>
        <li>🧰 Utility — weather, qr, calc, wiki, git, carbon…</li>
        <li>🛡️ Group — ban/mute/warn/lock/purge/welcome/filters/notes</li>
        <li>👑 Owner — broadcast, gban, eval, backup to Dropbox</li>
        <li>🔔 Logs — LOG_CHANNEL + keep-alive watchdog</li>
      </ul>
    </div>
    <div class="card"><p>Made with ❤️ by Beasgohan-code — based on <a href="https://github.com/Badmunda05/richgram">Richgram</a> & <a href="https://github.com/Badmunda05/ShizuMusic">ShizuMusic</a></p></div>
    </body></html>
    """

@app.get("/health")
async def health():
    return {"status":"ok","service":"Videl0","uptime":int(time.time()-start_time),"version":"2.0.0"}

@app.get("/ping")
async def ping():
    t0=time.time()
    # db check
    ok=True
    try:
        from bot.database import db
        await db.get_stats()
    except: ok=False
    return {"ok": ok, "ping_ms": int((time.time()-t0)*1000), "uptime": int(time.time()-start_time)}

@app.get("/stats")
async def stats():
    try:
        from bot.database import db
        s=await db.get_stats()
        return {"bot":"Videl0","stats":s,"uptime":int(time.time()-start_time)}
    except Exception as e: return {"error": str(e)}

@app.get("/keepalive")
async def keepalive():
    return {"alive": True, "ts": int(time.time())}

@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    from bot.config import WEBHOOK_SECRET
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    try:
        data=await request.json()
        bot, dp = _get_bot_dp()
        if not bot or not dp:
            return JSONResponse({"ok": False, "error": "bot not initialized"}, status_code=503)
        from bot.main import feed_webhook_update
        # ensure bot started
        try:
            me=await bot.get_me()
        except: pass
        await feed_webhook_update(bot, dp, data)
        return {"ok": True}
    except Exception as e:
        log.exception(f"webhook fail: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.on_event("startup")
async def on_startup():
    log.info("FastAPI keep-alive up")

if __name__ == "__main__":
    import uvicorn
    port=int(os.getenv("PORT","8000"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)
