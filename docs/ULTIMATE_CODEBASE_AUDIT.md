# Videl0 — Ultimate Codebase Audit

**Audit date:** 2026-11-01
**Repository / branch:** `Beasgohan-code/Videl0`, `arena/042d6599-videl0`
**PR:** #5 — OPEN, unmerged
**Audit status: PARTIAL — NOT A LINE-BY-LINE CERTIFICATION.** This report records verified findings, fixes made in the current worktree, and the exact coverage limits. The repository inventory is complete at the tracked-file/count level, and all tracked Markdown files were read. Deep tracing covered the highest-risk identity, internal API, music/download, game-store, deployment, and CI paths. The full 333-file Python corpus, every Telegram callback, every React interaction, every Mongo query, and every deployment/live behavior have **not** all been independently reviewed line by line. Do not describe this audit as complete until the remaining work in §18 is done.

## 1. Executive summary

Videl0 is a large split application: a Python Telegram bot and Flask internal API run together on Render; a Next.js/React Studio runs on Vercel; MongoDB stores bot, group, music-preparation, arcade, and analytics data. The webapp also has a separate Telegram-signed public-player identity path. Browser audio is not Telegram group voice playback.

The principal security issue reproduced from source was a **public example-environment fallback for `WEBAPP_SECRET`**. `config.py` loaded `.env.example` after `.env`; if the real secret was absent, the template's long instructional value could become the effective key used by `_internal_authorized()`. The checked-in current worktree now stops loading `.env.example`, leaves the template secret blank, rejects short/placeholder secrets, and has isolated regression tests. This fix is **not committed or deployed**. If any deployed environment copied the example value, rotate `WEBAPP_SECRET` on Render and Vercel.

The current worktree also removes the hardcoded owner account identifier from tracked source/docs/config/tests and client bundles. Owner identity is now read from server runtime configuration; the browser auth response no longer returns Telegram user details. This change requires `OWNER_ID` to be privately configured on **both Render and Vercel**. A scan found no exact former identifier in the current non-generated tree or the built public/server app output. Published Git history was not rewritten; older commits may still contain it.

Other high-value findings verified in source include persistent music downloads without a bounded eviction policy (still open) and same-video concurrent writes to shared filenames (process-local single-flight now implemented; cross-process coordination remains open); arcade room retention is still undefined, while the unbounded in-memory rate-limit maps have since been bounded and covered offline; and the PR's Python contract-test job being cancelled at its 25-minute limit. The malformed-duration search crash, Eldian/shared-secret coupling, and Eldian in-stream byte-cap gap were reproduced/confirmed and fixed in the current worktree with regression tests. The current GitHub PR checks show webapp checks passing, but the backend test job did not finish.

**No Critical-severity exploitable issue was established beyond the High internal-secret fallback described above.** The secret fallback is fixed in the worktree but needs configuration review, deployment, and secret rotation if it was ever used. Other findings are listed with confidence and verification limits below.

## 2. Scope, method, and confidence

- Enumerated **666 Git-tracked files** on the active branch, excluding generated dependency/build trees from the project inventory.
- Read all **25 tracked Markdown files**, including nested project/vendor/test documentation. Scanned local Markdown links: **26 files checked (25 tracked files plus this report), 0 broken relative links**.
- Cross-checked source/config/test/deployment claims in `README.md`, `FEATURES.md`, `todo.md`, `docs/`, Render/Docker/Koyeb config, GitHub workflows, dependency manifests, bot routes, web routes, the music pipeline, and game persistence.
- Audited `gh pr checks 5`; checked exact branch and PR status. No external service credentials were used.
- Ran static scans for owner-identity leakage and build artifacts. Did not print credential values. No current secret values were requested or exposed.
- **Confirmed** means directly observable from code/config or a deterministic test. **Strong evidence** means code strongly implies the risk but production impact or an external condition is unverified. **Needs verification** means a live service/device, deployment config, or dependency-enabled test is required.

## 3. Repository inventory

| Area | Tracked inventory | Main role |
|---|---:|---|
| Whole repository | 666 files | Python bot/API, web panel, tests, docs, deployment, vendored code and assets |
| Python | 333 `.py` files | Bot, web backend, media, utilities, vendor/tests/scripts included |
| Web source | 132 `.ts` + 65 `.tsx` = 197 files | 49 Next API route files plus components, screens, libraries and server proxy/auth code |
| Python tests | 129 files | Bot, permissions, Mongo contracts, callbacks, queues, API and feature tests |
| Web tests | 45 files | Node/TS tests and browser smoke harness |
| Markdown | 25 files | Root overview/backlog, docs, vendor and web test guidance |
| `docs/` | 23 files | Audits, implementation/release records, command inventories and plans |
| `webapp/public/` | 74 tracked assets | Images/artwork and public media |
| `vendor/` | 29 tracked files | Eldian downloader integration and Richgram fork, with associated project/license material |
| `videl/` | 173 tracked files | `api/`, `app/`, `core/`, `games/`, `modules/`, `plugins/`, `utils/` |
| `webapp/src/` | 158 tracked files | Studio screens/components, app routes, auth, player, UI, shared data/state |
| Automation/config | GitHub workflows/scripts, Render/Docker/Koyeb, requirements and npm lock/config | CI, deploy, packaging and reproducibility |

### Major data and execution paths

1. **Telegram commands:** Pyrogram/Kurigram client → legacy module handlers and declarative `videl.app` router/plugin routes → utilities/services → MongoDB and Telegram Bot API.
2. **Owner panel:** browser → same-origin Next route → owner/player cookie and request validation → backend proxy with `X-Videl-Internal` → Flask route → group/music/analytics/store service → MongoDB/Telegram.
3. **Public Arcade:** Telegram signed launch data → player session and actor assertion → Next `/api/arcade/*` proxy → Flask arcade route → `videl/games/store.py` and game rule modules.
4. **Studio Music:** owner browser player/search → Next `/api/music/*` → internal Flask music API → downloader providers and local media files → range-capable response to browser `<audio>`. This path is separate from Telegram voice-chat playback, which uses bot queue/player/PyTgCalls code.
5. **Media API:** authenticated Eldian-compatible Flask route → provider/yt-dlp → per-request output directory, with process-local concurrency/rate accounting.

### Directories and files included in inventory

Root configuration/deployment: `config.py`, `main.py`, `start`, `requirements*.txt`, `.env.example`, `sample.env`, `Dockerfile`, `docker-compose.yml`, `render.yaml`, `koyeb.yaml`, `.dockerignore`, `.gitignore`.
Python: `videl/api/`, `videl/app/`, `videl/core/`, `videl/games/`, `videl/modules/`, `videl/plugins/`, `videl/utils/`.
Webapp: `webapp/src/app/`, `components/`, `lib/`, `webapp/tests/`, `webapp/public/`, `package.json`, `package-lock.json`, Next/TypeScript/PostCSS/Tailwind configuration.
Tests/tools/docs: `tests/`, `scripts/`, `tools/`, `.github/workflows/`, `.github/scripts/`, all 25 tracked Markdown files, CSV command/auth inventories, and both vendor trees.

The counts above include tests and some vendor Python/TypeScript; they are not counts of first-party runtime modules alone.

## 4. Critical and High-priority findings

### SEC-01 — Public example configuration could become the internal API secret

- **Severity:** High (security boundary)
- **Confidence:** Confirmed source defect; live exploitation/configuration **not verified**
- **Status:** Fixed in the current uncommitted worktree; deployment and any required rotation remain pending.
- **Affected:** `config.py` environment loading and `WEBAPP_SECRET`; `.env.example`; `videl/__main__.py::_internal_authorized`; authenticated Flask routes.
- **Evidence:** Before this worktree fix, `config.py` loaded `.env.example` after `.env` using `python-dotenv`'s non-overriding default. Missing environment keys were therefore filled from the example file. The resulting `config.WEBAPP_SECRET` is the value compared by `_internal_authorized()` for the internal API. The example contained a long instructional placeholder, not a valid deployment-generated secret. A caller knowing the repository could supply that placeholder to the internal header if deployment had not injected a real secret.
- **Impact:** The shared header protects internal owner operations and data routes. If the example value was the active key, an unauthenticated external caller could impersonate the webapp backend and invoke internal routes. Actual service exposure and whether Render/Vercel had real values are not known.
- **Reproduction:** In an isolated config directory with no `.env` and no `WEBAPP_SECRET` in the process environment, put a long placeholder in `.env.example` and import the old config: the template value becomes the runtime secret. Send that known value in `X-Videl-Internal` to an internal route; `_internal_authorized()` accepts it.
- **Worktree remediation:** `config.py` now loads only the process environment/private `.env`; `WEBAPP_SECRET` defaults empty; values shorter than 32 characters or containing common placeholder markers are rejected and cleared; `.env.example` and `sample.env` leave the value blank; startup validation now includes the secret. Missing/invalid secret fails closed at the internal-auth helper. Regression coverage in `tests/test_config_secret_defaults.py` proves the public template is not loaded and weak local values fail closed.
- **Follow-up:** Verify private Render and Vercel env settings without printing them. If either ever used the example value or a weak value, coordinate rotation on both hosts and redeploy. Exercise a correctly configured and a missing-secret staging deployment.
- **Suggested additional test:** With Flask test client, prove every internal route rejects requests when `WEBAPP_SECRET` is missing/weak and accepts only the configured strong test secret. A direct helper assertion was added to `tests/test_owner_identity.py`, but that full test module could not be run in this local dependency environment.

### SEC-02 — Owner account identifier was embedded in public/client source

- **Severity:** High (privacy exposure; not an authentication bypass by itself)
- **Confidence:** Confirmed
- **Status:** Removed from the current worktree; no history rewrite performed.
- **Affected:** formerly `webapp/src/lib/access.ts`, auth UI/API, bot owner guards, Render config, README/features and historical docs/CSV/tests.
- **Evidence/impact:** The former numeric owner identifier was directly present in client/shared code and rendered on the sign-in page, plus tracked docs and deployment config. It exposed a stable Telegram account identifier and allowed enumeration/targeted contact. It was not the sole authorization check; server-side signed Telegram validation existed.
- **Worktree remediation:** server-only `webapp/src/lib/owner-config.ts` reads `OWNER_ID`; `webapp/src/lib/access.ts` no longer exports it to client code; `/api/auth` compares server-side and returns only `{ ok, owner }`; backend and bot checks use configured owner identity; deployment templates now request private configuration. Tests use a synthetic non-production fixture. A public bundle scan with a synthetic configured ID passed. A byte scan found zero former-ID matches in the current non-generated tree and in `.next/static` / `.next/server/app`.
- **Deployment requirement:** set `OWNER_ID` as a server-only environment variable on **both Render and Vercel**. Auth intentionally fails closed without it. This setting has not been changed on either live service.
- **History limitation:** previously published Git commits are untouched by design. Older commits may remain searchable; removing them would require a coordinated history rewrite, which was not done.
- **Regression test:** web auth test verifies no `user` details are echoed and missing owner configuration returns 503 before backend contact. Add a CI assertion that client chunks never contain the configured owner ID when present at build time; `webapp/scripts/check-public-bundle.mjs` now includes `OWNER_ID` in its configured-value scan.

### TEST-01 — PR Python contract-test job did not finish

- **Severity:** High (release confidence / CI gate)
- **Confidence:** Confirmed for the observed run; root cause of runtime length **needs investigation**.
- **Affected:** `.github/workflows/ci.yml`, Python `Bot backend` job.
- **Evidence:** `gh pr checks 5` showed the PR's `Bot backend` job as failed/cancelled after **25m15s**. `gh run view` identifies the test step `Run offline contract tests` as cancelled; dependency advisory audit, SBOM generation and compile completed successfully. Logs could not be fetched in this environment (GitHub log endpoint returned EOF), so no assertion failure or hang is claimed.
- **Impact:** The required Python suite has no passing result for the current PR head; a long suite may mask a hanging/flaky test or simply exceed the 25-minute budget. No conclusion can be drawn about Python functional correctness from this run.
- **Reproduction:** Inspect GitHub Actions run `41315283465`, job `124873959515`, at the original PR head. Local broad/selected unittest execution was also blocked by missing packages (see §15).
- **Recommendation:** Fetch the run log from GitHub, identify the slow test/module, report per-test durations, then split independent suites or remove avoidable global setup without weakening assertions. Raise the timeout only after identifying why the test takes >25 minutes.
- **Suggested regression:** CI should emit per-test duration data and a standalone timeout test for the identified slow/hanging case.

## 5. Medium-priority findings

### MUS-01 — Non-numeric search-result duration raises before the guarded parser

- **Severity:** Medium
- **Confidence:** Confirmed by source control flow and reproduced before the fix; provider occurrence frequency **needs verification**.
- **Status:** Fixed in the current worktree with regression tests; not deployed.
- **Affected:** `videl/utils/youtube.py::_parse_search_duration`, `search_yt_multi()`; `tests/test_youtube_search_duration.py`.
- **Evidence:** Line 459 converts every non-empty colon-separated duration piece using `int(x)` because the filter condition is `x.isdigit() or x` (the second condition is true for every non-empty string). The conversion sits *before* the following `try/except`, which already attempts a guarded conversion and fallback to zero. A result duration such as `LIVE`, `Upcoming`, or malformed provider text raises `ValueError` and aborts the entire search rather than returning the other results.
- **Impact:** Search can fail on an otherwise valid provider response containing a non-numeric duration; if the malformed result is in the returned result list, the user sees a search failure instead of usable tracks.
- **Reproduction:** Mock `VideosSearch.next()` to return one item with `duration: "LIVE"`; call `search_yt_multi()`. Execution fails at the list comprehension before reaching the guarded parser.
- **Fix in worktree:** Removed the unguarded conversion and added `_parse_search_duration()`, which bounds input length, accepts one-to-three ASCII numeric components, rejects invalid minute/second ranges, and returns zero for unknown/malformed values. Search now continues and retains valid neighboring tracks. The UI/API contract uses `PT0M0S` for unknown duration; provider text remains available in the `duration` field. This is not deployed.
- **Regression:** `tests/test_youtube_search_duration.py` covers `LIVE`, negative/malformed/empty components, invalid minute/second ranges, one/two/three-component forms, and mixed malformed/valid provider results.

### MUS-02 — Same-video concurrent download coordination

- **Severity:** Medium
- **Confidence:** Strong evidence / source-confirmed shared paths; process-local behavior is now barrier-tested.
- **Affected:** `videl/utils/youtube.py`; public `download_song()` and `download_video()` paths and provider helpers.
- **Evidence:** Before the fix, both public functions could pass the shared-cache lookup and concurrently enter providers that use deterministic video-ID paths. The new process-local flight registry shares one result per `(video_id, media_type)` across asyncio event loops; it is removed after completion, failure, or cancellation. Different IDs and audio/video types remain independent.
- **Impact/fix:** Duplicate same-process provider work and same-process `.part` contention are prevented. Cross-process contention remains if multiple workers share one download directory; there is no distributed lock or unique per-process temp name.
- **Tests:** `tests/test_downloader_concurrency.py` has nine deterministic barriers covering cross-event-loop same-ID audio, same-ID video, distinct IDs, distinct media types, shared failure, leader cancellation/retry, waiter cancellation isolation, registry cleanup, waiter-loop shutdown, and cancellation while a local worker thread is active. **9 passed** offline. No real provider or cookie file was used.
- **Remaining:** Design cross-process coordination only if deployment topology confirms workers share storage; persistent download cache still has no bounded eviction policy (MUS-03).

### MUS-03 — Music cache and download directory have no bounded eviction policy

- **Severity:** Medium
- **Confidence:** Strong evidence
- **Affected:** `videl/utils/youtube.py:50, 116-129, 173-206, 358-368`; `DOWNLOAD_DIR` and `_file_cache`.
- **Evidence:** `download_song()` and `download_video()` reuse local files, `_find_file()` scans the top-level download directory, and `resolve_stream()` adds entries to `_file_cache`. No age/size/count eviction was found on this playback cache path. Other download commands clean their per-request temp directories, but that does not remove these shared music-cache files.
- **Impact:** Persistent/VPS storage can grow with the number of distinct tracks. Directory scans become slower as top-level entries accumulate; `_file_cache` can grow for multiple input URL spellings. Render's local disk lifecycle differs from mounted VPS storage, so exact operational effect depends on hosting configuration.
- **Reproduction:** Repeatedly request distinct valid IDs and inspect `DOWNLOAD_DIR` and `_file_cache`; then measure `_find_file()` time as entry count increases. No production filesystem inspection was performed.
- **Recommendation:** Define an explicit cache budget (bytes and age), protect in-use files, use indexed metadata rather than full `os.listdir` scans, and expose cache size/evictions in operations telemetry.
- **Suggested regression:** Temporary-directory tests cover LRU/TTL eviction, active-file safety and bounded cache-map length.

### DB-01 — Arcade room documents are abandoned but not expired/deleted

- **Severity:** Medium
- **Confidence:** Confirmed
- **Affected:** `videl/games/store.py:94-107, 239-258, 907-920`; `game_rooms` indexes and watchdog sweep.
- **Evidence:** Index setup adds TTL indexes for `game_events` and `game_clips`, but not `game_rooms`. `sweep()` only updates old playing/open rooms to `abandoned`; it does not delete old completed/abandoned room records. Room documents include host/player IDs, seats, optional Telegram `chat_id`, and room metadata. The sweep is invoked by `videl/core/watcher.py`.
- **Impact:** Room records and identifiers accumulate indefinitely and remain in MongoDB after the useful game/event history expires. Storage and index costs grow; retention/privacy expectations become unclear. The six-character code space also has increasing collision pressure as old documents remain (the generator retries a bounded number of candidates).
- **Reproduction:** Create and finish/abandon rooms, advance time in a test database, run `sweep()`, and verify old room docs remain. Source confirms no game-room TTL index/delete path; no production database was inspected.
- **Recommendation:** Establish a documented retention period; delete/archive rooms after events/clips are no longer needed, or add a safe TTL field/index. Ensure room-code collision behavior remains correct during migration.
- **Suggested regression:** Fake-clock/Mongo contract test proves ended rooms expire only after retention and linked events/clips remain available for the intended period.

### PERF-01 — Arcade rate-limit dictionaries retained per-room/user keys indefinitely (fixed offline)

- **Severity:** Medium
- **Confidence:** Source-confirmed; fix covered by deterministic offline tests.
- **Affected:** `videl/games/store.py` limiter state and `tests/test_arcade_rooms.py`.
- **Evidence at audit time:** `_LAST_REACT`, `_LAST_NUDGE`, `_LAST_CHAT`, `_LAST_SIGNAL` were process-global maps keyed by `(room_code, user_id)`. Old deque timestamps were pruned when a key was reused, but empty buckets and reaction/nudge timestamps were not evicted after inactivity.
- **Impact at audit time:** Unique room/player pairs could retain limiter entries for the lifetime of the process, including after all rate windows expired.
- **Follow-up implementation (2026-11-02):** All four maps are now bounded `OrderedDict`s with a per-map 10,000-key ceiling. Entries expire by their accepted monotonic timestamp when a request next touches that limiter. A shared lock makes lookup, expiry, cooldown/window checks and insertion atomic across Flask request threads. Active keys are never evicted to admit new ones; a new key gets a safe 429 while the map is full, and expired keys are purged first. Chat/signal timing now uses monotonic rather than wall-clock time.
- **Regression coverage:** fake-clock tests prove expiration, preservation of active buckets, cap behavior for chat/signals/cooldowns, a 10,000-key stress boundary, and atomic same-key concurrent chat admission. `test_arcade_rooms.py` 48, `test_arcade_api.py` 16, and `test_game_rules.py` 64 passed. No live memory profile or multi-process test was run; caps remain per process.

### SEC-03 — Eldian media API reused `WEBAPP_SECRET` as its API key fallback

- **Severity:** Medium
- **Confidence:** Confirmed and reproduced before the fix.
- **Status:** Fixed in the current worktree with a regression test; not deployed.
- **Affected:** `config.py`; `videl/utils/youtube.py`; `videl/api/eldian_routes.py`; `tests/test_music_webapp_api.py`.
- **Evidence:** Before the fix, when `ELDIAN_API_KEY` was unset, the client and server fell back to `WEBAPP_SECRET`. This coupled the owner-panel internal HMAC credential with the media API key.
- **Impact:** Compromise/rotation of one service secret affected both trust boundaries and least-privilege isolation was lost.
- **Reproduction:** With only a synthetic `WEBAPP_SECRET` configured and `ELDIAN_API_KEY` empty, `GET /api/status` accepted the webapp secret in `X-API-Key`; the new regression initially failed (returned 200 instead of 401).
- **Worktree fix:** `config.ELDIAN_API_KEY`, the YouTube client and server route now read only `ELDIAN_API_KEY`. Missing key fails closed. Render already declares a separate `ELDIAN_API_KEY` setting, and `.env.example` documents it separately.
- **Regression:** `test_public_media_api_does_not_reuse_internal_webapp_secret` proves a synthetic webapp key is rejected when the Eldian key is missing and only a separate synthetic media key is accepted. `tests.test_music_webapp_api` now passes **13 tests**.

### API-01 — Eldian response streaming lacked an in-stream byte cap

- **Severity:** Medium
- **Confidence:** Confirmed and reproduced by source inspection; live provider behavior not tested.
- **Status:** Fixed in the current worktree with mocked chunk-stream regression tests; not deployed.
- **Affected:** `videl/utils/youtube.py::_save_eldian_response()` and new `tests/test_eldian_response_size.py`.
- **Evidence:** Before the fix, the Eldian response saver iterated chunks into a `.part` file without a running byte counter or response-length bound. The API route only checked resulting file size after the downloader returned.
- **Impact:** Oversized/abnormal responses could consume disk before rejection; concurrent requests multiply temporary storage pressure. Normal bot duration checks do not replace byte limits.
- **Fix in worktree:** Added a 300 MiB maximum for the Eldian client response path; rejects declared oversized `Content-Length`, counts actual bytes before writing each chunk, and removes partial files on streamed over-limit exceptions. The API route retains its post-download size check as defense in depth. Other provider paths have their own caps, but were not exhaustively revalidated here.
- **Regression:** Four tests prove early declared-length rejection, streamed over-cap cleanup, cancellation cleanup, and acceptance/atomic publication at the exact bounded size. `test_eldian_response_size`, `test_youtube_search_duration`, and `test_music_webapp_api` passed together (**18 tests**).

### OPS-01 — Music admission limits are process-local and route-specific

- **Severity:** Medium
- **Confidence:** Confirmed
- **Affected:** `videl/api/eldian_routes.py` `_SLOTS`, `/internal/music/track`, public media routes; `videl/utils/youtube.py` callers.
- **Evidence:** `_SLOTS` is a module-level two-slot semaphore shared by specific Flask endpoints. Bot callers can invoke `download_song()` outside those routes, and multiple backend processes each get their own semaphore. Rate accounting is also in-process memory.
- **Impact:** It does not provide a global limit under multiple processes, nor a hard cap for bot-triggered downloads. Under scale/restarts, aggregate provider and disk load can exceed the apparent route limit.
- **Recommendation:** Keep documented scope honest; if multi-instance scaling is planned, move admission to a shared queue/lease or single worker service. Add metrics before increasing concurrency.
- **Suggested regression:** Tests should prove direct bot paths are either intentionally excluded or acquire the same admission policy; a multi-process test is required before claiming global limits.

### DEP-01 — Feature-branch deploy check does not prove the preview serves this SHA

- **Severity:** Medium (release-process clarity)
- **Confidence:** Confirmed from workflow; deployed artifact was not independently queried.
- **Status:** Misleading workflow/job wording and README claim corrected in the worktree; actual Vercel preview-SHA verification remains unimplemented.
- **Affected:** `.github/workflows/deploy-check.yml`, `README.md`, `docs/WEBAPP_RELEASE_CHECKLIST.md`.
- **Evidence:** On non-main refs the workflow explicitly skips comparing the backend revision because Render deploys from `main`, but its web-panel step checks only that the configured `WEBAPP_URL` returns HTTP 200. That URL defaults to the production site; the step does not compare a Vercel preview URL or source SHA. The workflow can pass while the PR's preview is stale or absent.
- **Impact:** A green check can be misread as candidate-preview verification. It proves an endpoint answered, not that this branch's UI was deployed.
- **Reproduction:** Inspect a feature-branch run: backend step is skipped; web panel step tests only `$WEBAPP_URL/` for status 200.
- **Recommendation:** Keep a reachability check but label it as such. Obtain the preview deployment URL/SHA from Vercel and compare it to `GITHUB_SHA` in a separate step; fail or clearly mark unavailable when no preview exists.
- **Suggested regression:** Workflow test with a stale-preview SHA must fail the “candidate verified” step even if production returns 200.

### DEP-02 — Standalone `start` script upgrades yt-dlp at every start, unlike the Docker build

- **Severity:** Low
- **Confidence:** Confirmed
- **Status:** Fixed in the current worktree; static recheck passed. Not deployed.
- **Affected:** `start`, `requirements.txt`, `Dockerfile`.
- **Evidence:** Previously `start` ran `pip install -U yt-dlp` (with fallback) on startup. The Dockerfile installs pinned requirements and launches `python main.py`, so the paths diverged. `start` now only reports the installed yt-dlp version and launches the bot; `requirements.txt` pins yt-dlp. Operators must install the pinned requirements before starting.
- **Impact:** The prior script could drift from the tested dependency and required package-index access at every boot; this is removed from the current worktree.
- **Regression:** Static check confirms no `pip install`/upgrade command remains in `start`. Consider adding a shell-level assertion if entrypoint behavior changes.

### DB-02 — Index-creation failures are swallowed, so required query performance can silently degrade

- **Severity:** Low
- **Confidence:** Confirmed behavior; production occurrence **unknown**.
- **Affected:** `videl/utils/db.py::ensure_indexes`; `videl/games/store.py::ensure_indexes`.
- **Evidence:** Both paths catch broad exceptions during index creation; the general index helper logs at debug level, and the arcade helper discards the exception. Some indexes are marked as optimizations, but missing/failed uniqueness or TTL indexes can affect consistency/retention as well as speed.
- **Impact:** Restricted DB roles, conflicting existing indexes, or invalid index options can leave the app running with missing constraints/cleanup and no prominent health warning.
- **Recommendation:** Classify indexes as required vs optional; surface required-index status in `/health`/Control Room, log collection/index name and exception type safely, and validate existing index definitions before relying on them.
- **Suggested regression:** Mongomock/fake DB test forces an index error and asserts required-index degradation is visible rather than silently reported as healthy.

## 6. Low-priority and informational findings

### CFG-01 — Unused deployment configuration remains in `config.py`

- **Severity:** Informational
- **Confidence:** Confirmed source search
- **Affected:** `config.py:141-146` (`VERCEL_TOKEN`, Vercel project/team IDs, webhook URL/secret).
- **Evidence:** Repository-wide source search found definitions but no runtime consumers for these names (other than their definitions). The webhook secret has a default value, but no active webhook route uses it in the scanned source.
- **Impact:** Misleads operators into thinking Vercel deploy/webhook automation is active; the unused default is not itself an exploitable credential while no handler consumes it.
- **Recommendation:** Remove unused config only in a separately reviewed cleanup, or implement/document the integrations with explicit authentication. Do not treat the current placeholder as an active security boundary.
- **Suggested regression:** Static config-consumer inventory test or a documented supported-env-var table.
- **Resolution (2026-11-05):** A new current-tree reference search found these names only in their `config.py` declarations and this historical audit entry. Removed the unused runtime fields and the unconsumed webhook-secret default; retained `WEBAPP_URL`, which has active backend consumers. This historical finding is retained rather than deleted.

### DOC-01 — Arcade/group-manager document contains historical design details alongside current behavior

- **Severity:** Low
- **Confidence:** Confirmed
- **Affected:** `docs/ARCADE_AND_GROUP_MANAGER.md` throughout; current top-of-file warning was added in this worktree.
- **Evidence:** The document's original status said the Group Manager screen and presence streaming were future work; current code has the screen and room presence paths. The opening is now explicitly marked historical, but older design/phase sections still contain future-state descriptions and should not be followed as a current build plan without checking source/tests.
- **Impact:** Contributors can build duplicate features or misunderstand transport/security limits.
- **Recommendation:** Preserve the historical rationale, but split a dated “design history” from a concise current architecture/status page and add links to current source/tests.
- **Suggested regression:** Documentation review checklist matches current feature flags/routes before release.

### DOC-02 — `todo.md` is the canonical backlog but mixes active status with historical snapshots

- **Severity:** Informational
- **Confidence:** Confirmed
- **Affected:** `todo.md` (large active and historical record); Stage B/C audit docs.
- **Evidence:** The backlog explicitly says it is the single source of truth, but contains old “next task” instructions, per-stage snapshots and repeated status notes. Newer current-state notes now mark the full audit as in progress; older sections must remain historical rather than be deleted blindly.
- **Impact:** A reader can follow stale next steps or treat past test results as current. Useful history/security decisions must be preserved.
- **Recommendation:** Keep the file and history; add a dated “current status” index and mark superseded action prompts as historical. Link each active item to one owner/status section.
- **Suggested regression:** Lightweight docs check ensures current branch/PR status appears once in the current-state section and old branch data is explicitly dated.

## 7. Security review summary

### Verified protective controls

- Owner authentication validates Telegram Mini App/Login Widget signatures backend-side; private APIs use expiring signed HttpOnly/Secure cookies. The webapp has same-origin route guards and cross-site state-change rejection tests.
- Player/Arcade identity uses a separate session/actor assertion path; the backend routes require the internal secret and signed actor rather than trusting a browser-supplied player ID.
- Callback and connected-group audits document actor/target binding, fresh authorization, revision/CAS checks and confirmation flows. They are substantial evidence, not proof every callback has equivalent coverage.
- Internal backend auth uses `hmac.compare_digest`; media ID inputs are constrained; downloader redirects are disabled in reviewed provider calls; route output sizes and per-process concurrency are bounded in some paths.
- Public-bundle CI scans configured server secret values; current local scan also checks a configured owner ID. Full npm audit reported 0 vulnerabilities; Python dependency advisory CI step passed in the observed run before the test job was cancelled.

### Areas not certified

No full penetration test, fuzzing, live internal-route probe, secret-rotation exercise, production Mongo inspection, group-admin live test, Render/Vercel environment audit, or proof of log-retention/credential rotation was performed. Security tests are mostly offline/mocked. No claim is made that every callback or API input is safe.

## 8. Backend, API, and webapp review

- Next route inventory is 49 files; repository tests enforce each route's declared owner/player/public boundary. This is a useful static guard but does not prove every downstream backend operation's business authorization.
- The Flask backend exposes health/status routes and internal owner/player/media/manager/Arcade routes. Internal operations depend on shared-secret verification; Arcade routes additionally validate signed actors and current Telegram group-admin status for relevant group operations.
- Request bounds, route-specific error schemas and timeouts exist in many paths. Coverage is uneven; endpoint-by-endpoint body limits, timeout and denial behavior remains to be checked.
- `docs/FULL_CODEBASE_AUDIT.md` correctly records the browser music pipeline as separate from Telegram voice playback and notes range handling and latest-request race guards. The browser player is not verified in a real browser in this environment.
- Webapp tests render components and test mocked route handlers; they do not cover all user flows, mobile browser quirks, media decoding/autoplay, or network reconnection behavior.
- No lint script is declared in `webapp/package.json`. Typecheck/build/tests are the configured web checks.

## 9. Telegram bot, permissions, and callback review

- The command catalog reports **209 live command names**; the 215-row historical baseline contains six retired entries. Existing generated inventory and Stage C ledgers are valuable.
- Stage C Batch 2 still marks the 45 music/playback/queue/playlist command review incomplete. Legacy effect/seek access is now owner/current-group-admin-only per user decision (MUS-PERM-01; six offline role tests); live Telegram role behavior remains unverified. Channel target binding and remaining callback boundaries still need review. Queue admission/recovery limits are fixed offline under MUS-QUEUE-02; 36 focused queue/play/channel/lifecycle tests pass. Vote-skip's unsafe direct-pop path was corrected under MUS-QUEUE-01: it validates the active player-card message, deduplicates actors, gates overlapping threshold operations, and delegates to the shared acknowledged transition. Eight deterministic tests pass. No live Telegram/voice validation was performed.
- The Stage B authorization matrix documents route/callback/mutation coverage, current-admin rechecks and historical immediate mutations. It is a source map, not exhaustive live permission validation.
- Telegram Bot API 10.3 features and custom UI fallbacks have offline tests; no live Bot API capability/eligibility test was performed.
- Background task creation exists in reminders, player progress, autoplay, group-view jobs, CAPTCHA, queue persistence and watchdog paths. This pass did not exhaustively verify cancellation, exception retrieval and cleanup for every task.
- No clone-bot-specific behavior was established in the audited configuration; multi-process and multiple-bot deployments still need explicit review for process-local locks, cache keys, unique IDs and shared Mongo state.

## 10. MongoDB and data integrity review

- MongoDB is the only configured application database. `videl/utils/db.py` creates indexes on startup, uses finite connection/server/socket timeouts, and degrades on connection failure. `mongomock` provides offline contract tests but does not validate Atlas replica-set, authorization, TTL timing or real write-concern behavior.
- Several feature collections define TTL indexes (analytics, audit/events/clips and temporary state). TTL deletion is asynchronous in Mongo; application cleanup and UI must not assume exact deletion time.
- Arcade event/clip TTL exists but `game_rooms` has no TTL; current watchdog sweep only marks stale rooms abandoned (DB-01).
- No separate numbered migration framework was found in the tracked inventory. Indexes are created idempotently; schema changes rely on compatible code/data writes. Before destructive field changes, use an explicit migration/backup plan.
- Queue recovery intentionally restores records for explicit user action rather than resuming streams at startup. That is a deliberate safety boundary, not a missing auto-resume bug.
- Backup/restore and Mongo outage paths have focused mocked tests. Live restore, concurrent writers, database outage/recovery and actual restart behavior remain unverified.

## 11. Music, browser playback, and streaming review

### Verified architecture boundaries

- Browser Studio Music uses an HTML audio player and local browser queue. Telegram group playback uses the bot queue/PyTgCalls. There is no evidence that pressing browser play mutates a Telegram voice chat queue.
- Backend media routes accept constrained YouTube IDs/URLs, use server-side credentials, cap selected routes and return private/no-store range-capable responses. Existing tests cover backend range/status and a mocked Next 206 pass-through.
- Stage D added deterministic latest-request protections for browser play promises/searches and a shared two-slot budget on the internal preparation route; see `docs/FULL_CODEBASE_AUDIT.md`.

### Remaining risks and limitations

- Same-video requests are coalesced within one process by MUS-02; multiple processes sharing a download directory remain uncoordinated.
- Shared playback cache can grow without eviction and is scanned linearly (MUS-03).
- MUS-01 is fixed in the worktree: malformed provider durations now yield an unknown duration without aborting search; the Eldian client also has an in-stream size cap (API-01). These changes are not deployed.
- Route semaphore/rate limits are process-local and not a global cap (OPS-01).
- Expired URLs, refresh/remount behavior, real seeking, browser decoding/autoplay and mobile network recovery were not exercised in an installed browser. The prior Playwright attempt could not launch because Chromium was unavailable.
- No real Telegram voice chat, PyTgCalls session, media provider, Render filesystem or rate limit was tested.

## 12. Performance and scalability

1. **Likely first pressure point — media disk and provider concurrency:** same-track duplication and no cache eviction can grow storage and duplicate upstream work before CPU is saturated.
2. **Arcade in-memory limiter keys:** PERF-01 is bounded offline to 10,000 keys per limiter with lazy TTL expiry and safe rejection at capacity; memory and enforcement remain process-local, so separate workers do not share buckets.
3. **Mongo game room history:** abandoned room documents remain; query indexes help current lobby reads but do not bound collection growth (DB-01).
4. **Process-local assumptions:** locks/semaphores/rate counters do not coordinate across replicas; more backend instances can multiply accepted work.
5. **Async request paths:** Flask handlers call asynchronous downloader work using `asyncio.run`/`wait_for` in worker threads; this is bounded for selected routes but should be profiled under multiple users and provider timeouts.
6. **Frontend assets:** 74 public files include 54 post assets plus other artwork. No current bundle-size baseline or image-weight budget was recorded in this audit; the production build succeeds, but performance on a low-end phone was not measured.
7. **Control Room:** current telemetry is application/process/API/Mongo-oriented. It does not provide Render deploy/build logs or platform CPU/memory graphs (see §13).

## 13. Deployment, operations, and monitoring

- `render.yaml` declares the Docker backend, health endpoint, Singapore region/free plan, and server environment keys. `Dockerfile` installs dependencies, compiles modules, creates a non-root user and defines a local health check. These are source facts, not live deployment verification.
- `docker-compose.yml` is a local setup with a legacy `videl.db` volume despite MongoDB being the application DB; verify whether the unused volume is still needed before removing it. The optional web container uses Node 20 while CI uses Node 22; test compatibility or align versions.
- The Render plan is free in the checked-in manifest; cold starts and resource limits are deployment characteristics to verify on the actual service. No live plan/metrics were inspected.
- DEP-02's runtime yt-dlp mutation was removed from `start` in the current worktree; Docker and script startup now rely on the pinned install. Not deployed.
- `/health` reports application state, revision, bot, database, assistant, downloader and measured API/DB metrics. This is not Render control-plane monitoring. No Render API token/client or deployment/log endpoint was found in the checked-in source/config, and none was requested.
- The deploy-check workflow's non-main behavior is a reachability check, not proof a PR preview serves the PR SHA (DEP-01).
- No shutdown/redeploy was performed. Graceful cancellation of every task and worker under SIGTERM remains a live/runtime verification item.

## 14. Dependencies and supply chain

- `requirements.txt` pins direct Python dependencies; `requirements-dev.txt` adds `mongomock`. CI runs `pip-audit`, Python compilation/tests and CycloneDX SBOM upload. The observed CI advisory scan passed, but its Python test step was cancelled at the timeout.
- Webapp lockfile is tracked; `npm audit` in this workspace reported **0 vulnerabilities**. Webapp CI also ran npm audit and uploaded an SBOM successfully on the observed PR check.
- Local `.venv` lacks `requests` and `pytgcalls`; local `pip-audit` is not installed. `pip check` reported no broken installed requirements but does not prove the project dependency set is installed.
- `start` no longer performs a runtime package upgrade in the current worktree (DEP-02); pinned install procedure is required and deployment was not tested.
- No full unused-dependency proof was performed. A source search found the Vercel/webhook config names in `config.py` without current consumers (CFG-01); this does not establish unused third-party package dependencies.

## 15. Tests and exact verification results

### Passed in this work session

- `npm test` — **230 passed, 0 failed, 0 skipped**.
- `npm run typecheck` — passed.
- `npm run build` — passed; Next.js compiled and generated the app routes.
- `OWNER_ID=<synthetic test value> npm run check:public-bundle` — passed; 43 public assets scanned and no configured values/credential-shaped strings found.
- `npm audit` — **0 vulnerabilities**.
- `.venv/bin/python -m unittest tests.test_config_secret_defaults -v` — **2 passed**.
- `.venv/bin/python -m unittest tests.test_config_secret_defaults tests.test_youtube_search_duration tests.test_eldian_response_size tests.test_music_webapp_api -q` — **20 passed** after the SEC-01, SEC-03, MUS-01 and API-01 changes. Media-only subset: **18 passed**.
- `.venv/bin/python -m unittest tests.test_vote_skip -v` — **8 passed** for MUS-QUEUE-01; focused compile of `smartqueue.py`, `player.py` and the new test passed; `git diff --check` passed after the follow-up.
- PERF-01 arcade limiter follow-up (2026-11-02): `test_arcade_rooms.py` — **48 passed**; `test_arcade_api.py` — **16 passed**; `test_game_rules.py` — **64 passed**. These are offline/mock suites; the 10,000-key cap and concurrent admission are tested, but not live memory load or multi-process coordination.
- `OWNER_ID=<synthetic test value> .venv/bin/python -m compileall -q videl tests` — passed.
- `git diff --check` — passed at last check.
- Markdown relative-link scan — 26 files (25 tracked Markdown files plus this report), 0 broken local links.
- Owner ID scan — zero exact matches in current non-generated source/docs/tests/config and zero in built `.next/static` and `.next/server/app`.

### Failed, cancelled, unavailable, or not run

- GitHub PR #5 `Bot backend` job — **cancelled at 25m15s** in `Run offline contract tests`; earlier dependency audit, SBOM and compile steps passed. The downloadable job log failed with EOF from this environment, so the exact slow test/root cause remains unknown.
- Local `OWNER_ID=<synthetic test value> .venv/bin/python -m unittest tests.test_owner_identity tests.test_command_ui tests.test_replacement_domains tests.test_manager_access tests.test_plugins tests.test_automation tests.test_scheduled_posts tests.test_sudo tests.test_replacement_router -q` — **failed with 27 errors across 106 tests** because this local environment lacks runtime packages including `requests` and `pytgcalls`; it is not evidence that those tests fail with CI's complete install. In particular, the full changed owner-auth test module did not run locally.
- `pip-audit` — local command unavailable; remote CI advisory step passed on the observed run.
- Browser smoke — not completed; Chromium is absent in this environment. No browser console/network/device results are claimed.
- No Python linter/type checker is configured in the inspected project files; no Python lint result is claimed.
- No real Render, Vercel settings, Telegram, MongoDB, media provider, staging group, Android/iOS WebView or production playback validation was performed.

## 16. Documentation audit

- All 25 tracked Markdown files were read; local relative links resolve.
- `FEATURES.md` previously understated the generated Post Asset catalogue; current worktree corrects it to 54 assets (34 wide covers, 10 stories, 10 quote cards), matching `webapp/src/lib/post-assets.ts`.
- The opening state in `docs/ARCADE_AND_GROUP_MANAGER.md` previously said the Group Manager screen/presence path remained future work; current worktree marks the opening as historical. Other internal phase/architecture statements remain a reconciliation task (DOC-01).
- README and examples now describe `OWNER_ID` as privately configured, rather than printing the account identifier. `WEBAPP_SECRET` examples are blank and labeled required.
- `docs/FULL_CODEBASE_AUDIT.md`, Stage B/C docs and command CSVs retain useful historical evidence and must not be deleted. Avoid replacing snapshots with fabricated “current” measurements.
- `todo.md` is retained as the declared canonical backlog. Its current-status section was refreshed to distinguish current audit state from old next-step notes; older chronology still needs careful reconciliation, not deletion (DOC-02).
- Setup documentation should explicitly state that Render and Vercel each need the private owner ID and matching strong `WEBAPP_SECRET`, and that changing either requires redeployment. No live environment settings were checked.

## 17. Product improvements (not defects unless separately verified)

### Essential, evidence-led

1. Per-process same-ID single-flight is implemented under MUS-02. Add bounded shared-cache eviction and only add cross-process coordination if deployment topology confirms shared storage.
2. Add streaming byte caps on every provider path; expose cache/disk use and active downloads in Control Room.
3. Finish Stage C Batch 2's source/callback review and close its queue/vote/target authorization questions with regression tests.
4. Add bounded retention and cleanup for Arcade rooms and per-user throttling state.
5. Make deployment checks distinguish “production endpoint reachable” from “this preview SHA deployed.”
6. Add a real browser smoke lane with installed Chromium for audio source changes, seeking, play rejection/recovery, navigation/unmount cleanup and stale requests.
7. Keep Videl process metrics and Render platform metrics as separate, accurately labeled data sources; implement Render API integration only with server-side least-privilege credentials and unavailable states.

### Optional advanced work

- Durable media worker queue with cancellation/idempotency and cross-instance admission.
- Explicit browser playback history/playlist persistence with clear local-vs-server privacy choices.
- Arcade match/room retention controls visible to users; admin export/deletion policy.
- Mobile WebView test matrix for safe areas, cookies, microphone/audio session behavior, and keyboard/touch targets.
- Add operational SLOs and alert thresholds around API p95, Mongo p95, disk headroom, media failure rate and bot reconnect loops.
- Dependency/license inventory automation for vendored projects and dead-config detection.

## 18. Prioritized action plan

1. **P0 security before next deploy:** verify private Render/Vercel `WEBAPP_SECRET` and `OWNER_ID` values; rotate the shared secret if the example/weak value could have been deployed; deploy the fail-closed config changes only after both environments are ready.
2. **P0 CI:** inspect the cancelled GitHub backend test log; isolate the >25-minute test or suite; require a completed backend job before merge.
3. **P1 media correctness:** malformed-duration handling and per-process per-video single-flight are fixed/tested; define bounded cache policy and decide whether multi-process coordination is needed.
4. **P1 persistence/scale:** define room retention and expire/delete completed rooms; PERF-01 limiter memory bounds are implemented and offline-tested, but validate expected 429-at-capacity behavior under staging load and recognize the limits are per process.
5. **P1 credentials/limits:** Eldian key separation and streamed response size enforcement are fixed in the current worktree; verify private deployment key configuration and review every other provider's caps/cleanup path before closing this area.
6. **P2 release process:** make Vercel Preview SHA validation explicit; review Python startup/shutdown task cancellation; align `start`, Docker and Node runtime versions.
7. **P2 audit completion:** finish 45 music commands, then remaining command/callback/admin mutations, route-by-route API input/response review, all DB query/index/TTL paths, and every frontend interaction.
8. **P2 docs:** reconcile historical Arcade phases and backlog status; retain audit evidence; keep setup/security/deploy instructions generated from actual environment requirements.
9. **P3 live validation:** with owner-approved staging credentials, verify Render health/degraded states, Mongo restart/recovery, Telegram permissions/callbacks, media provider behavior, and mobile/browser playback. Record service SHA and test setup without secret values.

## 19. Files and components inspected

### Deeply traced in this pass or prior scoped audit records

- `config.py`, `.env.example`, `sample.env`, `render.yaml`, `Dockerfile`, `docker-compose.yml`, `koyeb.yaml`, `start`, `requirements*.txt`, `.github/workflows/ci.yml`, `.github/workflows/deploy-check.yml`.
- `videl/__main__.py` health/auth/internal API and startup paths; `videl/api/eldian_routes.py`; `videl/api/actor.py`; `videl/api/group_view_routes.py`; `videl/api/manager_routes.py`; `videl/games/routes.py`; `videl/games/store.py`; `videl/utils/db.py`; `videl/utils/youtube.py`; command catalog/router and relevant auth helpers.
- `webapp/src/lib/auth.ts`, `access.ts`, owner config, backend proxy, Studio Music and latest request helpers, music API routes, owner auth/API routes, Arcade player session paths; 49 route inventory and source-backed auth inventory tests.
- `tests/test_config_secret_defaults.py` (new), owner/auth and focused media API/player regression suites by audit records; `webapp/tests/` broad unit suite; public bundle checker.
- All 25 tracked Markdown files, including README, FEATURES, TODO, security/audit/release docs, vendor documentation and web test README.

### Inventory-checked but not fully line-by-line reviewed

All remaining modules in `videl/modules/`, `plugins/`, `utils/`, `core/`, `games/`; all non-auth/music/Arcade web screens/components and their API interactions; all Mongo CRUD methods and every index/query; all callbacks/keyboard paths; all vendored implementation details; every fixture/assertion in 129 Python and 45 web test files; and every media asset's licensing/weight/accessibility.

## 20. Areas explicitly not verified / limits

- This is a partial audit, not an assertion that every command, callback, component, or query was inspected line by line.
- No live credentials, secrets, Render/Vercel dashboards, GitHub-hosted log archive, production DB, Telegram account/group, real media provider or staging system were accessed.
- No real browser was launched; Chromium is absent. No mobile/Telegram WebView device was available.
- The full Python suite did not complete locally; GitHub's Python test step was cancelled by timeout. Focused config regression tests did pass locally.
- No throughput, soak, memory, disk-fill, multi-instance, replica-set, concurrent migration or fault-injection test was run.
- Existing tests are primarily offline/mock based; passing web tests/build does not prove real Telegram delivery, browser audio playback, deployment health, or database recovery.
- Existing published history was not rewritten. The worktree's privacy/security fixes and this report have not been committed or pushed. PR #5 remains OPEN/unmerged.
