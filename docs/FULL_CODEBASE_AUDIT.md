# Full codebase audit — Videl0

**Audit date:** 2026-11-01 (Asia/Kolkata)  
**Branch:** `arena/042d6599-videl0`  
**Scope:** evidence-first source, test, and deployment-configuration audit for the requested player, streaming surfaces, operations/Render monitoring, and connected webapp/backend security and UX paths. This is not a live-service, visual-device, or production security certification.

## Executive summary

The repository already contains a real **personal browser audio player**: the owner-gated Next.js API proxies a validated track ID to the Flask backend, which prepares audio, serves it inline, and supports HTTP range requests. This is not the Telegram group voice-chat engine. Telegram playback remains driven through bot commands such as `/play` and the bot's PyTgCalls/queue lifecycle. Do not claim that the Music page controls Telegram playback or that local browser audio proves group playback.

The internal music routes have meaningful auth, validation, bounded status metadata, safe errors, and range-response tests. The most evident player defect in the inspected UI is a stale asynchronous playback failure (and stale search response) being allowed to overwrite newer state after a rapid track/search change. No root cause for a blanket failure to play was reproduced; browser autoplay, production proxying, provider availability, and Telegram voice playback still need their own tests.

Owner operations currently reports app/backend measurements and bounded sanitized events. It does **not** read Render deployment state, build/runtime logs, or Render service metrics. No Render API token or Render control-plane integration was found in source or `render.yaml`. Any such integration must be a new, server-side, owner-authorized feature with genuine data and explicit unavailable states.

## Audit method and limits

Reviewed the music/voice UI and API path, owner-session and internal-secret boundaries, queue/voice/download status and logs, Render deployment configuration, navigation/mount behavior, and existing focused tests. Also cross-checked existing repository audit artifacts: command inventory and Stage C ledgers, Stage B authorization/API inventory, operations resilience (#245/#248) notes, and the test/backlog notes in `todo.md`.

The repository already has a broad route inventory (49 Next API `route.ts` files at audit time), a generated 209-live-command inventory, and many focused regression tests. Those artifacts are useful but do not mean every command, component, route, dependency, callback, or runtime path has been re-audited line-by-line in this pass. Stage C music-command review is still marked In Progress in `todo.md`. No code was changed as part of this audit phase. No live Telegram, Render, Vercel, MongoDB, media-provider, staging, mobile WebView, or browser end-to-end verification was performed.

## Architecture and trust boundaries

- **Telegram bot and group playback:** `videl/` contains the bot, command/module registration, Telegram API handlers, the shared queue (`videl/core/queue.py`), and voice-call playback. `/play` and related bot commands use Telegram/PyTgCalls flows; their state is distinct from the browser player.
- **Backend service:** `videl/__main__.py` and `videl/api/` host Flask endpoints in the bot/backend process. Internal endpoints use `X-Videl-Internal` compared against `WEBAPP_SECRET` with constant-time comparison. Music internal routes live in `videl/api/eldian_routes.py`.
- **Webapp:** `webapp/src/` is the Next.js/React Studio. Browser requests use same-origin `/api/...` routes; server routes apply owner or Telegram auth, then call the backend with server-side configuration through `webapp/src/lib/backend.ts` or a route-specific proxy.
- **Deployment:** `render.yaml` describes the Render-hosted backend. The repo does not contain a Render control-plane API client or `RENDER_*` credential/configuration. Vercel deployment settings/secrets and the actual deployed plan were not available for inspection.
- **Sensitive data:** current music BFF routes do not accept an arbitrary upstream URL and do not expose the internal secret to browser code. The track route forwards only the caller's `Range`/`If-Range`, and forwards a small allowlist of media headers.

## Streaming-related surfaces

### A. Videl Music Studio page — browser playback

`webapp/src/components/studio/screens/Music.tsx` renders a single `<audio>` element. The page labels playback as browser playback and says Telegram voice-chat streaming remains available via `/play`. Track lookup, play/pause, seek, queue, favorites, history, mini-player, and theatre controls are implemented as browser-local UI/state; favorites/history are localStorage-backed, while the current queue/player state is React state. This is a personal browser session, not a shared group queue or a Telegram playback control panel.

The mini-player is portalled to `document.body`; the shared audio element is rendered independently of the selected Studio tab. `StudioProvider.tsx` retains visited screens mounted but hidden. Therefore playback should survive tab navigation in the same mounted app session; refresh, auth/session remount, browser suspension, and cross-device persistence are not established by that design or by tests.

### B. Browser-to-backend stream path

1. `Music.tsx` calls `/api/music/search`, `/api/music/status`, and `/api/music/track/<videoId>`.
2. Next routes under `webapp/src/app/api/music/` apply `ownerRequired`; the search/status/track routes proxy server-side to the backend using internal configuration.
3. `videl/api/eldian_routes.py` checks the internal secret, bounds search query/result count, validates 11-character video IDs and task IDs, and calls the existing `download_song` implementation.
4. Prepared files are size-checked, served inline with `send_file(..., conditional=True)`, marked `private, no-store`, and retain conditional/range support. Status records have TTL/bounded process storage and are persisted to MongoDB where available. Persistence failure is represented as process-only durability, not falsely as durable job execution.
5. `webapp/src/app/api/music/track/[videoId]/route.ts` forwards range headers, uses a long upstream timeout, returns a streaming response body, and does not forward arbitrary backend HTML/errors.

The backend suite `tests/test_music_webapp_api.py` covers internal auth, input validation, status bounds/persistence/failure, inline audio, and range handling. `webapp/tests/music-center.test.ts` covers owner authorization and malformed status IDs. These tests establish route behavior under their test setup; they do not prove browser decoding/autoplay, Next-to-Render streaming in production, provider reliability, or Telegram playback.

### C. Telegram/group playback and adjacent surfaces

- Group music and voice playback run through bot commands, `videl/core/queue.py`, and the Telegram voice-call lifecycle, not the Studio `<audio>` element. The command-level audit and existing lifecycle/queue tests are tracked in `docs/STAGE_C_BATCH_2_AUDIT.md`, `tests/test_music_lifecycle.py`, `tests/test_queue*.py`, and `todo.md`; that command review remains incomplete.
- `webapp/src/components/studio/boards/VoiceDock.tsx` and `webapp/src/lib/voice.ts` implement room voice through browser WebRTC. This is a separate peer voice feature, not Telegram group music playback.
- `VoiceNote.tsx`, `InboxComposer.tsx`, and media previews in `GroupViewer.tsx` record/play message attachments or browser previews. They are not the Telegram group playback engine.
- `EventRooms.tsx` has an optional music-request field; that is not itself evidence of an active stream or synchronized bot queue.
- No second Music page or duplicate browser music engine was found in the inspected navigation/component path. `/play` in Telegram remains the distinct bot-side entry point.

## Findings

### F-01 — Product boundary: browser player is not Telegram group playback (confirmed; product-scope gap)

**Evidence:** `webapp/src/components/studio/screens/Music.tsx` (audio element, local React queue and playback handlers; explicit browser-playback label and `/play` notice); backend `/internal/music/*` in `videl/api/eldian_routes.py`; group queue and voice lifecycle in `videl/core/queue.py` and bot modules. Owner operations music aggregate (`videl/__main__.py` `/internal/ops/music`, `webapp/src/app/api/ops/music/route.ts`) returns counts/status, not the current group track or browser-player synchronization.

**Root cause / impact:** these are separate architectures and state stores. The browser player prepares a downloadable audio file for the owner; it does not invoke a Telegram voice-call transport or mutate the Telegram queue. Treating its play/queue controls or the aggregate ops metrics as Telegram playback controls would misrepresent functionality.

**Reproduction:** open Studio Music, start a result, and observe playback in the browser `<audio>` element. Separately use `/play` in a Telegram group. The inspected page has no authenticated group selector/control call that binds those actions to the Telegram queue.

**Disposition:** do not silently replace the page with a fake local representation of voice playback. Keep browser preview explicitly labeled, or design a separate real Telegram control surface backed by authenticated group/queue operations and current server state. Test with mocks first; any live claim requires a real Telegram group/voice-call check.

### F-02 — Stale play promises can overwrite a newer track's state (confirmed UI race; untested in browser)

**Evidence:** `Music.tsx:211-238` immediately switches `current`, task ID, source, and audio element; the promise from `player.play()` unconditionally sets `playing`, `loading`, and `error` in both continuations. There is no generation/current-track check before those asynchronous state writes.

**Root cause / impact:** when a user rapidly selects A then B, the source replacement can reject A's pending `play()` promise after B has begun loading/playing. The old catch then marks the newer player paused/not-loading and displays an error. This is a code-evident race, but its user-visible timing has not yet been reproduced in a browser.

**Reproduction to add:** delay/reject the first `play()` promise, select a second track, resolve the second promise, then reject the first; assert B remains current/playing and no stale error is displayed. Also exercise a rapid seek/source reset and unmount.

**Recommended fix:** use a monotonically increasing playback generation or track/task token in every `play()` resolution/rejection and relevant media event. Ignore stale callbacks; pause/reset and clear source/error state deliberately on track changes. Add a focused failing test before modifying implementation.

### F-03 — Search results and busy/error state can be stale after overlapping searches (confirmed UI race; untested)

**Evidence:** `Music.tsx:190-209` starts a fetch for every search, then each completion writes `results`, `error`, and `searching`; there is no abort controller/request sequence guard.

**Root cause / impact:** if a slower earlier query resolves after a newer query, its results can replace the newer result set, and the earlier `finally` can clear the busy indicator while the later request is still pending.

**Reproduction to add:** issue two searches with controlled deferred responses and resolve them out of order; assert only the latest request updates results, errors, and busy state.

**Recommended fix:** cancel the previous request or apply a request-generation guard, including cleanup on unmount. Add deterministic component/helper tests.

### F-04 — Internal track preparation has no visible admission/concurrency bound (confirmed by route comparison; operational risk)

**Evidence:** `videl/api/eldian_routes.py:255-289` validates the owner-proxied route and bounds each download to 300 seconds and `MAX_BYTES`, but directly starts `download_song` for every request. `_MUSIC_TASKS` bounds status metadata; it does not bound active workers. The user-facing Next route is owner-only (`webapp/src/app/api/music/track/[videoId]/route.ts`). The separate existing media-serving path's semaphore was not shown applied to this internal preparation route.

**Root cause / impact:** rapid/repeated requests can create overlapping provider/download work and consume backend CPU, memory, file descriptors, network, and disk. The owner-only gate limits who can initiate requests, but is not an admission-control policy. This has not been load-tested and is not evidence that production is currently overloaded.

**Recommended fix:** inspect downloader caching/locking first, then add a shared bounded semaphore/queue, same-track deduplication where safe, and an explicit busy response/status; consider cancellation/cleanup without breaking range seeks. Test maximum concurrent downloader calls, duplicate track requests, timeout/error cleanup, and process restart. Avoid arbitrary rate limits until observed behavior and intended owner usage are understood.

### F-05 — Existing Control Room is app telemetry, not Render monitoring (confirmed capability gap)

**Evidence:** `OwnerHome.tsx` consumes `/api/ops/metrics`, `/api/ops/events`, `/api/ops/logs`, `/api/ops/music`, and `/api/version`. Backend endpoints in `videl/__main__.py` measure this process, return bounded command/error categories from app/Mongo data, and aggregate music/voice/download state. `render.yaml` and source search expose no Render API credential/client or deployment/log endpoint.

**Root cause / impact:** the current dashboard cannot report Render deployment history, build logs, service-level events, or Render control-plane metrics. An app process being healthy does not establish a successful Render deploy; app-local error categories are not the same as platform logs. Calling current app data "Render monitoring" would be inaccurate.

**Recommended implementation if requested:** a new server-only Render adapter with a secret credential (never `NEXT_PUBLIC_*` or browser payload), fixed/allowlisted service identifiers, owner authorization, strict schemas, bounded pagination, timeout, cache/rate controls, secret/identifier redaction, and distinct configured/unavailable/error/stale states. Preserve current app-level telemetry under its accurate name. Add mocked contract/security tests, then validate against Render only when credentials and a real service are configured. No Render credential was available or sought in this audit.

### F-06 — Current tests do not cover the browser streaming experience end-to-end (confirmed coverage gap)

**Evidence:** backend route tests cover internal auth, validation, and range responses; `music-center.test.ts` is narrow owner/status coverage. No inspected test drives the player through overlapping track/search requests, media events, browser range proxying, refresh/remount, or the Telegram-vs-browser boundary.

**Impact:** a green backend route suite cannot clear the UI races in F-02/F-03 or certify proxy behavior in a deployed browser. Existing tests are useful and should be retained; no current playback root cause should be inferred from them.

**Recommended verification:** add the deterministic UI race tests first; then test browser media event/state behavior and the Next BFF range headers/body using mocks. Run existing focused Python/web tests and typecheck/build. Keep production/Vercel, provider, Telegram, and device results separately labeled as not run unless actually run.

## Security, reliability, and UX observations

- **Auth boundary:** browser-facing music routes use owner authorization; internal backend routes require a constant-time comparison against `WEBAPP_SECRET`. IDs and status task IDs are validated; error responses avoid exposing backend HTML/diagnostics; audio responses are private/no-store. Keep tests for missing/wrong secrets and owner rejection.
- **Range and seeking:** both backend `send_file(..., conditional=True)` and the Next proxy preserve range-related headers/status behavior. Existing backend tests cover ranges; add proxy-level tests before changing response streaming.
- **Status semantics:** download preparation status is not playback status, and an audio file's `ready` state is not a Telegram voice call. Persistence is MongoDB-backed when possible; process-only/unavailable durability is explicitly represented.
- **Navigation lifetime:** visited Studio screens remain mounted and hidden, which supports same-session browser playback persistence. Refresh, remount, session expiry, and media suspension remain unverified. Do not store credentials or assume cross-device playback state in localStorage.
- **Owner metrics freshness:** operations data is bounded and polls periodically. Data sources differ (process snapshot, Mongo records, queue/voice aggregate, sanitized events); label each source and its timestamp/state rather than combining into a fictional platform health score.
- **No speculative redesign:** no evidence in this audit supports introducing another Music page, replacing the current player with a fake Telegram player, changing downloader/provider policy, or adding a Render token without configuration and tests.

## Test and verification inventory relevant to this work

- `tests/test_music_webapp_api.py` — internal music route auth/input/status/audio/range behavior (offline tests; inspect its current result before changes).
- `webapp/tests/music-center.test.ts` — owner auth and malformed status ID.
- `tests/test_music_lifecycle.py`, `tests/test_queue*.py`, and `docs/STAGE_C_BATCH_2_AUDIT.md` — Telegram playback/queue related source/test coverage; Stage C Batch 2 remains incomplete.
- `webapp/tests/*` — broader route, auth, owner operations, and Studio tests. Existing `todo.md` records a previously successful web typecheck/test run; rerun relevant checks against the actual worktree before relying on it.
- `render.yaml` — Render service definition, not proof of current production deployment state or Vercel configuration.

No test command was run for this document-only audit. No live-service result is claimed.

## Ordered next steps

1. Keep this audit as the evidence baseline and update `todo.md` without disturbing its historical backlog.
2. Add TDD coverage for F-02 and F-03 and fix only the demonstrated stale-state races; re-test audio range proxy behavior and component lifetime.
3. Finish the Stage C Batch 2 review of all 45 music/playback/queue/playlist commands, including permission/callback and queue-boundary review; document any verified issues before changing them.
4. Audit all streaming-adjacent components and API routes from the surface list above, and keep browser voice, Telegram voice, media preview, and request-only UI clearly distinguished.
5. Decide whether Render control-plane monitoring is in scope and whether a server-side credential/service ID can be provisioned. Until then, retain honest unavailable/configuration states and do not call app telemetry Render data.
6. Continue webapp UX/security/performance work only for verified gaps; run focused and broader feasible offline tests. Record browser, production, Telegram, Render, and device checks separately.
7. Commit changes in reviewable logical batches to `arena/042d6599-videl0`; do not merge/close PR #5. Preserve unrelated worktree changes.

## Audit status

The audit establishes the current architecture and the findings above, but it is not the final completion report for the requested overhaul. Root causes F-02/F-03 have not been browser-reproduced; no implementation fixes are included in this audit. F-04 is a source-evident resource-control gap requiring downloader-cache inspection and a test before implementation. Render control-plane monitoring is absent and cannot be truthfully tested without server-side configuration. The overall task remains in progress.
