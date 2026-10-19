# ◍ Vɪᴅᴇʟ ◍ — Perfect Production Music Bot

> **Cyber Dark • Kurigram + PyTgCalls • Bot API 10.3 Rich UI • Full-Stack**

⚡ Based on **Beasgohan-code/videl** — production proven Videl Music Bot, now **perfected**.

**Fast • Smooth • Powerful • Free to Deploy • Full-Stack Admin + AI**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Kurigram](https://img.shields.io/badge/Kurigram-dev-00BFFF?style=for-the-badge)](https://github.com/KurimuzonAkuma/kurigram)
[![PyTgCalls](https://img.shields.io/badge/PyTgCalls-VC-6A5ACD?style=for-the-badge)](https://github.com/pytgcalls/pytgcalls)
[![aiogram](https://img.shields.io/badge/aiogram-3.31-2B5BFE?style=for-the-badge)](https://github.com/aiogram/aiogram)

---

## ◍ Wʜᴀᴛ's Pᴇʀғᴇᴄᴛ ⬪

This is **not** a demo — it's the **real Videl** from `Beasgohan-code/videl` (7 commits production) **fully integrated** + cyber dark perfected + full-stack upgrade.

### Cyber Dark Aesthetic ⫶

* **Small caps** `ɪᴅ ɪɴғᴏ ᴀssɪsᴛᴀɴᴛ` via `formatters.sc()` — every label perfected
* **Sans bold** `𝗩𝗶𝗱𝗲𝗹` for premium titles
* **Dark glyphs** `◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢` — your pick `◍ ⬪ ⫶` — no light ✰ ☂︎ left
* **Progress bar** rewritten: `⬪ ◍───────── ⬪` moving cyber dot (was ♡)

### Production Core — Directly from Upstream ✅

Full `videl/` from `Beasgohan-code/videl` kept intact:

| Module | What it does — production grade |
|--------|---------------------------------|
| `core/player.py` `core/call.py` `core/queue.py` `core/watcher.py` | VC auto-join, idle leave (idle VC cleanup), stream end → smartqueue, auto DB cleanup 30d inactive |
| `modules/play.py` | **Search picker** top-5 YouTube, document mkv/mp4 support, `force_video`, cplay, cooldown, vote-to-skip, local media handler |
| `modules/admin.py` | `ban/mute/kick/promote/warn/welcome/purge/pin` with proper `ChatMemberStatus` & `FloodWait` handling — real TG admin rights |
| `modules/locks.py` | **Locks panel** interactive + anti-flood, panel keyboard |
| `modules/playlist.py` `smartqueue.py` `autoplay.py` | User/group playlists, smart queue, autoplay related |
| `utils/youtube.py` | **Eldian API + Shruti API + yt-dlp** fallback chain with cookies.txt & proxy support — fixes Render bot-check |
| `utils/rich_ui.py` | **Obfuscated production Rich UI** — Bot API 10.3 `rich_heading` `rich_kv_table` `rich_note` with fallback, `RICH_AVAILABLE` check |
| `api/eldian_routes.py` | Built-in **Eldian-compatible download API** `GET /api/stream_audio?url=` + `POST /v1/track/by-video-id` — bot uses `http://127.0.0.1:$PORT` internally |
| `__main__.py` | Flask `/_health` + `/` + Eldian routes, `assistant.start()` → `call_py.start()` → `idle()` watchdog pattern |

### Full-Stack Perfection — Added on Top ⬪

| Feature | Status |
|---------|--------|
| **AI chat** `videl/modules/ai.py` | OpenAI → Groq → Gemini → Mistral fallback, history, `/ask` `/imagine` pollinations, cyber dark prompt |
| **Utils** `videl/modules/utils_extra.py` + `fun.py` | weather wttr.in, qr, shorten, calc, wiki, git, afk, joke/8ball/ship/quote — all `◍` styled |
| **Admin extended** | `SUDO_USERS` set, `LOG_CHANNEL_ID`/`LOGGER_ID` dual, `WEBAPP_URL` in start |
| **Supabase sync** | `config.SUPABASE_URL` + `bot/database.py` mirrors MongoDB `served_chats/users` to `hanre-studio` for dashboard |
| **Dropbox backup** | `bot/services/watchdog.py` every 6h `videl.db` → `/Videl0/backups` (full use of connector) |
| **Vercel webapp** | `webapp/` Next.js 15 dashboard (stats/queue/gbans/ai) — `hosting-bot-dashboard` `prj_p3jQDGAHmkvTp0spcK3tzNJXYxsD` — uses same Supabase |
| **Server keep-alive** | `server/app.py` FastAPI `/health` `/ping` `/stats` `/webhook` for aiogram side, watchdog loop |
| **Docker** | Production Dockerfile with `ffmpeg` + `yt-dlp` fresh + both Flask (10000) & FastAPI coexistence |

External repos **fully used** as demanded:
* **Richgram** (Badmunda05) — production `rich_ui.py` (obfuscated) + `rich_heading` tables — not reinvented
* **Kurigram dev.zip** — Bot API 10.3
* **py-tgcalls + ntgcalls** — real VC, not file fallback only

---

## 🚀 Deploy — Production

```bash
git clone https://github.com/Beasgohan-code/Videl0
cd Videl0
cp sample.env .env
# fill API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, MONGO_DB_URL, OWNER_ID → required
nano .env
python main.py        # production: Flask health on PORT + Videl watchdog
# or Docker:
docker build -t videl:perfect . && docker run --env-file .env -p 10000:10000 videl:perfect
# or Koyeb/Render one-click: uses render.yaml / koyeb.yaml
```

Required env: `API_ID` `API_HASH` `BOT_TOKEN` `STRING_SESSION` `MONGO_DB_URL` `OWNER_ID` — same as upstream `Beasgohan-code/videl`.

Optional pro: `OPENAI_API_KEY` `GROQ_API_KEY` for `/ask` AI, `SUPABASE_URL`/`KEY` for dashboard sync, `DROPBOX_ACCESS_TOKEN` for backup, `LOGGER_ID` for logs channel.

Free hosts in `render.yaml` `koyeb.yaml` `railway.json` already configured — just set env.

---

## ◍ Sᴛʏʟᴇ Pʀᴇᴠɪᴇᴡ ⫶

```
/start → ◍ Vɪᴅᴇʟ ᴍᴜsɪᴄ ◍
         ⬪ Hᴇʏ Beasgohan ⬪
         ⫶ Welcome — a telegram VC music bot ⫶
         ⬪ Fᴇᴀᴛᴜʀᴇs ⬪  ◍ audio & video in voice chat

/play → ◍ sᴇᴀʀᴄʜɪɴɢ ⫶ → search picker ⬪ top 5 ⬪
/ping → ⦿ Pᴏɴɢ ⦿  ◍ Lᴀᴛᴇɴᴄʏ: 42ms ◍
progress → 1:02 ⬪ ──◍─────── ⬪ 3:27
```

All modules now use `sc()` `sb()` `⬪ ⫶ ◍ ⬩ 𖦹` — 100% perfect cyber dark.

---

## 📦 Structure — Perfect & Better

```
Videl0 (production)
├── videl/                ← upstream Beasgohan-code/videl FULLY KEPT (core, modules, utils, api)
│   ├── modules/ai.py     ← NEW perfect AI
│   ├── modules/utils_extra.py, fun.py ← NEW utils
│   └── utils/formatters.py ← cyber dark upgraded (progress ◍)
├── bot/                  ← Videl0 full-stack side (aiogram, Supabase, fonts ⬪)
├── webapp/               ← Next.js dashboard (Vercel)
├── server/app.py         ← FastAPI keep-alive + webhook
├── config.py             ← merged upstream + extensions (Supabase/Dropbox/AI)
├── main.py, start        ← upstream production entrypoint
├── requirements.txt      ← merged upstream + AI + Supabase/Dropbox
└── Dockerfile, render.yaml, koyeb.yaml ← production deploys
```

---

## 🔗 Connectors — All Used

* **Supabase** `hanre-studio` `gnfgnwkxomwomgmyvzlq` — tables `videl_*` mirrored for dashboard
* **Dropbox** `gokuvssaitama492@gmail.com` — `videl.db` backups
* **Vercel** `beasgohan-code` `team_vCfLqwFv8sokRbyUnLjGZ867` `hosting-bot-dashboard` — webapp live

---

## 👤 Credits — Kept

* **Videl** by [Beasgohan-code](https://github.com/Beasgohan-code) — original production bot
* **Richgram** by **Badmunda05** — Rich UI
* **Kurigram** • **PyTgCalls** • **aiogram** community

MIT — fork & perfect freely. Keep credits ❤️
