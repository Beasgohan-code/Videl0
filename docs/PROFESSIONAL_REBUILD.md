# Professional rebuild

Removed redundant service/search/novelty command adapters; retained group operations, music, AFK and reminders. Existing MongoDB records are not deleted.

Removed adapters:
- `videl/plugins/barcode.py`
- `videl/plugins/channel.py`
- `videl/plugins/clean.py`
- `videl/plugins/currency.py`
- `videl/plugins/define.py`
- `videl/plugins/ebook.py`
- `videl/plugins/filters_pro.py`
- `videl/plugins/google.py`
- `videl/plugins/helper_pro.py`
- `videl/plugins/idpro.py`
- `videl/plugins/invite.py`
- `videl/plugins/language.py`
- `videl/plugins/lastfm.py`
- `videl/plugins/lyricspro.py`
- `videl/plugins/musichelp.py`
- `videl/plugins/notes_pro.py`
- `videl/plugins/paste.py`
- `videl/plugins/pollpro.py`
- `videl/plugins/rules_pro.py`
- `videl/plugins/scheduler.py`
- `videl/plugins/sticker_tools.py`
- `videl/plugins/tagall.py`
- `videl/plugins/telegraph2.py`
- `videl/plugins/telegraph_pro.py`
- `videl/plugins/timer.py`
- `videl/plugins/trace.py`
- `videl/plugins/translate.py`
- `videl/plugins/tts.py`
- `videl/plugins/unshort.py`
- `videl/plugins/userinfo.py`
- `videl/plugins/ytsearch.py`

## Command and button UI

`/help` and the start panel now share one help center: Music, Group management,
Protection & notes, Telegram tools. Legacy wizard and duplicate novelty adapters
were removed. This is a shared guide/native-keyboard rewrite, not a claim that
every legacy command response was rewritten or live-tested.

Badmunda05 Richgram remains MIT vendored in `vendor/richgram` (upstream:
https://github.com/Badmunda05/richgram). Local `tg-button` markup now becomes
actual Kurigram inline keyboards on sends and edits, preserving callbacks, URLs,
rows, semantic styles and optional custom emoji IDs. Explicit keyboards win.
Standard-HTML fallback therefore keeps actionable buttons rather than bold inert
labels. Native labels strip HTML and normalize legacy small-cap typography.
Premium icon eligibility and client rendering are still enforced by Telegram.

## Advanced public studio

- 20 original editable layout recipes across six categories, with dynamic counts.
- Button editor: add/edit/remove, reorder rows, HTTPS links, copy-text actions,
  default/primary/success/danger styling and optional custom emoji IDs.
- Approximate styled preview; it does not execute copy or navigation actions.
- Portable versioned post JSON import/export retains formatting and button metadata.
  Local image blobs are deliberately excluded; PNG/design export remains separate.
- Public local creation/export stays available; exact-owner 6265999542 publishing
  and bot-management boundaries remain intact. No AI, Supabase or Dropbox added.

## Music/API provenance and rollout limits

The own-service Eldian routes retain the MIT engine in `vendor/eldian_music_api`;
upstream reviewed: https://github.com/Eldian-Network/eldian-music-api,
commit `06e752467b06d2838feae3882ae2e4d361cd0444`.
Authentication, concurrency/rate limits and post-download size checking are not
an end-to-end streaming/duration cap. Legacy blacklist migration, exhaustive
CAPTCHA concurrency/restart testing and real voice/moderation checks remain open.
Do not advertise Rose parity or full Bot API coverage.

Offline validation: Python unittest, frontend unit tests, typecheck, production
build and Chromium smoke tests. No live Telegram sends are performed by tests.
Render rollout is not verified; source changes alone do not update the live bot.

Initial next-work proposals were brand kits, draft approvals and scheduled publishing.
The follow-up below implements basic kits and scheduling; approvals remain open.

## Retention and managed watchdog (follow-up)

The previous age-only purge deleted playlists and group configuration. It has
been replaced with an allowlist: old `chat_activity`/`user_activity` telemetry
and **sent** reminders with an old `sent_at`, using 30 days by default. Legacy
missing timestamps, pending/unconfirmed jobs, memberships, settings, play totals,
saved content and moderation records are never inferred disposable from age.
`cleanup_old_data()` previews by default; `apply=True` deletes using the original
age/status predicate atomically, not a stale list of IDs. Database outages and
partial failures are reported, not presented as successful empty cleanups.

The managed watchdog starts after bot boot and is cancelled on shutdown. Every
minute it checks Telegram transport/MongoDB, restarts a finished CAPTCHA worker,
checks idle voice calls and dispatches a scheduled post. A failed job does not
prevent other checks. Failures and recoveries are logged without credentials.
Every six hours it applies the safe retention policy and sweeps old download
files (deferred while any music queue has work, preserving symlinks). Mongo
connections now have finite connect/socket timeouts. `/health` includes a public
aggregate watchdog heartbeat, not private maintenance details.

Private, exact-owner commands:
- `/watchdog` — read per-check maintenance status.
- `/dbcleanup` — preview safe retention counts; `/dbcleanup apply` executes it.

An activity observer now covers incoming non-music messages too, throttled to one
write per minute per chat/user with a bounded in-memory throttle. It is telemetry,
not evidence that a user has blocked the bot or a chat has removed it.

This watchdog does not restart the host process, prevent provider suspension or
prove end-to-end Telegram RPC health. It cannot perform work while Render sleeps.

## Creator tools and scheduled publishing

Brand kits save up to 20 local color/font presets; no logo storage/sync is claimed.
Version history stores up to 20 manual post checkpoints locally (text, buttons,
remote media URL), without embedding image blobs. Publishing checks are advisory:
length, common template placeholders, HTTPS preference, image context and icon
eligibility. They do not fetch links or promise destination availability.
`/permissions` reads the bot's actual group admin rights and explains missing
permissions. Assistant/session/media prerequisites remain separate.

Owner-only `/api/schedules` proxies a dedicated authenticated backend endpoint.
Schedules are stored in MongoDB, survive restarts, accept explicit UTC instants
from the device-timezone picker, and preserve a post snapshot. Only persistent
HTTPS image URLs or text posts are supported, not local image uploads. The first
version accepts 1 minute–90 days ahead and dispatches at most one due job per
minute. Cancellation atomically targets pending jobs only. Existing jobs are not
changed by edits in the studio; cancel and create a replacement to reschedule.

UUID idempotency keys prevent duplicate queue insertion for a retried request.
Each send is claimed atomically. Explicit 4xx rejection is failed; ambiguous
transport/5xx results are unconfirmed and never automatically retried. Jobs
claimed before a crash become unconfirmed after 10 minutes; jobs more than 24h
late become missed. The dashboard exposes the latest 50 job statuses. These are
at-most-once attempts, not a promise of exactly-once delivery. Telegram must be
checked before manually creating a replacement for an unconfirmed post.

A dedicated schedule endpoint is intentional: against an older backend it fails
closed (404) instead of accidentally sending immediately through the post route.
Remaining suggested features include approval queues, logo kits, history
comparison, multi-layer image editing and direct editing of published posts.

Latest follow-up validation: **66 Python tests**, **36 frontend tests**, production
build, typecheck, all registered module imports and Chromium smoke checks passed.
Browser scheduling/cancellation uses mocked APIs, not real deliveries. MongoDB
retention and scheduler queries are unit-tested with mocks; no production data
was deleted and no real Telegram post was scheduled by these tests.
Changes are local to the working branch; production rollout is still pending.

## Command UI migration and modern tools

The complete registered source inventory is in `docs/COMMAND_REFERENCE.md`:
185 names including aliases, regex-based music/effect/seek routes and enabled
plugins. Regenerate it with `.venv/bin/python -m tools.command_reference`.
`/commands [keyword|music|manage|tools]` provides searchable, paginated Richgram
navigation with bounded native callback payloads. Owner entries are available
only to owner 6265999542 in private directory views. Discovery is not permission
checking; each original handler remains authoritative. Duplicate routes fail the
inventory except for the explicitly disjoint `/seek` argument/usage handlers.

77 bot-authored moderation status/usage messages now use shared Richgram notice
cards; existing music/group handlers continue through the common Richgram send,
reply, edit and native keyboard adapters. Legacy decorated approval/federation/
blacklist heading wrappers were simplified. Inline rich-button markup now shares
native keyboard semantic styles, strips HTML from labels and preserves optional
custom emoji IDs without promising Premium eligibility. Definite style/icon
rejection falls back to a copied standard keyboard, preserving all actions.
Timeouts are not blindly retried. `/ping` now uses the same card transport,
non-blocking resource collection and owner-private process metrics; an uncertain
probe does not trigger a second send. `/start` no longer blindly resends in its
outer exception handler.

Implemented tools: `/copy` (256 UTF-16 units), `/buttons` (real keyboard preview),
`/features` (implementation/compatibility guide), and `/pollstop` (reply + admin
guard; Telegram poll ownership still enforced). Topic-management slash commands
have been retired; previously posted inline close/reopen controls remain admin-
checked. Existing advanced poll flags, explicit reactions and diagnostics remain.
No paid actions, Stars/gifts, arbitrary execution or AI were introduced. “Modern
tools” does not mean every Telegram Bot API method is supported or that a live API
version has been detected.

Saved user text, notes, filters, welcomes, files, polls and broadcast payloads
intentionally retain their native content/transport; presentation is not allowed
to rewrite user data. This migration standardizes command-facing UI and audited
navigation rather than blindly replacing business logic or bypassing permissions.
Latest validation: **80 Python tests passed**, compileall and all registered
module imports passed. New handler/API tests are offline mocks, not live Telegram
moderation, forum or voice checks. Production deployment remains pending.

## Full retained-command presentation pass

The 148 retained command names now use a shared command-facing Richgram adapter
for text send/reply/edit paths, with real navigation buttons and preserved
existing keyboards. Thirty command/runtime source files were migrated before
pause/resume were further consolidated behind `utils/music_actions.py`. Raw
user-payload delivery and structured media/poll APIs are intentional exceptions,
covered by source-level regression tests. The latest API/UI details and test
results are recorded in `docs/TELEGRAM_API_UPGRADE.md`. No removed demo commands
were restored. No deployment or live Telegram checks are claimed.

## Full application replacement in progress

The new `videl/app` runtime now owns 22 freshly implemented command names, including
moderation and music controls; their superseded handlers have been removed.
This supersedes the temporary `utils/music_actions.py` consolidation above.
See `docs/BOT_REBUILD.md` for exact coverage, safety limits, validation and the
remaining 126 legacy names. This is not yet the requested complete rewrite and
has not been deployed. Latest local validation: 128 Python + 36 frontend tests.
