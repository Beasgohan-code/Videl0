# Telegram API and bot UI upgrade

## Verified sources (20 October 2026)

- Official Bot API server source: https://github.com/tdlib/telegram-bot-api/tree/e3e9dd8e5b3d7ab8537cd5a10dc31d5ffa8f82d1
  - CMakeLists.txt declares **10.3**. This is the audited source version, not a claim about the running Telegram server; `getMe` does not report its API version.
  - `Client.cpp`: ordinary inline keyboard `style` / `icon_custom_emoji_id`, `sendRichMessage`, `sendMessageDraft`, `setMessageReaction`, forum-topic endpoints, and advanced poll fields.
- Maintained Kurigram 2.2.26 installed types: `ButtonStyle`, `InlineKeyboardButton`, `CopyTextButton`, rich messages, forum routing, and drafts. Current pinned client already supports these types; replacing it with archived Pyrogram would break compatibility.
- Custom emoji button eligibility: https://github.com/python-telegram-bot/python-telegram-bot/blob/master/src/telegram/_inline/inlinekeyboardbutton.py
- Existing Richgram fork: https://github.com/Badmunda05/richgram — original MIT license retained at `vendor/richgram/LICENSE`. Videl's fallback changes are local to that fork.
- Eldian Network music downloader and attribution remain intact.

No external bot code or emoji packs were blindly imported. Existing configured IDs are retained, not claimed universally valid. `/emojiinfo check` asks Telegram to resolve them at runtime.

## Integrated

| Area | Implementation |
| --- | --- |
| Bot UI | Shared semantic native keyboard factory: primary Studio actions, success confirmations, danger destructive actions; stable existing callback data and URLs. Adopted by active modules, shared plugin runtime and music controls. |
| Rich cards | Existing rich-message engine retained; one semantic premium icon in bot-authored headings, readable HTML fallback. User message bodies are not rewritten. |
| Music | Generated 1280×720 now-playing posters with track artwork, an original Videl record-sleeve layout, cover-derived accent colors, artist/requester chips and a decorative waveform; live playback progress stays in the editable caption. Pillow is optional and falls back to the existing thumbnail/rich card. Native controls, callback payloads and voice streaming APIs remain unchanged. |
| Start | Rich/text welcome rather than an unreliable external image/caption fallback chain; no repeated sends after ambiguous network failures. Mini App launch buttons preserve signed identity in private chats. Missing database counts say Unavailable, not zero. |
| Polls | `/poll [flags] Question | A | B`; optional multiple answers, public identity, shuffle, added options, hidden results and members-only voting. Anonymous by default. |
| Quizzes | `/quiz Question | *Correct | Other`, including multiple *correct answers through current `correct_option_ids`. Strict question/option validation; same-topic delivery. |
| Reactions | `/react 👍` or `/react clear` on a reply, restricted to owner/group admins. Telegram's allowed-chat reactions still apply. No automatic reactions or paid reactions. |
| Topics | `/topicnew Title`, `/topicclose`, `/topicopen`; forum/admin checks, explicit refusal to alter the General topic through these commands. Bot must have Telegram topic-management permission. |
| Copy buttons | Actual `CopyTextButton` actions in owner ID/emoji diagnostics. |
| Diagnostics | Owner-only `/apiinfo` verifies bot identity; `/emojiinfo` extracts replied custom emoji IDs; `/emojiinfo check` resolves configured IDs without claiming rendering eligibility. |
| Menus | A canonical public command menu used by startup and Studio sync; an additional owner-private menu on startup. `/help`, `/commands` and the Start/help buttons explain the new tools. |
| Transport | Bounded HTTP calls outside the event loop; no tokens/URLs in exception logs. A definite HTTP 400 may retry without visual extras, preserving destinations, privacy options and button actions. Timeouts, 429s and server errors are never automatically retried. |

## Eligibility and safety

`USE_PREMIUM_EMOJI=0` disables custom emoji text; `USE_PREMIUM_BUTTON_ICONS=0` disables custom icons while keeping native button styles. Telegram imposes Premium/Fragment and message-context restrictions. Possessing an ID is not permission to render it. Known visual rejections can fall back to readable text and icon-free keyboards without mutating shared keyboard instances.

“All new API features” is not a single safe switch. These changes do **not** enable Stars spending, paid broadcasts, gifts, payments, business-account impersonation, webhook replacement, or automatic reactions. Drafts and other SDK capabilities are available but are not exposed as user-facing features unless integrated. They require separate product decisions, credentials and permission testing.

PyTgCalls 3.x / NTgCalls 3.x are separate breaking voice-engine upgrades, not Bot API UI updates. Existing known-compatible versions remain pinned; dependency version numbers alone are not evidence of working playback.

## Validation and rollout

Run `.venv/bin/python -m unittest discover -s tests -q` and import all `ALL_MODULES` offline. Tests mock network calls, confirm topic/admin checks, preserve callback actions, exercise emoji rejection fallbacks, and prohibit duplicate sends after ambiguous timeouts. No real messages, reactions, topics or polls are created by the tests.

The **Render backend must deploy this commit** for bot handlers/UI changes to take effect; Vercel alone cannot update a running bot. Live custom emoji eligibility, real voice playback, and Telegram admin rights still need verification on the configured bot. Do not paste bot tokens into chat.

## Complete command presentation follow-up

Active command text sends, replies and edits now explicitly import the adapters
in `videl/utils/command_ui.py`. These call the vendored Badmunda05 Richgram engine;
there is no global monkey patch. Feedback without a heading gets a consistent
card heading (without exceeding the visible message limit), and feedback without
existing controls gets real Guide/Commands buttons. Explicit keyboards, rich
inline action markup, edit-time keyboard removal, thread/quote/privacy options
and return values are preserved. Existing destructive/admin actions still run
through their original permission guards. Saved user payloads stay native.

`/start` now separates public creation/music from private owner metrics and owner
navigation. The help center uses readable rows and category navigation.
Pause/resume use one acknowledged path: a failed player-card refresh no longer
misreports a confirmed voice-engine state change as a failed pause/resume.

Additional poll flags: `--silent`, `--protect`, `--seconds=60` (5–600 seconds).
These send actual `disable_notification`, `protect_content` and `open_period`
fields; malformed timers fail before Telegram is called. Forum results include
styled Close/Reopen controls whose callbacks check the message's chat and current
admin privileges on every click. General-topic actions are refused. `/apiinfo`
and `/emojiinfo` are exact-owner/private only.

Removed demo commands remain removed; the command catalogue is generated from
registered handlers, including aliases. New features are added to useful existing
commands, not reintroduced as showcase commands. The implementation does not
claim support for every Bot API method or universal client support.

Validation at the original integration checkpoint: 97 Python tests and 36
frontend tests passed; compilation and all registered module imports passed. Tests include real Richgram-to-native
fallback rendering with mocked Telegram calls, explicit keyboard preservation,
public/owner start separation, native transport exceptions, topic callbacks and
poll validation. Production rollout and live voice/forum/poll verification remain
pending; deploying the frontend alone cannot update the bot handlers.
