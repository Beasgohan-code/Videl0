# Videl shared-listening rooms: design proposal

**Status:** design, pure policy helpers, Mongo store, internal backend routes, and player-authenticated web proxy routes are implemented. Music Studio controls, multi-client polling/playback, and live database/browser verification are not yet implemented.
**Boundary:** this is a browser music feature. It does not control or join Telegram voice chats, change bot queues, or expose owner-only Music Studio APIs to player sessions.

## Repository evidence

- The browser can authenticate a public player through Telegram Mini App launch data. `webapp/src/lib/player-auth.ts` verifies a separate `videl_player` cookie and signs short-lived `X-Videl-Actor` assertions for the backend. This identity is deliberately distinct from the owner cookie.
- `webapp/src/app/api/arcade/*` is the existing same-origin authenticated proxy pattern. `videl/games/routes.py` verifies the internal secret and actor assertion, and `videl/games/store.py` uses Mongo-backed state and compare-and-set versions for concurrent game actions.
- The Arcade is an existing multiplayer game feature. Shared listening should not add listening-specific behavior to its room store or conflate game rooms with music rooms.
- `/api/music/*` includes owner-only browser-player/provider routes. A new room API must use the public player identity boundary, not forward an owner session or weaken those existing routes.

## MVP boundary

A signed-in Telegram player can create a private, short-lived listening room, share its invite code/link, and let other signed-in players join. Members see a server-authoritative queue and playback intent. The host can enqueue or remove tracks, select the current track, and publish play/pause/seek intent. Clients reconcile against a versioned server snapshot and their local playback clock.

MVP deliberately excludes: public room discovery, anonymous/guest membership, direct messages, voice/video, 3D, event integration, moderation beyond host removal/room closure, importing Telegram queues, and any claim that different providers/devices will produce sample-accurate synchronized audio. Each member's browser resolves and plays tracks independently; provider and browser restrictions can result in a member being unable to play a track.

## Identity and authorization

- Every create/join/read/mutate request requires `playerRequired` plus a signed backend actor assertion. The actor is taken from the verified cookie, never from a body or query parameter.
- Room codes are unguessable, short-lived capabilities but are not sufficient alone: joining also requires a valid player session. Do not expose room contents in unauthenticated metadata or logs.
- A member may read room state and leave. Only the host may mutate queue/order/current item, playback intent, invite rotation, or close the room. The host may remove a member; an ordinary member cannot remove another member.
- Host transfer is out of MVP. If the host leaves, close the room rather than silently transferring control.
- Endpoints require same-origin state-changing requests, bounded JSON, rate limits, and no-store responses. Do not return private Telegram profile data; use only the minimal display name and opaque room-local member identity needed by the UI.

## Persistence and consistency

Proposed separate Mongo collections: `listening_rooms` and `listening_room_events` (names subject to repository naming review). Room document fields:

- random code/id, host player id, member player ids with bounded display names and join timestamps;
- status (`open`/`closed`), created/updated/expiry timestamps, version and monotonically increasing event sequence;
- bounded queue of normalized public track metadata (`video_id`, title, channel, duration, thumbnail/provider key); never store resolved stream URLs, cookies, or access tokens;
- playback intent (`track_id`, `playing`, position, server anchor timestamp, version). The server stores intent, not audio bytes.

Each mutation must be an atomic compare-and-set against the observed room version (and sequence where appropriate). Reject stale host actions with a conflict and return a fresh snapshot; never merge concurrent queue changes silently. Validate every normalized track server-side and cap queue size at 100. Keep event payloads minimal and expire them on a TTL. Room TTL must be enforced on reads and writes even if Mongo TTL cleanup is delayed. Add indexes in the normal idempotent index setup; do not create indexes or mutate production data as part of an unapproved deployment.

## Playback protocol

- Host play/pause/seek/track-change writes an intent containing an incremented version and server timestamp. Clients poll bounded updates (initially reuse Videl's existing authenticated HTTP proxy; no new websocket/relay in MVP).
- For an active track, clients estimate position from the server anchor and elapsed time, clamped to known duration. On receipt of a newer intent they seek only when drift exceeds a conservative threshold and the media element supports seeking.
- Track preparation and autoplay are local. A blocked autoplay, unavailable track, or provider failure is reported locally and does not rewrite the room's shared state. The host remains the sole authority for choosing a different item.
- Polling is rate-bounded; use `after` sequence cursors, cap returned event count/bytes, and return a full snapshot if a cursor is too old. Avoid per-poll writes for presence; if presence is added later, throttle heartbeats and expire them lazily.

## Abuse and privacy controls

- Private invites only; high-entropy code, normalized input, and constant-shape not-found responses to avoid room enumeration.
- Caps: initially 8 members, 100 queue entries, 100 active rooms per actor (subject to product decision), room lifetime at most 12 hours, and bounded track/text fields. Enforce limits atomically where concurrent creates/joins could exceed them.
- Backend proxy routes currently apply bounded process-local sliding-window limits to create, join, read and mutation operations, failing closed when limiter capacity is exhausted. This is defense in depth, not a fleet-wide quota: before multi-worker/high-volume production, move limits to a shared atomic store. Active-room-per-actor quotas and per-room-specific poll limits remain follow-up work.
- Room close, host removal, member leave, expiry, and failed writes must be explicit state transitions. Never log invite codes, actor identifiers, full request bodies, or provider URLs.
- Retain only room events needed for short polling/debugging and expire them. Keep an operational audit free of private player identifiers.

## Proposed implementation sequence

1. **Pure policy foundation added:** `videl/web_music_rooms.py` and `tests/test_web_music_rooms.py` cover code and track normalization, limits, membership/host policy, playback-anchor calculations and hard expiry. Database state transitions, including stale-version outcomes, remain for the backend phase.
2. **Backend store and routes added:** `videl/listening_room_store.py` and `videl/api/listening_room_routes.py` use the internal secret plus signed player actor, version-checked mutations, hard expiry checks, member/host rules, bounded payloads and room limits. Add deterministic database/route tests for denial-before-DB, spoofing, races, and expiry before release.
3. **Same-origin web proxy routes added:** `/api/music/rooms`, `/join`, and `/[code]` enforce the public player session and cross-site write guard, allowlist payloads, and do not relax owner-only Music endpoints. Add route-specific tests for request forwarding and body edge cases.
4. Add a Videl-native Music Studio room panel and invite/join flow, with accessible states for loading, expiry, playback blocked, unsupported track, conflict, and sign-in. Keep browser playback separate from Telegram voice playback and Arcade routes.
5. Run targeted Python/web tests, typecheck, production build, security/bundle checks, then use a controlled multi-client browser test before claiming synchronization. Provider/live production checks remain separate and require explicit authorization.

## Open questions before coding the room slice

- Is Telegram sign-in an acceptable requirement for everyone joining a room, or is a lower-privilege guest identity required? The secure default is signed-in players only.
- Should room creation be limited to the owner in an initial prototype, or enabled for all signed-in players with the limits above? The product default proposed here is all signed-in players, with server-side quotas.
- Which track source is allowed in a room? The first implementation should reuse only Videl's already-approved browser-source resolver, without copying Playeon provider code or resolving audio URLs in the room service.
