# Full bot replacement — staged migration

The requested target is a full bot rewrite with real music, moderation and useful
Telegram tools, using the locally maintained Badmunda05 Richgram fork. Preserve
the existing Post Studio webapp, MongoDB documents, deployment configuration and
third-party licenses. This is **not yet a completed full rewrite**.

## Current implementation

`videl/app/` is the replacement application. The production module list now loads
`modules/application.py`, which explicitly installs its router and navigation.
Importing the command manifest itself does not register Telegram handlers.

**22 command names are freshly implemented in the replacement application:**

- General: start, help, commands, ping, id, repo.
- Moderation: ban, tban, dban, unban, kick, dkick, mute, tmute, unmute.
- Music/queue: pause, resume, loop, shuffle, clear, queue, q.

Five obsolete modules have been deleted: start, ping, professional, pause, resume.
Their superseded handlers in misc, management_core, smartqueue, stop and
music_controls are removed too. The temporary shared music_actions adapter is
retired; its behavior is tested against the real replacement domain instead.

### Runtime guarantees and limits

- Immutable explicit command table; invalid names, permissions and duplicate
  registration are rejected. Bot mentions must match the current bot.
- Current Telegram membership is checked for each admin request. Moderation also
  requires the actor's specific Restrict members / Delete messages privileges,
  independently checks the bot's rights, and protects admin/owner targets.
- A single Richgram rendering boundary does not repeat an action when rendering
  fails. Provider errors are not copied into user-facing responses.
- At most 128 replacement actions run concurrently. The last 4096 completed
  chat/message IDs and all currently executing IDs suppress repeated updates.
  This is bounded in-process protection, **not durable exactly-once delivery**.
- New music controls serialize with one another per chat, preserve the current
  queue head, and change pause state only after voice-engine acknowledgement.
  Legacy stream callbacks do not yet share these locks.
- Migrated music controls and ID/source tools retain their existing MongoDB
  blocklist checks. Existing DB helpers' fail-open behavior during a database
  outage is unchanged, not a new fail-closed guarantee.
- Temporary bans/mutes validate 1 minute through 365 days. Kick uses a one-minute
  ban before release; partial release/deletion/audit outcomes are disclosed
  separately rather than automatically retrying a membership action.
- Unmute restores actual group default permissions, not fabricated broad rights.
- Owner totals and owner buttons only appear for account 6265999542 in private.
  Group use by that same owner never queries or displays private totals.
- All new screens use the existing MIT-licensed Badmunda05 Richgram fork and
  styled native buttons. Unsupported rich transports/styles retain the existing
  definite-rejection fallback; timeouts do not cause speculative resends.
  Telegram controls custom-emoji and premium-feature eligibility.

Existing Mongo collection shapes remain unchanged, including
`mgmt_banned_users`. No database migration, age-based data deletion or AI backend
has been added. Eldian and Richgram attribution/licenses remain intact.

## Remaining full-rewrite work

The command reference still contains **148 unique retained names**: 22 migrated
and 126 still provided by their functioning legacy domains. A reference entry or
passing mocked test is not proof that an external service works in production.

1. Replace search/play/vplay, replied files, channel playback and stream
   transitions. Unify player commands, buttons and stream-end callbacks under
   shared lifecycle coordination before removing the existing playback engine.
2. Migrate remaining moderation/protection: warnings, settings, notes, filters,
   locks, approvals, blocklists, federation and join/CAPTCHA workflows, preserving
   the existing Mongo document contracts.
3. Migrate playlists, AutoPlay, effects, seek/skip/replay/stop, downloads/lyrics,
   useful Telegram API commands, reminder/AFK plugins and owner operations.
4. Revalidate all names and callbacks, delete each superseded module after parity,
   then deploy and test real Telegram chats, Mongo and voice sessions.

Modern poll/quiz, forum controls, reactions, copy/forward, drafts and other Bot API
features from the previous upgrade remain available in the retained domains;
they have not all been rewritten into this router yet.

## Validation (local, offline)

- 128 Python tests passed, including replacement parsing, routing, permissions,
  registration rollback, duplicate updates, privacy, moderation partial outcomes
  and acknowledged music controls.
- 36 frontend tests passed.
- Python compileall, every production module import and git diff whitespace checks
  passed. The catalogue rejects duplicate names across old and new systems.
- No production deployment or live Telegram/Mongo/voice verification performed.
  Sandbox configuration lacks bot credentials and the Mongo connection string.

## Experience repair pass

After feedback that the whole bot experience was poor, the webapp was left
untouched. This pass repairs concrete onboarding/player inconsistencies:

- Public `/start` prioritizes adding the bot to a group and learning playback,
  rather than opening the already-working Post Studio. Private-chat copy explains
  that playback occurs in a group voice chat. Group-add URLs use the actual bot
  username and reject malformed usernames; Post Studio remains accessible.
- The setup button performs a read-only Telegram lookup of the bot's actual group
  privileges, lists missing rights and explicitly does not certify assistant,
  voice-chat or provider readiness. It never changes settings or memberships.
- Pause/resume, repeat-cycle, clear and queue buttons now delegate to the same
  domain functions and authorization as slash commands, via the existing callback
  dispatcher. Authorization uses the clicking user, never the bot-authored player
  message's author. Saved user/group block checks apply on both paths.
- Repeat-cycle clicks are serialized inside the shared control lock. Callback IDs
  have bounded in-process duplicate suppression. Callback answer failures never
  retry a voice action or issue a contradictory failure answer after success.
- A player-card refresh error cannot turn an acknowledged pause into "failed to
  pause". Clear consistently keeps the current track and disables AutoPlay.

Validation: **143 Python tests passed**, including 15 new experience regressions
that call the real callback dispatcher and verify the underlying action boundary;
compileall, production module imports and diff whitespace checks passed. The
webapp is unchanged in this pass; its previously verified 36 frontend tests remain
separate. These are offline checks, not live end-to-end playback or moderation
verification. The remaining full rewrite is still outstanding, including legacy
skip/stop/replay/stream-end lifecycle coordination. No deployment was performed.
