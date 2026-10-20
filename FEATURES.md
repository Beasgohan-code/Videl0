# Current feature boundaries

## Public creative workspace

- Post Studio with visual formatting, live preview and link-button design.
- Image Library with 36 original, locally generated PNG assets — 24 wide covers (16:9), 6 story cards (4:5) and 6 quote cards (1:1) — plus up to 10 personal PNG/JPEG/WebP uploads stored in that browser. Regenerate the catalogue with `python scripts/create_post_assets.py`.
- Telegram-style rich editor in Post Studio and in the bot messenger: format by selecting text (bold, italic, underline, strike, spoiler, monospace, code block, quote, lists, links), premium emoji picker, live Telegram bubble preview, Telegram HTML view and a character counter.
- 20 customizable image layouts, layer editing, JSON design import/export and PNG download.
- Local draft/recovery storage; downloadable plain text and native text sharing.
- Creator Tools: Unicode-aware caption counts, Telegram UTF-16 limit checks, unique hashtags and campaign URL builder.
- No login needed for creating or exporting. No bot telemetry or administrative tools are displayed.

## Verified owner workspace

Only Telegram account **6265999542** can authenticate. Bot-backed publication, chat sending, group rules, analytics, broadcasts and settings remain server-protected. Public users cannot publish through the owner's bot. The sign-in page explains signed Mini App and Login Widget flows; expiring HttpOnly cookies and sign-out are supported.

## Bot

Smart Chat sends bot messages with Telegram HTML formatting (bold, italic,
underline, strike, mono, quote, spoiler, links) and premium custom emoji via
`<tg-emoji emoji-id="…">`; viewers fall back to the supplied character. Bots need
a Fragment username or a Premium owner (Bot API 9.4+) to send custom emoji.

Bot Inbox is a messenger-style client: chat folders, drafts, search, media
sending, replies, reactions, polls and a chat-info panel (profile, member count,
description, permissions, pinned message, invite link, bot admin status).
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
