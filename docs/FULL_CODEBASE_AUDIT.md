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

### F-02 — Stale play promises could overwrite a newer track's state (source-confirmed; guarded; browser unverified)

**Evidence/root cause:** before the Stage D change, `Music.tsx` called `player.play().then(...).catch(...)` without associating either completion with the selected track. Replacing Track A's source with B can reject A's still-pending play promise after B starts; that stale catch could then change `playing`, `loading`, and `error`. The state writes were not generation-checked.

**Deterministic reproduction:** `webapp/tests/latest-request.test.ts` uses deferred promises: start A, start B, resolve B, then reject A. Assertions require B to remain current/playing with no stale error and loading false. This uses no timing sleeps. It exercises the shared gate used by the component; an actual browser/media timing reproduction is still outstanding.

**Fix:** `Music.tsx:252-306` now routes play results through `LatestRequestGate`/`settleLatest`; explicit pause invalidates pending play completions. Media event state writes check the active `currentSrc` against the currently selected stream URL, and task status responses are scoped to the active task ID.

### F-03 — Overlapping searches could commit stale result and status state (source-confirmed; fixed; browser unverified)

**Evidence/root cause:** the original `searchTracks` allowed every fetch completion/finally block to update results, error, and searching state. An earlier slow search could replace newer results or clear its busy state early.

**Deterministic reproduction:** controlled deferred A/B successes resolve B first and A last; tests assert B results remain. Another test resolves stale A while latest B is pending, then rejects B and asserts only B's error/completion is committed.

**Fix:** `Music.tsx:208-250` now assigns request generations, aborts a prior request when a new/invalid search starts, guards success/error/finally commits, and cancels active search on unmount. Actual browser fetch/console behavior remains unverified.

### F-04 — Internal track preparation previously bypassed existing admission control (mitigated; residual risks documented)

**Evidence/root cause:** before Stage D, `/internal/music/track/<video_id>` started `download_song` without acquiring the existing two-slot `_SLOTS` budget used by the public media-serving route. The internal route and the public route share the same process and download directory.

**Fix/test:** `videl/api/eldian_routes.py:256-300` now nonblockingly acquires `_SLOTS` before task preparation and releases it in `finally`. When both slots are occupied it returns 503 with `Retry-After: 5` and does not invoke the downloader. `tests/test_music_webapp_api.py::test_internal_track_preparation_rejects_when_shared_media_slots_are_full` covers this path.

**Residual risk:** this is not a global cap for bot code calling `download_song` directly or across multiple backend processes. There is still no same-video single-flight lock, and using a shared slot budget can transiently reject an owner request. See the explicit cache/concurrency review below; no broader worker redesign was made.

### F-05 — Existing Control Room is app telemetry, not Render monitoring (confirmed capability gap)

**Evidence:** `OwnerHome.tsx` consumes `/api/ops/metrics`, `/api/ops/events`, `/api/ops/logs`, `/api/ops/music`, and `/api/version`. Backend endpoints in `videl/__main__.py` measure this process, return bounded command/error categories from app/Mongo data, and aggregate music/voice/download state. `render.yaml` and source search expose no Render API credential/client or deployment/log endpoint.

**Root cause / impact:** the current dashboard cannot report Render deployment history, build logs, service-level events, or Render control-plane metrics. An app process being healthy does not establish a successful Render deploy; app-local error categories are not the same as platform logs. Calling current app data "Render monitoring" would be inaccurate.

**Recommended implementation if requested:** a new server-only Render adapter with a secret credential (never `NEXT_PUBLIC_*` or browser payload), fixed/allowlisted service identifiers, owner authorization, strict schemas, bounded pagination, timeout, cache/rate controls, secret/identifier redaction, and distinct configured/unavailable/error/stale states. Preserve current app-level telemetry under its accurate name. Add mocked contract/security tests, then validate against Render only when credentials and a real service are configured. No Render credential was available or sought in this audit.

### F-06 — Browser E2E coverage remains unavailable (partial mocked coverage added)

**Evidence:** `webapp/tests/latest-request.test.ts` now covers controlled stale/current playback and search completions plus media-source matching. `webapp/tests/music-center.test.ts` covers expired owner auth and mocked BFF 206/range pass-through. `tests/test_music_webapp_api.py` covers backend auth, validation, status, audio, ranges, and busy admission.

**Remaining limitation:** these tests do not instantiate the Music React component or a real browser decoder/network stack, and do not establish autoplay, refresh/remount behavior, or deployed proxy streaming. `npm run test:browser` cannot launch because the Playwright Chromium executable is absent. No browser console/network issue was observed because the browser test could not run; no actual playback failure root cause is claimed.

## Security, reliability, and UX observations

- **Auth boundary:** browser-facing music routes use owner authorization; internal backend routes require a constant-time comparison against `WEBAPP_SECRET`. IDs and status task IDs are validated; error responses avoid exposing backend HTML/diagnostics; audio responses are private/no-store. Keep tests for missing/wrong secrets and owner rejection.
- **Range and seeking:** both backend `send_file(..., conditional=True)` and the Next proxy preserve range-related headers/status behavior. Backend tests cover ranges; the Stage D proxy test now verifies a mocked 206 response, `Content-Type`, `Content-Range`, `Accept-Ranges`, body bytes, and forwarding of `Range`/`If-Range` without exposing the internal secret.
- **Status semantics:** download preparation status is not playback status, and an audio file's `ready` state is not a Telegram voice call. Persistence is MongoDB-backed when possible; process-only/unavailable durability is explicitly represented.
- **Downloader cache/concurrency review (Stage D):** `download_song` calls `_find_file` before trying providers; external/Eldian provider transfers use `.part` files and `os.replace`, and yt-dlp uses a shared per-video output template. There is no per-video single-flight lock, so simultaneous same-track requests can duplicate upstream work and contend on shared temp/output paths. `_file_cache` is used by `resolve_stream`, not directly by `download_song`; `download_song` instead scans supported files in the top-level `DOWNLOAD_DIR` (the local fallback's `downloads/eldian` subdirectory is not included in that scan). The internal browser-track route now shares the existing two-slot `_SLOTS` semaphore with the public media API and returns 503/`Retry-After: 5` before starting a third preparation. **Trade-off:** this reuses the repository's existing two-worker ceiling and avoids unbounded internal-route preparation, but can reject a legitimate owner request while both slots are occupied. It does not globally cap bot callers that invoke `download_song` outside those routes, does not deduplicate identical video IDs, and is not a distributed limit across multiple backend processes. Do not claim it solves all downloader concurrency.
- **Navigation lifetime:** visited Studio screens remain mounted and hidden, which supports same-session browser playback persistence. Refresh, remount, session expiry, and media suspension remain unverified. Do not store credentials or assume cross-device playback state in localStorage.
- **Owner metrics freshness:** operations data is bounded and polls periodically. Data sources differ (process snapshot, Mongo records, queue/voice aggregate, sanitized events); label each source and its timestamp/state rather than combining into a fictional platform health score.
- **No speculative redesign:** no evidence in this audit supports introducing another Music page, replacing the current player with a fake Telegram player, changing downloader/provider policy, or adding a Render token without configuration and tests.

## Test and verification inventory relevant to this work

- `tests/test_music_webapp_api.py` — internal music route auth/input/status/audio/range behavior (offline tests; inspect its current result before changes).
- `webapp/tests/music-center.test.ts` — owner auth/malformed status, expired stream-session rejection, and mocked range-proxy response.
- `tests/test_music_lifecycle.py`, `tests/test_queue*.py`, and `docs/STAGE_C_BATCH_2_AUDIT.md` — Telegram playback/queue related source/test coverage; Stage C Batch 2 remains incomplete.
- `webapp/tests/*` — broader route, auth, owner operations, and Studio tests. Existing `todo.md` records a previously successful web typecheck/test run; rerun relevant checks against the actual worktree before relying on it.
- `render.yaml` — Render service definition, not proof of current production deployment state or Vercel configuration.

No test command was run for this document-only audit. No live-service result is claimed.

## Stage D implementation and verification update (2026-11-01)

- **Playback race (F-02):** added a request-generation gate around every `play()` promise result and rejection. Media events now apply only when `currentSrc` matches the active stream URL. Explicit pause invalidates pending play completions. Changing tracks replaces/reloads the single audio source; unmount invalidates playback work, pauses audio, clears `src`, and reloads the element. Download-status polling also checks the current task ID so a late old task cannot change current status/error state.
- **Search race (F-03):** added request-generation guarded result/error/loading commits and aborts the prior fetch on a new or invalid search. The request is aborted on unmount; a 28-second timeout remains. Old completions cannot clear the latest search's loading state or replace its results.
- **Deterministic async/source tests:** `webapp/tests/latest-request.test.ts` controls deferred completions/rejections (no timer assumptions) for late Track A rejection after Track B, out-of-order A/B search success, latest-search error/loading ownership, and current-vs-stale media source matching. These exercise the same gate/source-matching helpers used by the component. The initial red run could not resolve the not-yet-implemented helper module; after implementation the controlled-async tests passed, and the final complete web suite passed.
- **Pipeline regression coverage:** `webapp/tests/music-center.test.ts` now checks that an expired owner session is rejected before any backend request, and checks the owner track BFF's mocked 206 response, MIME/range headers, body, `Range`/`If-Range` forwarding, and absence of secret leakage. Existing Flask range tests still check 206 and exact bytes. The task ID itself is status metadata, not an expiring bearer URL. A subsequent browser media error is surfaced as an in-page playback error. Actual browser console/network testing could not run because the Playwright Chromium executable is absent.
- **Cleanup:** old browser fetches are cancelled on a new search/unmount; old status polls are stopped and task-ID guarded; changing an audio source via `load()` cancels/replaces the browser media request, and component unmount clears the source. Studio tab navigation intentionally keeps the visited Music screen mounted, so it does not stop same-session playback.
- **Downloader capacity decision:** source review found cached-file lookup but no per-video lock/single-flight around `download_song`; shared `.part`/output names permit duplicate concurrent same-track preparation. The internal track route now nonblockingly shares the already-existing two-slot `_SLOTS` limit with the public media API, returns 503 with `Retry-After: 5` when both slots are busy, and releases the slot in `finally`. This is bounded admission for these HTTP surfaces only, not a global cap for bot callers or multi-process deployments; no per-track deduplication or disk-cache eviction was introduced.
- **Offline tests/checks:** `npm test` — 229 passed; `npm run typecheck` — passed; `npm run build` — passed; `.venv/bin/python -m unittest tests.test_music_webapp_api` — 11 passed; `.venv/bin/python -m py_compile videl/api/eldian_routes.py` — passed; `git diff --check` — passed. No lint script is defined in `webapp/package.json`. `npm run test:browser` was attempted but could not launch: Playwright's Chromium executable is not installed. No browser console/network, live provider, Telegram, Render, Vercel, production, or device validation is claimed.

## Remaining work and status

1. Continue the Stage C Batch 2 audit of all 45 Telegram music/playback/queue/playlist commands; it is distinct from this browser-player fix.
2. Consider per-video single-flight and cache cleanup only after separate tests/design for provider atomicity, file lifetime, bot callers, and multi-process behavior. Current admission is intentionally route-local and can return a transient busy response.
3. Browser UI behavior, autoplay, actual provider responses, owner-session expiry during a range seek, and browser console/network errors remain unverified because Chromium is unavailable. Tests use controlled promises and mocked upstream responses.
4. Telegram group playback remains entirely separate and was not changed or live-verified. Render control-plane integration remains absent; no Render token or live Render data was used.
5. Keep PR #5 open/unmerged and preserve unrelated edits in `tests/test_command_ui.py` and `tests/test_replacement_domains.py`.

F-02/F-03 now have deterministic controlled-async regression coverage and request-generation guards; this does not substitute for browser reproduction. F-04's HTTP route admission risk is mitigated using the established two-slot policy, with limitations above. Overall Stage D remains in progress until browser and remaining downloader/cross-command validation become feasible.
