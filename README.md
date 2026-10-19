# ✨ Videl0 — Full-Stack Telegram Bot

> Telegram Bot API **10.3** • **aiogram 3.31** • **Richgram** by Badmunda05 • **ShizuMusic** core • Full-stack with Vercel + Supabase + Dropbox

**Made by Beasgohan-code — don't hold back, everything included.**

---

## 🌟 What is Videl0?

All-in-one Telegram bot: **Music + AI Chat + Utilities + Group Management** with a sleek **Admin Dashboard** (Next.js) hosted on Vercel.

- 🎵 **Music** — High-quality VC streaming via `pytgcalls` + `yt-dlp` queue (ShizuMusic proven stack), pause/resume/skip/seek/shuffle, lyrics, playlists, thumbnail & autoplay toggles. Falls back to audio-file mode if no assistant session.
- 🤖 **AI** — OpenAI → Groq → Gemini → Mistral fallback, per-user history in Supabase, vision (reply to image), image gen (DALL·E + pollinations), summarize & translate.
- 🧰 **Utility** — weather (wttr.in), QR, shortener, calc, define/UD/wiki, carbon, paste, git, pinterest, sticker, AFK, tagall, speedtest, news.
- 🛡️ **Group Admin** — ban/unban/kick/mute, warn system, pin/purge/del, lock/unlock, slowmode, welcome/goodbye, filters/notes/rules, reports, staff list, language.
- 👑 **Owner/Sudo** — broadcast, global ban, block, add/remove sudo, backup to Dropbox, eval/shell, logs, restart, active VC, leave.
- 🔔 **Ops** — FastAPI keep-alive (`/` , `/health` , `/ping` , `/stats` , `/webhook`), APScheduler watchdog (restarts), logs channel, Dropbox backup every 6h.
- 🖥️ **Webapp** — Next.js admin dashboard (overview, music queue, moderation, AI playground, ops) deployed to Vercel.

---

## 🏗️ Architecture

```
Videl0/
├── bot/
│   ├── main.py              # aiogram Dispatcher + Bot (polling or webhook)
│   ├── config.py            # all env (Telegram, Supabase, Dropbox, Vercel, AI)
│   ├── database.py          # Supabase-first + SQLite fallback (videl_* tables)
│   ├── database_ext.py      # chat settings, locks, welcome, etc.
│   ├── rich_ui.py           # aiogram port of Richgram (Bot API 10.3 Rich Messages)
│   ├── handlers/            # start, admin, owner, music, ai, utility, group, callbacks
│   ├── middlewares/         # logging, tracker (flood/afk/gban/filter)
│   ├── services/            # ai_provider, music_service (pytgcalls), keep_alive, watchdog
│   └── utils/               # helpers, keyboards, youtube, decorators
├── server/
│   └── app.py               # FastAPI keep-alive + webhook
├── webapp/                  # Next.js dashboard (Supabase + Vercel)
├── Dockerfile & docker-compose.yml
└── .env.example
```

### External repos fully used

- **[aiogram 3.31](https://github.com/aiogram/aiogram)** — Bot API 10.3 support (Rich Messages, checklist, paid broadcast, direct messages, business).
- **[Richgram](https://github.com/Badmunda05/richgram)** — `rich_heading`, `rich_kv_table`, `rich_details`, colored `rich_button` rows, `RichDraft` live drafts — ported to aiogram (`bot/rich_ui.py`).
- **[ShizuMusic](https://github.com/Badmunda05/ShizuMusic)** — queue, player controls, `resolve_stream` via Shruti API + yt-dlp fallback, cooldown, channel-play, progress bar — adapted in `bot/handlers/music.py` & `bot/services/music_service.py`.

### Connectors (all 3 used)

- **Supabase** `gnfgnwkxomwomgmyvzlq` (ap-south-1, project `hanre-studio`) — primary DB (`videl_users`, `videl_chats`, `videl_music_queue`, `videl_ai_history`, `videl_gbans`, `videl_logs` …). Also exposed to webapp.
- **Dropbox** `gokuvssaitama492@gmail.com` — 6-hourly `videl.db` backup to `/Videl0/backups` + startup log docs.
- **Vercel** `beasgohan-code` team `team_vCfLqwFv8sokRbyUnLjGZ867` — `hosting-bot-dashboard` project hosts Next.js webapp; webhook URL configured via `WEBHOOK_URL`.

---

## 🚀 Deploy

### 1. Env

```bash
cp .env.example .env
# fill BOT_TOKEN (BotFather), OWNER_ID, SUPABASE_URL/KEY, etc.
```

Required: `BOT_TOKEN`, `OWNER_ID`. Optional but recommended: `API_ID`/`API_HASH`/`STRING_SESSION` for VC, `OPENAI_API_KEY` or `GROQ_API_KEY` for AI, `LOG_CHANNEL_ID` for logs channel.

### 2. Local (polling)

```bash
pip install -r requirements.txt
python -m bot.main                 # polling
# in another terminal:
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload   # keep-alive
# webapp:
cd webapp && npm install && npm run dev
```

### 3. Webhook (Vercel)

Set `WEBHOOK_URL=https://<your-vercel>.vercel.app/webhook` and `WEBHOOK_SECRET`. Deploy webapp to Vercel — the `/api` routes proxy to Supabase, and `/webhook` feeds aiogram.

### 4. Docker

```bash
docker-compose up --build
```

### 5. VPS

```bash
sudo apt update && sudo apt install -y python3 pip ffmpeg git
git clone https://github.com/Beasgohan-code/Videl0 && cd Videl0
pip install -r requirements.txt
cp .env.example .env && nano .env
python -m bot.main
```

---

## 📚 Commands (full)

| Category | Commands |
|---|---|
| General | `/start` `/help` `/ping` `/stats` `/id` `/info` `/about` `/repo` |
| Music | `/play` `/vplay` `/playforce` `/queue` `/skip` `/stop` `/pause` `/resume` `/seek` `/shuffle` `/lyrics` `/song` `/playlist` `/nowplaying` `/thumbnail` `/autoplay` |
| AI | `/ask` `/gpt` `/imagine` `/summarize` `/translate` `/tts` `/vision` (+ natural @mention) |
| Utility | `/weather` `/qr` `/shorten` `/calc` `/define` `/wiki` `/carbon` `/paste` `/git` `/pinterest` `/sticker` `/afk` `/tagall` `/speedtest` `/news` |
| Group | `/ban` `/unban` `/kick` `/mute` `/unmute` `/pin` `/purge` `/warn` `/lock` `/slowmode` `/setwelcome` `/filter` `/note` `/rules` `/report` `/staff` |
| Owner | `/broadcast` `/gban` `/block` `/addsudo` `/backup` `/eval` `/exec` `/logs` `/restart` |
| Fun | `/8ball` `/dice` `/flip` `/ship` `/joke` `/meme` |

See in-app: `/help music`, `/help ai`, etc.

---

## 🔐 Administration & Owner

- **Privileged:** `OWNER_ID` + `SUDO_USERS` (comma list) — bypass all checks. Sudo list also persisted in Supabase `videl_chats` id 0 (`sudo_users`).
- **Logs channel:** every `/start`, ban, gban, broadcast goes to `LOG_CHANNEL_ID` (`LOGGER_ID`).
- **GBan:** `/gban reply <reason>` — stored in `videl_gbans`, enforced on next message via middleware (auto-ban).
- **Watchdog:** checks `bot.get_me()` every 5m; exits if silent 15m so process manager restarts.
- **Keep-alive:** pings `KEEPALIVE_URL` every `WATCHDOG_INTERVAL` (default 300s) — suitable for Render/Koyeb free-tier.

---

## 🧪 Supabase Tables (created)

`videl_users`, `videl_chats`, `videl_warnings`, `videl_filters`, `videl_notes`, `videl_music_queue`, `videl_ai_history`, `videl_afk`, `videl_gbans`, `videl_logs`, `videl_stats`, `videl_playlists`, `videl_giveaways`.

Webapp uses same tables via anon key (RLS: allow read for stats/queue/gbans in production — configure in Supabase dashboard).

---

## 🙏 Credits

- **Richgram** & **ShizuMusic** by [Badmunda05](https://github.com/Badmunda05) — Rich UI and music core used with thanks.
- **aiogram** team — Bot API 10.3 on day one.
- Built for Videl0 by Arena Agent.

## 📄 License

MIT — see `LICENSE`.
