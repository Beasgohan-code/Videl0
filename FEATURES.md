# Current feature boundaries

## Public creative workspace

- Post Studio with visual formatting, live preview and link-button design.
- Eight customizable image layouts, layer editing, JSON design import/export and PNG download.
- Local draft/recovery storage; downloadable plain text and native text sharing.
- Creator Tools: Unicode-aware caption counts, Telegram UTF-16 limit checks, unique hashtags and campaign URL builder.
- No login needed for creating or exporting. No bot telemetry or administrative tools are displayed.

## Verified owner workspace

Only Telegram account **6265999542** can authenticate. Bot-backed publication, chat sending, group rules, analytics, broadcasts and settings remain server-protected. Public users cannot publish through the owner's bot. The sign-in page explains signed Mini App and Login Widget flows; expiring HttpOnly cookies and sign-out are supported.

## Bot

Music playback/queue controls, group moderation and MongoDB-backed rules are retained. New Telegram tools include advanced polls/quizzes, permission-checked reactions and forum-topic actions. See [API details](docs/TELEGRAM_API_UPGRADE.md) for exact commands and eligibility caveats.

No AI or additional database integration is enabled. Do not infer working delivery, scheduling durability or production playback from UI labels or module counts. Live Telegram checks require the configured bot and appropriate chat permissions.
