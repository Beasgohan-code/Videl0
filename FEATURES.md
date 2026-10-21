# Current feature boundaries

## Public creative workspace

- Post Studio with visual formatting, live preview and link-button design.
- Image Library with 36 original, locally generated PNG assets — 24 wide covers (16:9), 6 story cards (4:5) and 6 quote cards (1:1) — plus up to 10 personal PNG/JPEG/WebP uploads stored in that browser. Regenerate the catalogue with `python scripts/create_post_assets.py`.
- Telegram-style rich editor in Post Studio and in the bot messenger: format by selecting text (bold, italic, underline, strike, spoiler, monospace, code block, quote, lists, links), premium emoji picker, live Telegram bubble preview, Telegram HTML view and a character counter.
- 20 customizable image layouts, layer editing, JSON design import/export and PNG download.
- Brand kits save the palette, font, layout, logo and export footer; applying a kit restores
  them, and the logo and footer are painted onto every PNG export. Up to 20 kits live in
  this browser.
- Local draft/recovery storage; downloadable plain text and native text sharing.
- Creator Tools: Unicode-aware caption counts, Telegram UTF-16 limit checks, unique hashtags and campaign URL builder.
- No login needed for creating or exporting. No bot telemetry or administrative tools are displayed.

## Verified owner workspace

Only Telegram account **6265999542** can authenticate. Bot-backed publication, chat sending, group rules, analytics, broadcasts and settings remain server-protected. Public users cannot publish through the owner's bot. The sign-in page explains signed Mini App and Login Widget flows; expiring HttpOnly cookies and sign-out are supported.

## Group operations

The owner panel manages the served fleet from one screen, and every control maps
to code that actually runs:

- **Group Manager** — per-group drill-down with health (derived from stored
  settings, waiting join requests and the last Telegram read), an aggregate
  "needs attention" queue ranked worst-first with the recorded reasons, protection
  presets, greetings, rules, captcha, warnings, notes, filters, blacklist,
  approvals, join-request triage (approve/decline), report triage (warn, ban,
  resolve or dismiss) and a per-group audit trail
  (filterable by kind, paged with an exact cursor, CSV export, 180-day
  retention). Bot-side changes — locks, antispam, warnings, filters, blacklist
  words or its mode — are recorded too, with the acting admin when Telegram
  reports one.
- **Group backups** — download a group's configuration as JSON (locks,
  greetings, rules, automation, blacklist words and switched-off commands) and
  import it into another group. Imports are previewed as a diff and applied
  only on confirmation; the replaced state is saved so the import can be
  undone. Warnings, notes and member identities are never written to the file.
  The export endpoint is `/internal/chat/<id>/backup`; imports post
  `backup_import` / `backup_restore` to the usual group endpoint.
- **Command switches** — any of the 155 registered commands can be turned off
  for one group. A handler at group −1 refuses it before every other handler,
  so this also covers commands that never pass through the declarative router.
  Group admins and the bot owner stay exempt.
- **Warning ladder and decay** — the warning limit can run an ordered ladder
  (`mute → kick → ban`): the first time a member reaches the limit the first
  step runs, the next time the second, and the last step repeats. A ladder is
  written gentlest-first and the backend drops any rung that would weaken a
  repeat offender's action. `decay_days` (0–365) makes warnings older than the
  window stop counting, so a member who behaves starts fresh: once every
  warning has lapsed the ladder restarts at its gentlest rung instead of
  resuming where the member left off. Warnings without a timestamp are kept,
  never assumed old. `/warnings` shows the active count,
  what lapsed and when the next one expires, and the bot and the panel's report
  triage reach the same verdict for the same member. Each warned member has a
  case file: every warning on record with its date, the lapsed ones struck
  through rather than hidden, what still counts, and when the next one lapses.
  One button opens the group history filtered to that member.
- **Automation** — quiet hours delete member messages inside a stored window
  (per-group UTC offset, admins and approved members exempt), scheduled
  protection windows turn chosen locks on and release only the locks they
  turned on themselves, and the warning ladder chooses ban, temporary mute,
  kick or nothing at the warning limit. The watchdog applies windows every
  minute and writes a `protection_window` audit row per change.
- **Federations** — read-only overview of federations, member groups, admins and
  bans, with ban lifting. Creating federations and issuing bans stays on the bot
  commands, where the caller is verified against Telegram.
- **Release check** — Settings compares the Vercel commit with the backend's
  `revision` and reports drift instead of guessing, plus the measured p95 of
  the backend's internal API calls (the last 400 requests it served).
- **Honest health** — `/health` keeps `status: "ok"` while the HTTP API answers,
  so an uptime monitor does not flap when Telegram is down, and adds `degraded`
  with one reason per broken part (bot, MongoDB, watchdog) plus a redacted
  `bot_error` from the last failed start. The panel shows that reason on the
  control room and in Settings instead of only "connection not confirmed"; the
  bot token and other long credentials are stripped before the text is served.
- **Scheduled publishing** — status counts, failure reasons and a retry that is
  only allowed for posts Telegram explicitly rejected; accepted or unconfirmed
  posts are never resent. A rate limit (HTTP 429) is the one failure the queue
  handles alone: the job returns to the queue for the interval Telegram asked
  for, up to three times, and the monitor shows each automatic attempt. A
  terminal failure is posted once to the log channel with the chat, job id and
  the reason Telegram gave. A finished post can be copied into a new job at a
  time you pick (an hour ahead by default) — the copy is a fresh post, so the
  original is never resent, and a job still in the queue has to settle first.
  A schedule can repeat **daily or weekly** at the same UTC hour: one record
  carries the series, moving itself to the next occurrence after each accepted
  delivery, so the monitor shows a single line with a delivered count. A
  failure stops the series and waits for the owner; a series that fell more
  than a day behind skips the missed copies (and says how many) instead of
  sending them in a burst. Cancelling a repeating post stops it.

Retention: activity counters, delivered reminders and finished (`sent` or
`cancelled`) scheduled-post rows are pruned at the configured window. Failed and
unconfirmed sends are kept, because they are the records someone will come back
to read.

Boundaries: quiet hours only see messages delivered to the bot while it runs,
join requests are recorded from that point onward, and audit rows cover panel
changes plus bot-side lock, antispam, warning, ban/kick/mute/unban, filter,
blacklist, join-request, report, backup and recording events. History is
searchable by detail and filterable by actor, with an exact cursor for paging.

## Bot

Smart Chat sends bot messages with Telegram HTML formatting (bold, italic,
underline, strike, mono, quote, spoiler, links) and premium custom emoji via
`<tg-emoji emoji-id="…">`; viewers fall back to the supplied character. Bots need
a Fragment username or a Premium owner (Bot API 9.4+) to send custom emoji.

Bot Inbox is a messenger-style client: chat folders, drafts, search, media
sending, replies, reactions, polls, forwarding and a chat-info panel (profile,
member count, description, permissions, pinned message, invite link, bot admin
status). Chat avatars use the real Telegram profile photo, resolved through an
owner-only proxy with gradient initials as the fallback, and consecutive
messages from one sender are grouped the way Telegram renders them.
Formatting captured from Telegram message entities is stored as safe HTML, so
incoming bold, code, spoilers and premium emoji render in the viewer instead of
being flattened. Premium emoji artwork is resolved server-side through
`/api/premium-emoji` so the bot token never reaches the browser.

Music playback/queue controls, group moderation and MongoDB-backed rules are retained. New Telegram tools include advanced polls/quizzes, permission-checked reactions and forum-topic actions. See [API details](docs/TELEGRAM_API_UPGRADE.md) for exact commands and eligibility caveats.

No AI or additional database integration is enabled. Do not infer working delivery, scheduling durability or production playback from UI labels or module counts. Live Telegram checks require the configured bot and appropriate chat permissions.

## Lean command surface

Demo `/buttons` and `/features`, raw `/logs`/`/log` delivery, and redundant aliases
have been removed. Canonical music, moderation, forum, copy, reminder and owner
maintenance commands remain. The current registered set (including the few
retained common aliases) is in [the generated command reference](docs/COMMAND_REFERENCE.md).
No database records, saved media, credentials or licensed vendor components are
deleted by this source cleanup. Changes require backend deployment to take effect.
