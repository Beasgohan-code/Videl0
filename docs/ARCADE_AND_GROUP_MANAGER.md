# Plan: public games with live chat, Telegram sign-up, and a group manager

Status: **partly shipped.** The identity layer, the seven games (Chess,
Checkers, Five in a Row, Connect Four, Reversi, Tic-tac-toe, Ludo),
server-authoritative rooms with chat, live voice and timeouts,
the arcade screen, and the group-manager backend are in the repository and
tested. The group-manager screen, presence-based SSE and voice remain. Where
this document and the code differ, the code and its tests are the truth.

## Verdict first

| Ask | Feasible? | Shape |
| --- | --- | --- |
| Public multiplayer games | **Yes** | Rooms in the panel, server-authoritative rules, no accounts to create |
| Live text chat + presence | **Yes** | Server-sent events from the Render backend, short polling as fallback |
| Telegram sign-up | **Yes** | The Mini App already proves who you are; reuse that proof for everyone, not only the owner |
| Live **voice** chat | **Partly** | Voice lives in Telegram's own group voice chat (free, reliable). In-panel real-time audio is a gated spike: it needs TURN and fights iOS WebView |
| Group manager for admins | **Yes, and it is the smaller half** | Reuses `GroupView`, but only after an actor refactor — see §3.4, the current code acts as the owner |

The two features share one thing that does not exist yet: **an identity for
people who are not the owner.** That is why it is phase 0.

---

## 0. What the platform actually allows

These constraints decide the design; they are not preferences.

1. **Vercel holds no state.** Every room, move, message and rating lives in
   MongoDB behind Flask on Render. The panel only renders and calls
   same-origin `/api/*` routes, as it already does for schedules and groups.
2. **The Mini App can record audio, but cannot talk in real time for free.**
   `getUserMedia` works inside Telegram's WebView (Android grants it per
   WebView session, iOS through WKWebView). What it cannot do is reach another
   player's browser: that needs a signalling channel *and* a TURN relay for
   symmetric NAT, which is a paid or self-hosted component. Telegram WebApps do
   not expose a voice-room API.
3. **Telegram's own voice chat is free and reliable.** The bot already joins
   group calls through `call_py` (`videl/core/call.py`, `videl/core/player.py`).
   A room bound to a group can hand voice off to Telegram and lose nothing.
4. **One Flask process, 0.1 CPU on the free Render instance.** Long-lived
   connections are fine in small numbers; a hundred players polling every
   second are not. The transport below is chosen to keep both costs low.
5. **The Bot API is the only way to reach a player outside the panel.** A
   player can only be messaged if they have started the bot. Sign-up must
   therefore *end* with a bot chat, not instead of one.

---

## 1. Identity: "sign in with Telegram", for anyone

Today `POST /internal/auth` (`videl/__main__.py`, `_internal_auth`) verifies a
Mini App signature and then rejects anyone who is not `6265999542`. The
verification is good; only the last assertion is owner-specific.

### What changes

- Extract the HMAC check into `videl/utils/telegram_auth.py` *(new)*:
  `verify_init_data(init_data, bot_token)` and `verify_login_widget(data, token)`,
  returning `{id, first_name, last_name, username, photo_url, auth_date}` or
  raising a typed `AuthError`. No behaviour change; the same code is moved.
- `_internal_auth` keeps its owner assertion and calls the helper.
- **New** `POST /internal/identity` verifies either form and returns the user.
  It does not grant owner power; it says "this is who Telegram says you are".
- The panel's `/api/auth` route keeps minting `videl_owner`. **New**
  `/api/session` mints a separate `videl_player` cookie:

```
videl_player = base64url({sub, name, iat, exp, nonce}) + "." + HMAC(
    WEBAPP_SECRET, "videl-player-v1:" + payload)
```

  TTL 30 days, HttpOnly, Secure, SameSite=Lax, plus the `Partitioned`
  `SameSite=None` twin the owner cookie already has for embedded WebViews
  (`webapp/src/lib/auth.ts`).
- The signing prefix is different from the owner token (`videl-session-v2:`).
  A player token can never validate as an owner token, and the existing
  `validOwnerCookie` keeps ignoring `videl_player` because of its name check.

### Player record

```js
players = {
  _id: <telegram id>, name, username, photo_file_id,
  created_at, last_seen, dm_ok: bool,
  stats: {connect4: {w,l,d,rating}, reversi: {...}, quiz: {best, plays}},
  flags: {muted_until, banned, reason}
}
```

`dm_ok` is set the first time the player opens the bot (`/start`), never
guessed from a Mini App launch.

### Limits that keep this honest

- Sign-in is **Telegram-only**. There are no passwords, no email, no
  "continue as guest" for writing. Spectators may read public rooms without
  signing in; they cannot chat or move.
- The name shown is the Telegram name, verified from `initData`; the panel
  cannot edit it. Display names inside a room are the Telegram ones, so
  impersonation costs an account.
- No scopes are stored in the cookie. Admin rights are looked up live (§3.1),
  so revoking an admin takes effect within minutes, not at token expiry.

---

## 2. The arcade

### 2.1 Rooms

A room is one document and one code.

```
game_rooms = {
  _id: "K7M2QX",                 // 6 chars, no I/O/0/1
  game: "connect4" | "reversi" | "quiz",
  visibility: "private" | "public",
  host: <player id>,
  seats: [{user, name, seat, joined_at, last_seen}],   // 2 or up to 8 for quiz
  status: "open" | "playing" | "done" | "abandoned",
  turn: 0,                        // seat index, or null between rounds
  state: {...},                   // game-specific, server-owned
  version: 37,                    // incremented on every accepted move
  seq: 412,                       // incremented on every move *and* message
  deadline_at: ISODate,
  chat_id: null,                  // optional Telegram group binding
  created_at, expires_at,
  password_hash: null             // optional, bcrypt via werkzeug
}
```

`seq` is the single cursor for "what is new in this room", which lets one
request return both the board and the chat.

Lifecycle:

```
open ── seats full / host starts ──▶ playing ── result ──▶ done
  │                                     │
  └──── 30 min, <2 players ─────────────┴──── no move for 24h ──▶ abandoned
```

Two players may not hold the same seat; leaving mid-game is a forfeit after a
30-second grace period (a page reload must not lose the game).

### 2.2 Games for v1

| Game | Players | Turn timer | Why this one |
| --- | --- | --- | --- |
| **Connect Four** | 2 | 60 s live / 24 h async | Rules fit in 200 lines, provably testable, instantly understood |
| **Reversi** | 2 | 90 s / 24 h | Zero content, deep play, works asynchronously |
| **Tic-tac-toe** | 2 | 45 s / 24 h | The fastest complete game; a whole room can be played in a minute |
| **Chess** | 2 | 180 s / 24 h | The game people arrive asking for; full FIDE move generation rather than a subset |
| **Five in a Row** | 2 | 60 s / 24 h | One rule, 225 intersections, and the board reads well on a phone |
| **Checkers** | 2 | 75 s / 24 h | Draughts with the two rules that decide real games: compulsory captures and the longest chain; kings fly |
| **Ludo** | 2–4 | 45 s / 24 h | The game people ask for by name: a shared board, more than two seats, and chance that keeps every seat in it |

Deliberately **not** in v1: anything needing a dictionary (word games), real
physics, or licensed content. A bundled word list is a licensing and quality
problem, not a UI problem.

Checkers is the same bargain as Ludo: the panel draws and offers, the engine
decides. Captures are compulsory and the **longest** chain is the only legal
one; a man crowned on the eighth row ends its move there; kings fly the full
diagonal and may land anywhere beyond the captured piece; a side with no legal
reply loses (which is also how the corner trap resolves). The server sends the
complete chains — `{from, to: [...], via: [...]}` — so a tap can only ever send
a move that already existed, and a double jump is one tap rather than a
half-finished chain the client has to remember.

Ludo ships with two simplifications, stated to the player in the room rather
than discovered mid-game: tokens may stack on one square (no blocking), and the
first player home wins the room instead of play continuing for second place.
The board is the classic 52-square ring with eight safe squares (the four start
squares and four stars), a six to leave the base, an extra turn on a six, and
three consecutive sixes forfeiting the turn. Every rule lives in
`videl/games/ludo.py`; the panel only draws it.

A future **Quiz Rush** keeps one non-obvious rule: **the answer never reaches
the client before the reveal.** `state` for a live question would contain the
prompt and the four options; the correct index is written only into the
`reveal` event after every player answers or the timer expires.

### 2.2a The invite is an address, not a tab

A room is shared as `https://videl-studio.vercel.app/play/CODE`, which is its
own route (`webapp/src/app/play/[code]/page.tsx`) rather than `/?tab=arcade`.
A link pasted into a group has to open in whatever browser the reader has,
without the panel first deciding which tab it is on, and the code has to be in
the preview. The page paints the invitation immediately (the room code, the
art, one Telegram button) and only swaps to the table when `/api/session` says
this browser already holds a player cookie. `?tab=arcade&room=CODE` still
works for in-app navigation, and pasting any of the three shapes — a bare code,
a `/play/` link, or a `t.me/...?startapp=` payload — into the join field is
accepted by `codeFromLink()`.

The art in `webapp/public/arcade/` is original to this repository, generated
for the lobby and the invite page; nothing is loaded from a third-party CDN.

### 2.2b Voice at the table

Voice is peer-to-peer WebRTC in a mesh — one connection per pair of seats, so a
four-seat table is six connections and nothing needs an SFU. There is no second
socket: a signal is written by the backend as an ordinary room event
(`action: "rtc"`, addressed with `to`) and reaches the browser on the stream the
room already polls every 2.2 s. Joining a room is therefore the only thing that
has to succeed for voice to work, and leaving it stops voice for free.

Two consequences are stated in the UI rather than hidden:

* Telegram's in-app webview often refuses `getUserMedia`. That is a first-class
  state (`blocked`) with a sentence that names the fallback — Chrome/Safari, or
  voice notes over the room chat.
* The microphone starts **muted**, and speaking is push-to-talk (hold the
  button or the space bar). An open mic in a four-seat room is a bug, not a
  feature.

Signals are rate-limited separately from chat (240 per minute, 50 ms apart) and
capped at 3 KB in the backend and 2.6 KB at the webapp door, because an SDP is
much larger than a message and neither should be a way to fill the event log.

### 2.3 Timeouts without a timer thread

The watchdog ticks every 60 s (`videl/core/watcher.py`), which is too coarse for
a 60-second turn. Instead, a deadline is applied **lazily on every read and
every write**, in the same compare-and-set that the action already needs:

```python
def settle(room, now):
    """Apply a deadline at most once, whoever notices it first."""
    if room.status == "playing" and room.deadline_at <= now:
        return advance_on_timeout(room)   # forfeit, or random legal move
    return room
```

`advance_on_timeout` is itself a `find_one_and_update` guarded by
`{_id, status: "playing", version: room.version}`. Two players polling at the
same instant cannot both apply it. A 60-second sweep in the watchdog catches
rooms nobody is watching, so a game still resolves (and can notify the absent
player) when both tabs are closed.

This is the same pattern as `skip_next` in `videl/utils/scheduled_posts.py`:
read, decide, write with the old value in the guard, 409 when it moved.

### 2.4 Transport: SSE, with polling as the fallback

Polling every second through Vercel would spend the Hobby plan's entire request
allowance on a busy evening. Instead:

1. The panel calls same-origin `POST /api/arcade/ticket` (cookie-authenticated)
   and gets `{endpoint, ticket}` where `ticket` is HMAC-signed for exactly that
   room and user, valid 90 seconds.
2. It opens `EventSource(https://<render>/stream/room/<code>?ticket=...)`.
   Render keeps the connection open and pushes `state`, `event`, `presence`
   frames. A ping every 20 s keeps proxies from closing it.
3. The backend keeps one in-process subscriber list per room. A write notifies
   subscribers directly; a room with no subscribers costs nothing.
4. If SSE fails twice, the client falls back to `GET /api/arcade/room/<code>
   ?after=<seq>` every 3 s for the rest of the session, and says so quietly in
   the corner ("Live updates paused — refreshing every few seconds").

On Render's free instance (~50 idle threads is comfortable) this supports a few
dozen concurrent rooms. Beyond that the answer is a $7 Starter instance, not a
cleverer client.

### 2.5 Voice, in three honest tiers

| Tier | What the player gets | Cost | Risk |
| --- | --- | --- | --- |
| **A. Telegram voice chat** (recommended, ships with v1) | A **Join voice** button in the room that opens the bound group, where Telegram's own voice chat is already running. The bot announces rounds in that group and can stream lobby audio with `call_py`. | 0 | None; it is Telegram's feature |
| **B. Voice notes in the room** (v1.1) | Hold to record up to 15 s; the clip is uploaded and plays inline for everyone in the room. Works in any browser, no TURN. | MongoDB storage, ~60 KB per note, 24 h TTL | Permission prompts per WebView session on Android; audio blocked until a tap |
| **C. Real-time panel voice** (spike only) | WebRTC mesh, 2–4 players, push-to-talk. | TURN relay (Metered/Twilio free tier or a $5 coturn VPS) + signalling over the SSE channel | iOS WebView audio session, echo cancellation, NAT; 3–4 weeks and still fragile |

Tier A is what "live voice chat" should mean here: it is genuinely live, free,
and does not depend on a WebView behaving. Tier B covers "I want to hear a
teammate without leaving the panel". Tier C is only worth funding if A and B
prove insufficient.

**The bot cannot speak through a microphone.** Telegram forbids bots from
joining calls; only the assistant user session can, and it can only play
audio. Nothing in this plan pretends otherwise.

### 2.6 Chat, presence and moderation

- 400 characters, plain text, escaped on render (`cleanTelegramHtml` is not the
  right tool here — room chat is not Telegram HTML and must be shown literally).
- Rate: 1 message/second, 30/minute, 200 undelivered per room. Exceeding it is
  a 429 with a retry hint, not a silent drop.
- Presence comes from the SSE connection plus `last_seen`, not from a stored
  flag: a crashed tab stops counting in 60 s.
- Typing indicators are ephemeral, 3-second TTL, never written to Mongo.
- **Report** on any message writes `game_reports` and gives the room host a
  one-tap mute. Repeated reports on one player auto-mute for an hour pending
  review. The owner sees the queue in the existing audit surface rather than a
  new moderation app.
- A public room lists only rooms its host marked public; private rooms are
  reachable by code only. Blocked pairs (`player_blocks`) cannot share a room.
- Retention: messages and rooms expire 24 h after the last move; chat events 7
  days; a finished game leaves one aggregate row in `game_records` (no message
  content) so leaderboards and history survive.

### 2.7 Ratings and leaderboards

Elo for the two-player games only: K=32 while provisional (first 10 games),
K=16 after; a rating never drops below 100. Quiz keeps a weekly score board and
a personal best, not a rating — ranking a party game by Elo produces noise.

Leaderboards are a Mongo aggregation over `players.stats` (top 50, per game,
all-time and this week from `game_records`). No separate ranking service, no
materialised table to keep consistent.

### 2.8 Group integration

- A room launched from inside a group gets `chat_id` and appears in that
  group's admin panel under **Games**.
- On a turn change the bot posts one message to the group *only* if the
  recipient is not currently connected: `<a href="tg://user?id=…">Name</a>,
  it's your move in Connect Four`, with a `web_app` button back to the room.
  One message per turn, never per poll.
- Results post once. Chat is **not** mirrored into the group by default:
  echoing a public room's chat into a group turns a game into a firehose. A
  room owner may opt in, and the mirroring is rate-limited and labelled.

---

## 3. The group manager

### 3.1 Who may do what

| Scope | Who | How it is proved |
| --- | --- | --- |
| Owner console | `6265999542` | existing `videl_owner` cookie |
| Group manager | Any current Telegram admin of that group | `videl_player` cookie **plus** a live `getChatMember` check |
| Player | Any Telegram user | `videl_player` cookie |

Admin status is **never** stored in the cookie. It is checked against a
`chat_admins` cache (below) and, for any write, against the exact right the
action needs — `can_delete_messages`, `can_restrict_members`,
`can_invite_users`, `can_pin_messages` — through the existing
`GroupView.rights()` (`videl/utils/group_view.py`), which already compares both
the actor and the bot.

### 3.2 What a group admin can and cannot do

**Can:** protection toggles, welcome/goodbye/rules, notes, filters, blacklist,
warning limit, warn/reset, mute/ban/kick with reason, reports, join requests,
disabled commands, history for their group, games for their group, bot-rights
repair links.

**Cannot:** backup import/restore, inbox recording or purging, broadcast,
federations, analytics across groups, the fleet list, or anything that changes
another group's settings. Those stay owner-only, in the existing `Groups`
screen.

That split is not cosmetic. Handing an admin `backup_import` lets them
overwrite protection state; handing them `recording` lets them start capturing
member messages. Both must be unreachable, not merely hidden in the UI.

### 3.3 Screens

New section `manager`, reachable at `/?tab=manager`, no owner gate:

1. **Your groups** — every group where the caller is an admin, with member
   count, bot health dot and "3 reports waiting".
2. **Group card** — the focused subset above, laid out for a phone: sticky save
   bar, revision-guarded writes (the 409 contract from `1d6572c` already says
   "this changed, here is the current revision").
3. **History** — the same audit rows the owner sees, filtered to that group.
4. **Fix the bot** — one screen listing missing rights with a "Grant" deep link
   into Telegram's admin settings. This is where the existing boolean
   `permission_rows` (`videl/utils/permission_diagnostics.py`) becomes three
   states: granted / missing / could not be read.

### 3.4 The refactor that must happen first

`GroupView` currently assumes the owner is the actor:

- `access(chat_id)` calls `getChatMember` for `OWNER_ID` and **refuses the group
  unless that account is currently an administrator** (`group_view.py`). A group
  the owner has left cannot be managed at all — not even by its own admins.
- `log()` writes `actor=OWNER_ID` into the audit trail.
- `rights()` then checks that actor's Telegram rights — correct for the owner,
  **silently wrong** for anyone else.

So a naive `/internal/manager/chat/<id>` that reuses these routes would let any
group admin act, and be recorded, as the owner — including `backup_import`.
The fix is small but must land before the first admin route:

```python
class GroupView:
    def __init__(self, db, api, actor=OWNER_ID, scope="owner"):
        self.actor, self.scope = actor, scope
    def access(self, chat_id): ...          # uses self.actor
    def log(self, cid, action, body=None):  # actor=self.actor
    ...
```

plus a `SCOPES = {"owner": ..., "admin": {...allowlist...}}` check at the top of
`act()` so an admin request for `backup_import`, `backup_restore`, `recording`
or `purge_history` raises 403 before touching anything. `join_request` and
`report_update` stay available to admins — resolving a join request is their
job — but they are attributed to the admin, not the owner.

Every existing call site keeps `actor=OWNER_ID` by default, so the owner path
does not change behaviour and the current 439 tests stay green.

### 3.5 Finding an admin's groups without hammering Telegram

`getChatMember` is one request per group per user. For a bot in hundreds of
groups that is unusable during sign-in. Instead:

- `chat_admins` *(new collection)*: `{_id: "<chat>:<user>", chat, user, status,
  rights, checked_at}`, one row per admin per group.
- A watchdog job (`videl/core/watcher.py`, alongside `_dispatch_scheduled`)
  refreshes a rolling slice — e.g. 20 groups a minute — from
  `getChatAdministrators`, so the whole fleet is current every two hours.
- Opening one group refreshes that group immediately (one call).
- Every manager write re-checks the specific user/chat if the cache row is
  older than 5 minutes, and **any** 403 from Telegram forces a re-check. A
  demoted admin loses access within minutes, and always before the next write
  succeeds.

### 3.6 Endpoints

Panel (same-origin, cookie-authenticated):

```
POST /api/session                 sign in (initData or login widget)
GET  /api/session                 who am I
GET  /api/manager/groups          groups I administer
GET  /api/manager/groups/<id>     focused describe (no inbox, no backup)
POST /api/manager/groups/<id>     an allowlisted action
GET  /api/manager/groups/<id>/audit?before=
```

Backend (`X-Videl-Internal` secret + a signed actor assertion):

```
POST /internal/identity
GET  /internal/manager/groups?actor=<id>
GET  /internal/manager/chat/<id>
POST /internal/manager/chat/<id>
GET  /internal/manager/chat/<id>/audit
```

The actor assertion is `X-Videl-Actor` + `X-Videl-Actor-Sig` =
`HMAC(WEBAPP_SECRET, actor|chat|exp|nonce)`, valid 60 s. A leaked Vercel→Render
secret is already game over; this makes a leaked *route* insufficient on its
own, and gives the backend a value it can attribute instead of trusting a
number in a header.

---

## 4. Security checklist

- [ ] Owner cookie and player cookie are different names, different signing
      prefixes, different TTLs; a player token cannot open an owner route.
- [ ] `/internal/manager/*` requires the actor signature; `/internal/chat/*`
      stays owner-only (`_internal_authorized`).
- [ ] Admin power is re-read from Telegram, never cached in the cookie.
- [ ] Cross-chat: an admin of A calling B gets 403 even if both are in the
      cache; the check is `(chat, user)`, not `user`.
- [ ] CSRF: existing origin + `Sec-Fetch-Site` guard, reused
      (`webapp/src/lib/auth.ts`).
- [ ] Room mutations are compare-and-set; a replayed move is a 409, not a
      second move.
- [ ] Quiz answers are never serialised before reveal.
- [ ] HTML in chat, names and room titles is escaped; no `dangerouslySetInnerHTML`
      in the arcade.
- [ ] Rate limits per player and per room; tickets are single-room, short-lived.
- [ ] Every manager write lands in `audit` with the real actor and
      `source="web"`.
- [ ] Voice-note uploads: 15 s, 256 KB cap, MIME sniffed server-side, served
      with `Content-Type` fixed and `X-Content-Type-Options: nosniff`.

---

## 5. Capacity and cost

| Thing | Design point | Consequence |
| --- | --- | --- |
| SSE connection | ~1 per connected player | ~50 comfortable on free Render; Starter beyond |
| Writes per move | 2 (`game_rooms` + `game_events`) | A 200-move game is 400 documents |
| Reads per move | 1 SSE push, 0 polls | Vercel sees only ticket calls |
| Chat retention | 7 days, TTL index | Monitored against the 512 MB free Mongo |
| Quiz pack | ~120 questions bundled in the repo | No external API, no per-question cost |
| Voice notes (tier B) | 15 s, 60 KB, 24 h | ~3 MB per room per day worst case |
| Admin cache sweep | 20 groups/minute | Full fleet every ~2 h at 240 groups |

---

## 6. Delivery order

Each phase ends with something usable, and none of them breaks the current
owner flow.

| Phase | Work | Estimate | Gate |
| --- | --- | --- | --- |
| **P0** | Identity helper, `/api/session`, `players`, `chat_admins`, admin sweep, **read-only** Your Groups + group card | 3–4 days | A non-owner admin signs in and sees only their groups; a test proves a forged token and a demoted admin are refused |
| **P1** | Manager writes with scopes + audit + history + "fix the bot" | 4–5 days | An admin cannot reach `backup_import`, `recording`, or another group; every write is attributed to them |
| **P2** | Arcade core: rooms, Connect Four, Reversi, chat, SSE + polling fallback, turn messages, report/mute | 7–9 days | Two browsers play a full game; a dropped connection resumes on the same board; a replayed move is refused |
| **P3** | Quiz Rush, leaderboards, Elo, rematch, public lobby, spectators | 5–7 days | Answers are absent from every pre-reveal payload; ratings only move in rated rooms |
| **P4** | Voice tier A (group binding + join link + announcements), then tier B (voice notes) | 4–6 days | A group room's Join voice opens the live chat; a note records, uploads, plays for the other player |
| **P5** | *Spike, go/no-go:* WebRTC mesh + TURN, 2–4 players | 5 days | Works on Android, iOS Telegram, and desktop Chrome with TURN; if not, stop |

The order is deliberate: P0+P1 is "a group manager for admins" and lands in
about a week with almost no new runtime. P2 is the first game.

---

## 7. Test plan

- `tests/test_arcade_rules.py` *(new)* — exhaustive win detection, gravity,
  illegal-column refusal; 5,000 seeded random playouts per game asserting
  invariants (piece count, no overwritten cells, every finished game has a
  winner or a full board).
- `tests/test_arcade_rooms.py` *(new)* — CAS conflicts, double timeout
  settlement, join/leave/forfeit, abandonment, reconnect returning the same
  board, chat limits, TTL fields.
- `tests/test_arcade_quiz.py` *(new)* — answer index absent from every
  non-reveal view, scoring, late answers ignored.
- `tests/test_manager_access.py` *(new)* — admin of A refused on B; demoted
  admin refused on next write; owner routes unaffected; scope allowlist;
  audit actor is the admin, not the owner.
- `tests/test_identity.py` *(new)* — valid/expired/forged initData and widget
  payloads; player token cannot satisfy `validOwnerCookie`.
- Panel: `webapp/tests/arcade-room.test.ts` (state reducer, 409 recovery),
  `webapp/tests/manager-screens.test.ts` (admin vs owner rendering), and one
  browser smoke for a full two-seat game with a mocked backend.

Nothing here needs a live Telegram: `_bot_api` is already patchable, and
`mongomock` is the established pattern in `tests/test_schedule_timezones.py`.

---

## 8. File map

**Backend (new unless noted)**

```
videl/utils/telegram_auth.py      verification extracted from _internal_auth
videl/utils/players.py            player upsert, stats, Elo, leaderboards
videl/utils/chat_admins.py        cache + sweep
videl/utils/manager.py            scope allowlist, actor plumbing, focused describe
videl/games/registry.py           Game base class, validation, view projection
videl/games/connect4.py
videl/games/reversi.py
videl/games/tictactoe.py
videl/games/ludo.py               2–4 seats, ring, bases, home columns
videl/games/store.py              Mongo CAS, codes, TTL, events, chat, sweep
videl/games/routes.py             /internal/arcade/*  (polling; SSE stays future)
videl/api/actor.py                signed actor assertion
videl/api/manager_routes.py       /internal/manager/*
videl/__main__.py                 /internal/identity + route registration
videl/__main__.py                 (edit) register blueprints, sweep in watchdog
videl/core/watcher.py             (edit) _sync_admins tick
videl/utils/group_view.py         (edit) actor + scope — §3.4
```

**Panel**

```
webapp/src/app/api/session/route.ts               sign in / who am I
webapp/src/app/api/manager/…                      player-scoped proxy
webapp/src/app/api/arcade/…                       lobby, create, join, room
webapp/src/lib/player-auth.ts                     player cookie + actor assertion
webapp/src/lib/player.ts                          session client, retry, sign-out
webapp/src/lib/arcade.ts                          typed room API + Ludo geometry
webapp/src/lib/game-api.ts                        backend answer passthrough (409 kept)
webapp/src/components/studio/screens/Arcade.tsx   lobby + room host
webapp/src/components/studio/RoomView.tsx         board, chat, presence
webapp/src/lib/access.ts                          "arcade" is public
webapp/src/app/page.tsx                           register the screen
```

---

## 9. Non-goals (stated now so they are not discovered later)

- No native app, no standalone accounts, no email or password.
- No browser-side authority: the client never sends a board, only a move.
- No in-panel music or video streaming; voice is Telegram's, or short notes.
- No coins, purchases or paid entry. Stars spending stays off, as the README
  already promises.
- No chat mirrored into groups by default.
- No "the bot talks in the voice chat". Only the assistant can, and only plays
  audio.
- No global matchmaking queue in v1. Rooms are shared by code or host invite;
  matchmaking is a later, separate problem (ratings need a population first).

---

## 10. Three decisions before P0 starts

1. **Games scope:** the three above, or should the first release be one game
   done exceptionally well?
2. **Public rooms:** open lobby visible to every signed-in user (with reports
   and blocks), or invite-only links until moderation proves itself?
3. **Voice:** confirm tier A as the definition of "live voice" for v1, with
   tier B in v1.1 and tier C gated by the P5 spike.
