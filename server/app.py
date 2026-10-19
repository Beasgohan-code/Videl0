"""
◍ Vɪᴅᴇʟ — Keep-Alive & Webhook • Cyber Dark Perfected
FastAPI — / • /health • /ping • /stats • /webhook  • single PORT via KEEPALIVE_PORT
"""
import os, time, asyncio, logging
from pathlib import Path
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).parent.parent
start_time = time.time()
log = logging.getLogger("videl.server")

app = FastAPI(title="◍ Vɪᴅᴇʟ — Keep-Alive", version="2.0.0", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

_bot = None; _dp = None
def _get_bot_dp():
    global _bot, _dp
    if _bot and _dp: return _bot, _dp
    try:
        from bot.main import create_bot, create_dispatcher
        _bot = create_bot(); _dp = create_dispatcher()
        return _bot, _dp
    except Exception as e:
        log.warning(f"bot init fail: {e}")
        return None, None

# ── ◍ Cyber Dark HTML — minimal mono, dark only ───────────────────────────────
PAGE = """\
<html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>◍ Vɪᴅᴇʟ — Online</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0a0a0a;color:#e8e8e8;padding:40px;max-width:760px;margin:auto;line-height:1.6}
  a{color:#9ab7ff;text-decoration:none;border-bottom:1px solid #2a2a2a} a:hover{border-color:#9ab7ff}
  .card{background:#111;border:1px solid #222;border-radius:16px;padding:20px;margin:16px 0}
  .pill{display:inline-flex;gap:6px;align-items:center;background:#1a1a1a;border:1px solid #2a2a2a;border-radius:999px;padding:6px 12px;font-size:12px}
  .dot{width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1} 50%{opacity:.5}}
  h1{font-size:14px;letter-spacing:.12em;text-transform:uppercase;color:#888}
  h1 span{color:#fff;font-weight:700}
  h3{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#999;margin-bottom:8px}
  code{background:#1e1e1e;border:1px solid #2a2a2a;padding:2px 6px;border-radius:6px;font-size:12px}
  ul{list-style:none} li{padding:6px 0;border-bottom:1px solid #111} li:last-child{border:0}
  .mono{font-variant-ligatures:none}
</style></head><body>
<h1><span>◍ Vɪᴅᴇʟ</span> ⫶ ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ ⬪ ᴄʏʙᴇʀ ᴅᴀʀᴋ</h1>
<div class="card">
  <div class="pill"><span class="dot"></span> ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ ⫶ {up} ⬪ ᴀʟʟ sʏsᴛᴇᴍs ᴘᴇʀғᴇᴄᴛ</div>
  <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:8px;font-size:13px">
    <a href="/health">⬪ ʜᴇᴀʟᴛʜ</a> <a href="/ping">⫶ ᴘɪɴɢ</a> <a href="/stats">◎ sᴛᴀᴛs</a> <a href="/docs">⬢ ᴅᴏᴄs</a>
    <a href="https://hosting-bot-dashboard.vercel.app">◍ ᴅᴀsʜʙᴏᴀʀᴅ</a>
  </div>
  <div style="margin-top:12px;font-size:12px;color:#888">
    <code>POST /webhook</code> — ᴠᴇʀᴄᴇʟ ᴡᴇʙʜᴏᴏᴋ ⫶ <code>GET /keepalive</code> — ᴡᴀᴛᴄʜᴅᴏɢ ᴘɪɴɢ
  </div>
</div>
<div class="card">
  <h3>⬪ ғᴇᴀᴛᴜʀᴇs ⬪</h3>
  <ul class="mono" style="font-size:13px;color:#bbb">
    <li>◍ ᴍᴜsɪᴄ — ᴠᴄ sᴛʀᴇᴀᴍɪɴɢ ⫶ ǫᴜᴇᴜᴇ ⫶ ʟʏʀɪᴄs</li>
    <li>⬪ ᴀɪ ᴄʜᴀᴛ — ᴏᴘᴇɴᴀɪ ⫶ ɢʀᴏǫ ⫶ ɢᴇᴍɪɴɪ</li>
    <li>⫶ ᴜᴛɪʟɪᴛʏ — ᴡᴇᴀᴛʜᴇʀ ⫶ ǫʀ ⫶ ᴄᴀʀʙᴏɴ ⫶ ɢɪᴛ</li>
    <li>◎ ᴀᴅᴍɪɴ — ʙᴀɴ ⫶ ᴍᴜᴛᴇ ⫶ ᴡᴀʀɴ ⫶ ʟᴏᴄᴋ ⫶ ɢʙᴀɴ</li>
    <li>⬢ ᴏᴘs — ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ ⫶ ᴡᴀᴛᴄʜᴅᴏɢ ⫶ ʟᴏɢs ⫶ ᴅʀᴏᴘʙᴏx</li>
  </ul>
</div>
<div class="card" style="font-size:12px;color:#666">
  ᴍᴀᴅᴇ ᴡɪᴛʜ ◍ ʙʏ <a href="https://github.com/Beasgohan-code">ʙᴇᴀsɢᴏʜᴀɴ-ᴄᴏᴅᴇ</a> ⫶ ʙᴀsᴇᴅ ᴏɴ <a href="https://github.com/Badmunda05/richgram">ʀɪᴄʜɢʀᴀᴍ</a> & <a href="https://github.com/Badmunda05/ShizuMusic">sʜɪᴢᴜ</a> ⬪ ᴄʏʙᴇʀ ᴅᴀʀᴋ ᴘᴇʀғᴇᴄᴛ
</div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    h, rem = divmod(int(time.time() - start_time), 3600); m, s = divmod(rem, 60)
    up = f"{h}ʜ {m}ᴍ {s}s"
    return PAGE.format(up=up)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Videl", "cyber_dark": True, "uptime": int(time.time()-start_time), "version": "2.0.0-perfect"}

@app.get("/ping")
async def ping():
    t0 = time.time(); ok = True
    try:
        from bot.database import db
        await db.get_stats()
    except: ok = False
    return {"ok": ok, "ping_ms": int((time.time()-t0)*1000), "uptime": int(time.time()-start_time)}

@app.get("/stats")
async def stats():
    try:
        from bot.database import db
        s = await db.get_stats()
        return {"bot": "Videl", "cyber_dark": True, "stats": s, "uptime": int(time.time()-start_time)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/keepalive")
async def keepalive():
    return {"alive": True, "ts": int(time.time()), "cyber_dark": "◍ ⬪ ⫶ perfect"}

@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    from bot.config import WEBHOOK_SECRET
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret ⫶ forbidden ◍")
    try:
        data = await request.json()
        b, dp = _get_bot_dp()
        if not b or not dp:
            return JSONResponse({"ok": False, "error": "bot not initialized — check .env"}, status_code=503)
        from bot.main import feed_webhook_update
        try: await b.get_me()
        except: pass
        await feed_webhook_update(b, dp, data)
        return {"ok": True}
    except Exception as e:
        log.exception(f"webhook fail: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.on_event("startup")
async def on_startup():
    log.info("◍ Vɪᴅᴇʟ keep-alive — cyber dark perfect ⬪")

if __name__ == "__main__":
    import uvicorn
    # FastAPI keep-alive NEVER uses main PORT — always KEEPALIVE_PORT to avoid clash with videl Flask
    port = int(os.getenv("KEEPALIVE_PORT", os.getenv("PORT_KEEPALIVE", "8000")))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)
