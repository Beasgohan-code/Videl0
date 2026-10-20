# Bot inbox: DMs, groups and chat settings

An owner-only Telegram-style panel inside the existing single-root Studio. This
uses **the bot account**, never a personal Telegram account or a second update
poller. The panel replaces the old session-only Smart Chat sender; Post Studio
and all other panels are preserved.

## What is implemented

- A conversation list of bot DM peers observed since this capture feature starts,
  plus existing served groups. Minimal peer metadata (name/type/ID) can be listed
  even when message recording is off; body content is not saved until opt-in.
- New and edited message snapshots, reply context, sender/message/topic IDs,
  literal text search, sender filtering and bounded older-message pagination.
- Plain-text messages and replies sent as the bot, not only replies to existing
  messages. Confirmed sends appear immediately as session-only receipts when
  incoming recording is paused; these receipts are not a persistent archive.
- Photo/MP4 uploads, uploaded voice messages and browser microphone recording.
  Attachments have previews and can include captions or reply/topic context.
- Owner-authenticated incoming photo/video/audio previews. Telegram file IDs stay
  server-side, file bytes are fetched only from Telegram-returned paths, and no
  bot-token download URL is exposed to the browser.
- Group delete, pin/unpin, ten-minute mute, unmute to real group defaults, ban and
  existing protection toggles. Group admin targets are protected. These controls
  are not offered as group moderation inside private DMs.
- Per-conversation recording on/off; 1, 7 or 30 day retention; dashboard-only
  history clear. Enabling recording posts a notice in the conversation first.
- `/groupview off|status`: any current group admin can stop group recording.
  `/inbox off|status`: a DM participant can stop recording of their own bot chat.
- Request IDs protect sent actions/attachments against resending an uncertain or
  repeated request. A Telegram success is reported separately from a failed
  local history/audit follow-up. There is no automatic send retry after timeout.

## Boundaries and limits

- Owner authentication is required on every proxy/API/media endpoint. Group
  reads/actions additionally check the owner's **current group admin** status;
  moderation checks specific actor and bot privileges independently.
- The bot cannot initiate conversations with arbitrary Telegram users. A peer
  must have messaged the bot and appeared in its own update stream. Existing
  group-member IDs are not presented as fabricated bot DMs.
- No old Telegram history is imported. Only updates Telegram delivers to this
  bot are observable. Bot privacy settings and permissions affect group coverage;
  other bots' messages, unseen deletions and messages during downtime are not a
  guaranteed part of this archive.
- Polling is every six seconds while the panel/page is visible. It pauses while
  browsing older messages. The capture queue is bounded to 500 items and reports
  overload drops; it is in-process, not durable delivery across restarts.
- Maximum upload: **4 MiB**, allowing multipart overhead within a Vercel function's
  request size limit. Videos must be MP4. Photos are decoded and re-encoded as
  JPEG, with pixel/dimension limits. Preview downloads are bounded to **8 MiB**;
  larger originals should be opened directly in Telegram.
- Voice is limited to **120 seconds**, converted server-side to Ogg Opus using
  ffmpeg/ffprobe. The production Dockerfile already installs both. Microphone
  capture needs HTTPS, browser support and explicit microphone permission. Some
  embedded Mini App/iframe environments may disallow microphone access; voice
  upload is the fallback. Recordings stop on panel change, backgrounding or chat
  change; nothing is sent until the owner presses Send.
- Reply bodies are plain text; this is not a full Telegram client, call client,
  read-receipt system, arbitrary account session, or full-size video uploader.
- Mongo TTL may run asynchronously; read and action queries also enforce expiry.
  Retention updates use MongoDB's date-plus-milliseconds update pipeline (Mongo
  4.2+). History clear touches only this inbox's message snapshots and pauses
  recording; it does not delete Telegram messages, users, groups or playlists.

## Deployment and testing

Both the Render bot/backend and Vercel frontend must deploy together. Existing
`WEBAPP_SECRET`, Telegram bot credentials and MongoDB configuration are reused;
never expose them as frontend environment variables. New collections are
`bot_inbox_peers`, `group_view_settings`, `group_view_messages` and
`group_view_operations`; indexes are created lazily on first enable/send/capture.

Local tests require `pip install -r requirements-dev.txt` in addition to normal
bot dependencies. Mongomock is used only for offline contract tests, never as an
application data backend. Its missing date-arithmetic pipeline support is mocked
in the retention-contract assertion; real Mongo integration remains to verify.

Current checks: Python suite **174 run, 173 passed, 1 skipped** (real voice codec
conversion skipped because this sandbox lacks ffmpeg/ffprobe); **45 frontend
tests passed**; TypeScript check and Next production build passed. Playwright
fixture checks cover mobile layout, owner DM text sends, multipart photo sends
and hiding group-only moderation in DMs. They use mocked APIs, not live Telegram.
No live Telegram/Mongo/media delivery or production deployment is claimed.

## Advanced workspace pass

The original Studio design and one-root panel navigation remain intact. Added:

- All / DMs / Groups / Pinned conversation folders, pinned-first ordering and
  title/ID/tag search. A conversation pin here is an owner preference, **not** a
  Telegram message pin or an action visible to group members.
- Per-chat plain-text drafts stored in MongoDB with explicit Save, Restore and
  Clear actions. They can be restored from another authenticated device after
  deployment. Attachments and microphone recordings are never draft-persisted;
  there is no misleading automatic-save indicator.
- Up to five conversation tags, private owner notes, and create/edit/delete/use
  saved replies. Using a saved reply only fills the composer and asks before
  replacing existing text; nothing is sent automatically. Notes/drafts/replies
  are owner-authored workspace data, separate from captured-message retention.
- A monotonic per-chat review marker and an incoming-new count for the **loaded
  message window**, excluding bot-authored and deleted items. Mark reviewed is a
  database preference only: no Telegram read acknowledgement is sent or implied.
- Ctrl/Command+Enter to send from the active composer, while normal Enter retains
  multiline text. IME composition, recording, busy state and size limits guard
  the shortcut.
- Separate edit revisions for draft, notes and organization fields, plus saved
  reply revisions. Stale-window writes return 409 instead of silently overwriting
  newer text. Mongo save acknowledgement and subsequent list refresh are separate
  outcomes; a refresh failure does not cause an automatic second save/send.

New collections: `inbox_owner_chats`, `inbox_quick_replies`. New owner-only proxy
and internal endpoint: `/api/inbox-workspace`, `/internal/inbox-workspace`.
The server always supplies owner ID 6265999542, ignoring client ownership claims.
Per-chat detail reads/writes use the inbox's current group-admin access check;
global preference summaries exclude private notes and drafts. No localStorage
copy, user-account login, AI backend or database replacement is added.

Latest local verification: **186 Python tests run, 185 passed, 1 skipped** (same
sandbox ffmpeg/ffprobe limitation); **50 frontend tests passed**; TypeScript,
Next production build, compileall and diff checks passed. Two Playwright fixture
suites passed: existing DM/multipart flows and new drafts/notes/pins/replies/
review markers/chat-switch isolation/keyboard send/mobile layout. These use
mocked APIs and do not establish live Telegram/Mongo integration. Both backend
and frontend deployment are still pending.

## Production rollout preparation — 2026-10-20

Production was still serving the pre-inbox commit `fdaede4`; publishing local
files did not deploy either service. Vercel automatic Git deployments are
disabled, so production must be deployed explicitly from the published SHA.
The navigation now names the owner-only section **Bot Inbox**. Missing legacy
backend routes return an explicit backend-update-required error, rather than
looking like an empty conversation list. JSON chat-not-found responses remain
unchanged. This does not claim that media, message capture or Mongo workspace
storage can work until the matching backend is deployed.

Fresh verification after restoring sandbox dependencies: 186 Python tests
(185 passed, one ffmpeg-dependent skip), 51 frontend tests passed, production
build and typecheck passed. The rollout compatibility test distinguishes absent
routes from genuine JSON 404s. No live owner/Telegram/Mongo session was used.

Backend rollout: in the existing Render service, use **Manual Deploy → Deploy a
specific commit** with the published inbox commit SHA on
`arena/1cfcb3da-videl0` (not an older `main` commit). Keep the existing environment,
MongoDB database, disk and service; do not create a second bot instance. This
session has no Render connector, so backend deployment remains manual and
must be verified separately before declaring the inbox fully live.

## Messenger-first layout — 2026-10-20

Reworked the inbox around the actual Telegram chat pattern, not visible admin
workspace columns. Desktop has a conversation rail plus a flexible chat; mobile
shows either the conversation list or the selected chat, with a Back to chats
button. Chat info, saved replies, notes and moderation are behind the header menu.
The composer uses one attachment/text/microphone/send row with an expandable
media picker; long messages grow vertically. The global tool finder is omitted
while chatting. Existing send confirmation, upload/recording limits, owner auth
and CSRF protection remain in place. No personal-account session is introduced.

Messages initially scroll to the latest captured message. Polling preserves the
reader's position if they scroll up; a jump-to-latest control is available.
Prepending older captured pages compensates scroll height to preserve the
viewport. The chat rail refreshes every 15 seconds while the panel is visible,
with real session previews from opened chats (not invented snippets or unread
counts). Date separators and compact times replace database IDs on bubbles.
Only the configured bot's username or a confirmed local send is outgoing; other
bots are not treated as this bot. There are no fake online/read indicators.

Validated with frontend unit tests and a production build; three mocked browser
suites exercise mobile chat/back navigation, sending/media, workspace access,
initial bottom position, no polling scroll hijack, older-history anchoring and
composer placement. These are offline fixtures, not live Telegram/Mongo proof.
The previously documented matching backend deployment is still required.

## Rich formatting, premium emoji and cover assets — 2026-10-20

Smart Chat now sends and renders Telegram's documented HTML formatting. The
composer has a formatting bar for **bold, italic, underline, strikethrough,
monospace, spoiler, quote and links**, plus `Ctrl/⌘ + B / I / U / D`
shortcuts and a live Telegram preview toggle. Formatting wraps the current
selection, so no HTML knowledge is required. Messages already stored with HTML
render formatted in bubbles; the chat-list preview and reply snippets are
plain-text, not raw tags.

Premium (custom) emoji use `<tg-emoji emoji-id="…">` inside the same HTML
message. The composer's **Premium Emoji Studio** offers a starter set of real
custom-emoji IDs plus an ID + character field for any ID copied from Telegram;
only 1–20 digit IDs are accepted. Telegram Premium subscribers see them as
animated custom emoji; other viewers see the fallback character. This is a
Telegram rendering rule, not a Videl guarantee.

Both `POST /internal/group-view` (text and replies) and
`POST /internal/inbox-media` (captions) now accept sanitized Telegram HTML. The
server whitelists `b,strong,i,em,u,ins,s,strike,del,code,pre,blockquote,a,
tg-spoiler,tg-emoji`, strips `on*` handlers, only allows `https/http/tg`
links, validates emoji IDs, and enforces the 4096/1024 visible UTF-16 limits.
Unrecognised tags are shown literally instead of being sent. Invalid HTML is
rejected before any Telegram call. The snapshot advertises `rich_text: true`;
until the deployed backend reports it, the composer sends clean plain text and
shows a small notice, then switches rich sending on automatically after the
backend deploy — no further frontend change is needed.

Post Studio's **Cover Library** now has two tabs: 54 generated Videl images
(34 covers, 10 story cards, 10 quote cards) and **Your Assets** — up to 10
PNG/JPEG/WebP uploads (1.5 MB each) stored in
localStorage in that browser, reusable as post covers, downloadable or
deletable. `videl_image_design_v1` remains the editable layout document; custom
covers are images, not design documents, and are not synced to other devices.

Frontend unit tests now include premium-emoji sanitisation, chat HTML
rendering and selection-wrapping checks; Python tests cover rich replies,
sanitisation and premium-caption handling. No live Telegram/Mongo message was
sent during verification.

## Studio guide, small caps and a larger artwork engine — 2026-10-20

The website gained a public **Command Guide** panel (`/?tab=guide`, also linked
from the bot's `/start` keyboard). It lists every command in the bot's generated command
catalogue — including legacy modules merged into it — with
a summary, usage hint, chat scope and a one-tap copy button. The data file
`webapp/src/lib/commands.ts` is generated by `scripts/build_webapp_commands.py`,
so the guide cannot advertise a command the bot does not register. Owner
operations are hidden until an owner session is verified, matching `/commands`.

Labels, breadcrumbs and section heads now use true small caps
(`font-variant-caps`), keeping title case in the markup for screen readers.
The artwork engine grew from 36 to 54 deterministic PNGs: 34 covers at
1200×675, 10 story cards at 1080×1350 and 10 quote cards at 1080×1080, with two
new geometric compositions and six new palettes. Rebuild with
`python scripts/create_post_assets.py`; the script rewrites the manifest too.
