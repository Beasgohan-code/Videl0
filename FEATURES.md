# ◍ Vɪᴅᴇʟ — Feature Suggestions & Roadmap • Cyber Dark Perfect

> *"Exceed Rose/GroupHelp via federations, blocklist, disable, log channels, anti-raid/spam/porn, welcome media+buttons, notes/filters, connections, cleaners — then add music + AI awesome."*

This doc lists **implemented ✅** + **suggested ⬪** features. Use it to decide next build priority.

---

## ✅ Implemented — v3 + Expansion (2026-10-19)

### Music & Media
- `/play`, `/vplay`, `/cplay`, `/cvplay` — VC streaming via PyTgCalls 2.2.11 + ntgcalls (real VC, not file fallback)
- Queue, skip, pause/resume, stop, seek, seek-back/forward, replay, loop (off / one / all)
- Now-playing cyber-dark UI (◍ progress bar ⫶ rich buttons ⬪ next + queue count)
- `downloader` module: `/song` (MP3 192k) + `/vsong` (MP4 1080p) + `/download` auto-detect — yt-dlp + aria2c + cookies + proxy + external downloader
- `/playlist` save/play/list/del (user & group playlists, Supabase + Mongo)
- `/lyrics`, `/queue`, `/smartqueue`, autoplay
- Channel-play `/cplay` with promotion & VC creation fallback

### AI Chatbot — Awesome
- Multi-provider fallback: **OpenAI → Groq → Gemini → Mistral → Pollinations** (all 4 external repos used)
- Streaming not via edits, concise warm cyber tone, system prompt from env
- `/ask`, `/gpt`, `/ai`, `/videl`, `/gemini` + `/imagine` (DALL·E + Pollinations fallback)
- History trimmed to 8 turns, Supabase `videl_ai_history` if present
- Web playground at `/dashboard` → AI tab (same provider chain)

### Group Help — Exceeds Rose / GroupHelp
- `/ban`, `/kick`, `/mute`, `/unmute`, `/warn` + warns DB, `/pin`, `/purge`, `/promote/demote`
- **Locks elite**: 30+ lock types, proper enforcement, `locks` + `locks_elite` modules
- **Federations** (`federation.py`): create/join/leave, fban/unfban, import, log channel, owner-only actions
- **Blocklist** (`blocklist.py`): add/del/list, modes delete/warn/mute/kick/ban/tban, sticker blacklist
- **Approve**: approve/unapprove/list/clear — bypass for locks/filters
- **Captcha**: welcome captcha (math/button), anti-raid, auto-kick on fail
- **Welcome** media + buttons, `extra_group` with rules, report, staff, connections, cleaners, anti-spam/porn

### Premium UI — Richgram 0.2.0
- `richgram` fully used: `rich_send`, `rich_edit`, `rich_heading`, `rich_kv_table`, `rich_table`, `rich_note`, `rich_details`, `rich_button`, `rich_img`, `rich_send_blocks`
- `premium_emojis` (63 IDs) + 4 emoji packs (NewsEmoji, iOS Icons, Rijif, Boseh) via `pe()` + `PREMIUM_IDS`
- Theme `cyber_dark` (◍ ⬪ ⫶ ⬩ ⦿ ◎ ⬢ 𖦹) — small-caps `sc()` + sans-bold `sb()`, no cute ✰☂︎

### Owner Utils — Professional
- `owner_utils` (Pyrogram) + `bot/handlers/owner` (aiogram): `/sysinfo`, `/ping`, `/logs`, `/shell` (timeout 15s, blocks dangerous), `/eval` (async, 10s), `/active`, `/restart` (Docker-aware `os._exit(0)`), `/update` (git pull + pip install + restart), `/broadcast_pro` (rich progress)
- All owner cmds: `OWNER_ID` + `SUDO_USERS`, logged to `LOG_CHANNEL_ID`, `tini` zombie reaping, non-root `videl`

### Webapp + Web Chat (real user)
- **Next.js 15 + Tailwind** (`webapp/src`), Vercel hosting, Supabase + Dropbox + keep-alive + watchdog
- `/dashboard` — overview / music queue / ai playground / gbans / ops
- **Channel Post Studio** (`/dashboard/channel`): compose HTML, media URL, inline buttons JSON → `POST /api/channel` → Bot API 10.3 `sendMessage`/`sendPhoto` (live preview)
- **Web Chat** (`/dashboard/chat`): chat as **bot** (BOT_TOKEN) **or as real user** (STRING_SESSION via Pyrogram). Input `chat_id` (default `muhehehe` demo → set real `-100…`/`@username` to send live). `POST /api/chat` → Bot API or backend `/api/user/send` (userbot). History polls `videl_webchat` via Supabase every 4s.

### Ops & Infra
- `config.py` single source of truth (API_ID/HASH/BOT_TOKEN/STRING_SESSION/MONGO/SUPABASE/OWNER_ID, helpers `_req`/`_int`/`_bool`)
- `videl/__main__.py` Flask owns `PORT` (health + Eldian API), `server/app.py` FastAPI owns `KEEPALIVE_PORT` if set → no port clash (fixed)
- `Dockerfile` hardened: `python:3.11-slim` + `ffmpeg` + `aria2c` + `tini` + Node 20, non-root, `HEALTHCHECK`, `VOLUME` downloads/logs, multi-stage cached, `tini --` signal handling
- `watcher.py` + `db.py` cleanups: downloads TTL 2h, DB 30d, idle VC 10m, every 5m/6h

---

## ⬪ Suggested — Build Next (by impact)

### 1. Media Downloader Pro ⬪⬪⬪
- [ ] `/song` search picker (5 results carousel) if query ambiguous — use `py-yt-search` + buttons
- [ ] Instagram Reels / TikTok / Twitter downloader via yt-dlp + `gallery-dl` fallback (needs cookies env `INSTA_COOKIES`)
- [ ] Apple Music / Spotify metadata resolver → YouTube match via `spotipy` + `yt-dlp --extractor-args youtubetab:skip=authcheck`
- [ ] Thumbnail + `ffmpeg` trim `/trim 0:10-0:30` for samples; ID3 tags via `mutagen`

### 2. Owner Suite ⬪⬪⬪
- [ ] `/stats` pro: top chats/users, command heatmap (Recharts in dashboard already)
- [ ] `/backup` → Dropbox ` /Videl0/backups/{date}.dump` (pymongo `mongodump` via `mongodump` bin)
- [ ] `/announce` with pin + silent toggle + preview
- [ ] `/leave <chat_id>` + `/chatlist` (with pagination)
- [ ] Secret vault: `/env set KEY VALUE` → write to Vercel env via API + restart

### 3. Music Awesome++ ⬪⬪
- [ ] Effects persistent: `ffmpeg` `atempo`, `asetrate`, `bass`, `nightcore`, `8d` — save per-chat in `videl_effects` (currently in-memory only)
- [ ] Spotify/Deezer playlist import: paste URL → resolves 50 tracks via `yt-dlp` + queues
- [ ] Vocal isolation via `spleeter`/`demucs` (optional VPS-only)
- [ ] 24/7 radio mode + auto-DJ crossfade

### 4. AI Awesome++ ⬪⬪
- [ ] Memory per-user (Supabase `videl_ai_history` with embedding via `openai` + vector search)
- [ ] `/summarize` (reply to long message), `/translate <lang>`, `/tts` (gTTS), `/vision` (photo → ask)
- [ ] Streaming edits: show typing + edit chunks every 0.8s
- [ ] Persona packs: `/persona cyber` / `cute` / `roast` → swaps system prompt

### 5. Channel Studio Pro ⬪⬪
- [ ] Schedule posts (cron via Vercel Cron + Supabase `videl_scheduled_posts`)
- [ ] Drafts + history + duplicate to multiple channels
- [ ] Polls/quizzes (`sendPoll`) + inline keyboard builder drag-drop
- [ ] Analytics: views/forwards (via `getChat` + channel stats bot)

### 6. Web Chat Pro ⬪⬪
- [ ] Real-time via Supabase Realtime channel (instead of 4s polling)
- [ ] Typing indicator + read receipts (Telegram `sendChatAction`)
- [ ] File uploads via web (proxy to Bot `sendDocument`)
- [ ] Multi-chat sidebar (recent chats from `videl_chats`), search

### 7. Infra Hardening ⬪
- [ ] Redis queue for broadcast (instead of 0.04s loop)
- [ ] Rate limiter (per-user token bucket for `/song`, `/ask`)
- [ ] Sentry + Logdra / BetterStack logging
- [ ] E2E tests: `pytest` + `pyrogram-test` for all command handlers

---

## How to prioritize
1. **Keep-alive + logs channel + watchdog** → already done, verify `LOG_CHANNEL_ID` + `KEEPALIVE_PORT=8000` on VPS
2. Next sprint: **media picker + schedule posts + AI streaming** (visible user delight, low risk)
3. Then: **effects persist + backup + stats pro** (owner power)
