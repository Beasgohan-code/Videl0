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
- **Scheduled publishing** — status counts, failure reasons and a retry that is
  only allowed for posts Telegram explicitly rejected; accepted or unconfirmed
  posts are never resent.

Boundaries: quiet hours only see messages delivered to the bot while it runs,
join requests are recorded from that point onward, and audit rows cover panel
changes plus bot-side lock, antispam, warning, filter, blacklist, join-request,
report and recording events.

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
