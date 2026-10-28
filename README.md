# Videl Studio

Telegram music and group management with a separate, privacy-first creative webapp.

## Access model

- **Everyone:** public Home, Post Studio, image designer, local drafts, text/image export, native text sharing, caption checks, hashtag extraction and campaign-link creation. No account required. Public users cannot send through the owner's bot.
- **Owner only — Telegram ID `6265999542`:** bot dashboard, chat sending, served-group settings, automation controls, analytics, broadcasts, bot configuration, publishing through the bot, and the in-page Videl Music player.
- Mini App launch data and Login Widget signatures are verified server-side. Client-supplied IDs, Telegram usernames and `initDataUnsafe` never grant access. Both the auth proxy and backend enforce the exact owner ID.
- Signed, HttpOnly owner sessions expire server-side after 24 hours. Browser and partitioned Mini App cookie contexts are supported; sign-out clears both. The former non-expiring cookie markers are intentionally invalidated.
- Private API endpoints, including legacy summary and health routes, reject unauthenticated requests before contacting the backend. Navigation filtering is additional UX, not the authorization boundary.

## Structure

- `videl/`: Python bot, Flask internal API served through Waitress, voice streaming and MongoDB-backed management.
- `webapp/`: Next.js app deployed on Vercel; all workspace panels use one root URL, including the owner-only Videl Music browser player.
- `vendor/eldian_music_api/`: licensed Eldian Network downloader integration, shared by bot playback and the in-page player.
- `vendor/richgram/`: licensed Richgram UI fork with safe rejection fallbacks.
- `tests/`, `webapp/tests/`: offline behavior, authorization, rendering and browser regression tests.

MongoDB is the only application database. No AI, Dropbox or Supabase integration is enabled. Post drafts and editable design state use the visitor's own browser storage, not a shared server collection.

## Deployment

The current web URL is **https://videl-studio.vercel.app**. The Python bot/internal API runs separately on Render; deploying Vercel does not update a running bot.

Backend settings are documented in `.env.example`. Set `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_DB_URL`, `OWNER_ID=6265999542`, `WEBAPP_URL` and `WEBAPP_SECRET`. Voice-chat streaming also needs an authorized `STRING_SESSION` and group permissions. It defaults to PyTgCalls High output (48 kbps stereo); the owner or a bot sudo operator can use `/voicequality studio|high|medium|low` in private chat. The selected preset is saved in MongoDB and applies to new streams; `/voicehealth` checks the assistant, PyTgCalls, FFmpeg and media-provider readiness. `/restart` is owner-only and disconnects active voice chats. Output bitrate cannot restore detail missing from the source recording. Never commit real cookies, tokens or session strings.

Vercel needs `VIDEL_BACKEND_URL` and the same server-only `WEBAPP_SECRET`. Browser Login Widget sign-in also requires the production web domain to be configured with BotFather; Mini App launch buttons provide signed Telegram launch data directly. No bot token belongs in `NEXT_PUBLIC_*` settings.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py

# Separate shell; Next.js proxies authenticated operations server-side.
cd webapp
npm ci
npm run dev
```

## Checks

```bash
.venv/bin/python -m unittest discover -s tests -q
npm --prefix webapp test
npm --prefix webapp run build
```

Two workflows run in CI. `ci.yml` runs the suites above on every push. `deploy-check.yml` runs after the push, waits for the live bot backend to report the pushed
commit and for the panel to answer, and fails when either is still serving an older build — so "it deployed" is checked rather than assumed. A `/health` that
reports a bot which is not online is a warning there, not a failed release.

`webapp/tests/browser-smoke.cjs` exercises public/owner views, editing and export with mocked Telegram/backend requests. A passing mock is not evidence of live Telegram delivery, Premium eligibility or working production voice permissions.

## Scope and limitations

Real bot features include voice playback, moderation, notes/filters, advanced polls/quizzes, admin reactions and forum-topic actions. See [Telegram upgrade details](docs/TELEGRAM_API_UPGRADE.md). Custom emoji IDs still require Telegram eligibility; readable fallbacks are provided. No Stars spending or paid broadcasts are enabled.

Chat is a sending workspace, not a synchronized inbox. Broadcasts are bounded synchronous operations, not a durable queue. Saved settings and schedule records should not be mistaken for new background services.

Inactive demos and duplicate source were removed; retained commands are explicitly loaded by `videl/modules/__init__.py` and `videl/modules/plugins_loader.py`. [Cleanup inventory](docs/CODE_CLEANUP.md).

## Attribution

Videl by [Beasgohan-code](https://github.com/Beasgohan-code). Richgram by [Badmunda05](https://github.com/Badmunda05/richgram). Music downloader integration by [Eldian Network](https://github.com/Eldian-Network/eldian-music-api). Their vendored licenses and notices are retained.

The original project's acknowledgements also credit Kurigram, PyTgCalls, PaulSonOfLars/tgbot, AnonymousX1025/FallenRobot, botdev72/GroupHelp and CertifiedCoders/AnnieXMusic. Retain upstream attribution when redistributing source.
