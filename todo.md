# Videl active feature and code-improvement backlog

Backlog IDs are stable; gaps mean completed or deliberately removed entries. Treat remaining items as unimplemented until behavior, permissions, tests and docs are verified. Work incrementally, prefer improving existing functionality, and remove an item only after validation.

## Delivery phases
- **Phase 1 — Security foundation (in progress):** #201–202, #204–205. Added a security model, per-handler API-guard inventory, bounded auth/bulk request parsing, DJ membership recheck, global web security headers, log/error/URL secret redaction, a sentinel scan of built public assets and explicit previews/confirmations for bulk and restore operations. #141, #203 and #206 are complete: owner/player sessions have tested signing, secure cookie scope, expiry, rotation/logout and CSRF/origin handling; Python and npm advisories are checked in CI and CycloneDX SBOMs are emitted as artifacts. Authorization feedback now distinguishes a blocked account/group from an unverified role or permission; continue with remaining authorization edge cases, secret-leak checks and destructive-action confirmations.
- **Phase 2 — Admin and group management (in progress):** #207–213. The group-admin workspace already scopes reads/actions to a Telegram-verified admin, provides group settings, health/setup status, inbox workflows, revision-aware writes, backups/recovery and guided bot-rights status. This pass added filtered per-group audit history with bounded, actor-ID-minimizing CSV export and explicit confirmations for join-request and report decisions. Keep Phase 2 open until the full settings inventory, audit/export, bulk preview, validation/recovery and rights-guidance flows are individually verified.
- **Phase 3 — Webapp quality and security (in progress):** #214–222. API-route guard inventory now distinguishes owner-only routes from Telegram-player group-manager/arcade routes instead of accepting either guard indiscriminately; real-handler tests also prove owner cookies cannot enter player routes and player cookies cannot enter owner routes, with both denied before backend access. Browser smoke coverage remains in place. Recent passes added real-handler tests for group-manager authorization/audit forwarding and player-session issuance, status, cross-site denial and logout cookie clearing; tests also pin bounded backend timeout/retry classification. The group-admin workspace now exposes active section state and accessible names for its key controls. Added `docs/WEBAPP_RELEASE_CHECKLIST.md` for preview/source-SHA checks, backend compatibility, schema/index rollout, feature gates, health, rollback and post-release observation. The real Chromium suite could not run in this environment because no browser binary is installed. Continue with a full role matrix, actual revoked-token handling, keyboard/screen-reader/mobile review and route contracts.
- **Phase 4 — Remaining product backlog:** work through the other active IDs in order, validating each before removal. Latest pass: `/ping` now provides a bounded, read-only snapshot of Telegram latency, CPU/load, RAM (container-aware), disk, process footprint, database/assistant/watchdog status, aggregate music-queue counts, uptime and build revision; failures degrade to safe status labels. This advances diagnostic visibility but does not complete #41 or #200 (no support-bundle export, correlation ID or delivery workflow).
- **Next prioritized implementation sequence:** #234 code containment is hardened and tested, but rotation/revocation, production-copy verification and coordinated history cleanup remain owner/maintainer actions. #235 `/song` delivery tests and #236 dual-context catalog/guide checks now run in this dependency environment; continue with #237 queue recovery and controls, then #238 stale Telegram-settings conflict handling and safe resets, #239 Music Center, and #240 privacy-safe analytics/owner diagnostics. Do not claim deployment delivery or telemetry that has not been verified.

### Member experience and privacy
29. Language selection — let members choose the language used in private bot replies.
30. New-member FAQ flow — answer common group questions from admin-written responses.

### Studio, analytics, and integrations
41. One-click diagnostic report — collect useful health details while redacting tokens and private data.
42. Command usage trends — show which commands are actually used, by group and over time.
43. Moderation trend dashboard — visualize reports and actions without exposing member identities by default.
44. Onboarding funnel insights — see where new members abandon verification or onboarding.
45. Anomaly alerts — notify an owner when usage or failure rates change unusually.
47. Webhook event stream — send selected bot events to an owner-controlled endpoint.
48. RSS-to-announcement rules — publish updates from approved feeds with rate limits and preview.
49. Redacted CSV exports — export selected group activity for review without unnecessary personal details.
50. Configuration import/export — move a group’s Videl settings between environments with validation first.
223. Better queue and playlist management — improve music queue editing, ordering, playlist creation and reuse; verify behavior against the live Telegram voice stack before claiming successful playback.
224. More advanced image editing — expand post-creator image adjustments with clear previews and safe, reversible controls.
225. More reusable post templates — let owners save, organize, duplicate and reuse post layouts/content without accidentally reusing stale destinations or schedules.
226. Cross-device draft synchronization — securely sync drafts across the owner’s signed-in devices, with conflict handling, deletion semantics and clear limits for local media.
227. Broadcast Center upgrade (High) — expand the text-first Broadcast screen to support media, albums and inline buttons; require a reviewable preview before send; support scheduled campaigns, delivery history with failure details, safe retries and campaign duplication. A queued or UI-reported success is not proof of Telegram delivery.
228. Advanced automation builder (High) — add a visual trigger → condition → action workflow builder, including welcome/goodbye workflows, keyword replies, scheduled actions, execution history and actionable error notifications. Clearly distinguish configured rules from confirmed executions.
229. Multi-admin workspace (Medium) — add owner, administrator, moderator and viewer roles; per-section permissions; admin activity history; and secure invitation, revocation and access-management flows.
230. Better analytics (Medium) — add 7-day and 30-day trends, member growth, group comparisons, moderation statistics, broadcast performance and downloadable reports with privacy-safe aggregation and clear data scope.
231. Notification Center (Medium) — centralize failed broadcasts, group alerts, bot disconnections, pending reports, automation failures and scheduled-post results, with honest delivery state and user-controlled notification preferences.
232. Arcade reliability improvements (Polish) — improve reconnect handling, player presence and voice reliability; assess and verify TURN relay support as a documented reliability upgrade, including real network-path testing.
233. Music and creator improvements (Polish) — coordinate the related queue/playlist, image-editing, reusable-template and cross-device-draft work in #223–226, alongside a persistent music player that remains available across sections.

### Next prioritized implementation sequence

234. **Cookie-secret containment (Critical; code hardening validated, operational remediation remains)** — treat the formerly tracked YouTube cookie values as compromised. The current tree has no tracked cookie jar; `.gitignore` and `.dockerignore` now exclude common cookie-jar names, and the Dockerfile only copies explicit application paths. A shared `configured_cookie_path` resolver now requires an explicitly configured absolute file outside the checkout, bounds file size, validates Netscape-format YouTube/Google auth rows, and is used by the bot downloader, local YouTube fallback and Eldian API. Cookie paths and raw yt-dlp exceptions are no longer logged. Focused coverage now verifies missing/relative/repository paths are rejected, an explicit external jar works, malformed content is rejected, redaction is preserved and the Eldian path uses the shared policy; 13 downloader-option tests pass in the supported test environment. No automatic cookie-URL fetch path was found. **Still outstanding:** rotate/revoke the credentials, verify the production deployment no longer has a copy, and coordinate a separate repository-wide history rewrite with maintainers—the cookie file was added in Git history. Never force-push from the active Arena branch or rewrite history without coordination.
235. **`/song` handler delivery tests (High; mocked delivery paths validated)** — preserve the existing handler in `videl/modules/downloader.py`, including query/reply parsing, blocked-term checks, metadata, 50 MB limit, definitive `BadRequest` document fallback, ambiguous-send behavior and cleanup. `tests/test_song_command.py` covers group/private success, reply-query parsing, blocked input, oversize files, provider errors, definite rejection, ambiguous timeout and cleanup; all 7 tests now pass in the supported dependency environment. Keep live provider/Telegram smoke tests opt-in and do not claim production delivery from mocked tests.
236. **Dual-context command catalog accuracy (High; source, generated guides and registry tests validated)** — `videl/utils/command_catalog.py` represents handlers accepting both group and private chats as `group_private`; `scripts/build_webapp_commands.py` and `webapp/src/lib/commands.ts` expose that label for `/song`, `/vsong` and `/download`. The webapp command guide is regenerated from the live command catalog and has a regression test for both context labels and generated-file freshness; retired `/setup` and `/modernhelp` remain excluded. Summary normalization preserves acronyms such as UTC. The command registry suite (9 tests) and catalog/reference suite (6 tests) pass; `docs/COMMAND_REFERENCE.md` was regenerated to match registered handlers. Webapp typecheck passes and all 210 webapp tests pass. Preserve existing command policies and filters.
237. **Durable queue metadata and safe controls (High; partially implemented; coordinate with #161 and #223)** — this pass adds admin-only `/remove`, `/move`, `/jump` and `/clearqueue` controls in `videl/app/music.py`, registers them in `videl/app/routes.py`, and documents/tests their current-track protection and rollback on an unconfirmed jump. Persistence/recovery is still outstanding: centralize queue mutations through `videl/core/queue.py`; integrate with `videl/core/player.py`, `videl/core/transitions.py`, `videl/core/playback_state.py`, `videl/core/autoplay.py`, and enqueue callers in `videl/modules/play.py`, `videl/modules/cplay.py` and `videl/modules/smartqueue.py`. Before rollout, define a versioned per-chat Mongo queue-state document and atomic revision/claim behavior. Persist only safe track/request metadata, never expiring stream URLs or temp paths. Default recovery must not auto-rejoin or replay an old voice stream: mark the active item interrupted and require explicit restore of upcoming items. Extend queue tests with persistence, restart, malformed-record, concurrent mutation and no-auto-resume cases.
238. **Conflict-safe Telegram settings and safe resets (High; coordinate with #73 and #207)** — use the existing `videl/utils/settings_store.py` revision mechanism for stale `/settings` and `/setup` callbacks in `videl/plugins/settings.py`; do not silently apply stale values through `videl/plugins/base.py`. On conflict, show current values and require the admin to review before retrying. Add per-category preview → explicit confirmation → audited reset operations, preserving existing setting keys and enforcement. Extend `tests/test_settings_revision.py` and `tests/test_command_registry_audit.py` for stale callbacks, reset scope, authorization and audit outcomes. Preserve the current command manager and existing `/permissions` diagnostics rather than adding duplicates.
239. **Integrated Music Center (Medium)** — evolve `webapp/src/components/studio/screens/Music.tsx` and authenticated `webapp/src/app/api/` routes only after verifying backend data and permissions in `videl/app/routes.py` and the existing music modules. Surface supported playback/queue state, downloader task status and failure details; add cancellation only if a real cancellable task registry exists. Keep queue editing backed by #237, reuse existing playback handlers, and test loading, empty, unavailable and failed states. Do not represent provider configuration as proof of a running task or successful Telegram delivery.
240. **Privacy-safe analytics and owner diagnostics (Medium)** — build on recorded events in `videl/utils/audit.py` and the existing read-only health/status paths. Define retention, aggregation, redaction and owner-only authorization before adding command-usage, moderation-trend, download-outcome or error views in `webapp/src/components/studio/screens/Analytics.tsx` and `OwnerHome.tsx`. Add routes only through existing auth guards and test role denial, aggregation, redaction, bounded queries and missing telemetry. Report only metrics the backend actually measures; do not infer CPU, worker, queue or provider health from reachability alone.

### Important things to verify
- No AI integration is currently enabled; do not describe any UI or workflow as AI-powered unless an actual integration is added, configured and tested.
- Inbox capture is limited by the messages and events Telegram actually delivers to the bot; do not imply complete chat history or archive coverage.
- Music playback and scheduled publishing require production-like delivery checks. A visible queue, schedule or success-shaped UI state alone does not prove Telegram accepted or delivered the action.
- The Arcade voice experience has network reliability limitations; verify connection recovery and communicate degraded/offline behavior honestly before claiming dependable voice play.

## Core upgrade backlog

### Moderation reliability and safety
51. Per-action permission preflight — check the bot's exact Telegram rights immediately before every moderation action and explain missing rights.
52. Action idempotency keys — prevent retried callbacks or network retries from applying the same moderation action twice.
53. Temporary-action expiry ledger — record mute/ban expiry and reconcile Telegram state after downtime.
54. Undo window for moderator actions — offer a short, permission-checked undo for reversible actions.
55. Bulk-action dry run — show exact targets and consequences before a multi-member action.
56. Protected-member policy editor — centrally manage users/roles automation must never act on.
57. Rule-to-action mapping — let each group choose a bounded response for each enabled rule.
58. False-positive feedback controls — let admins label a filter hit as correct or mistaken and preserve an audit entry.
59. Evidence reference links — attach a message link or Telegram message ID to a case without copying private message contents.
60. Case assignment and ownership — assign an open case to a moderator and make reassignment visible.
61. Case status states — track open, investigating, awaiting member, resolved and reopened states.
62. Moderator action quotas — optional per-moderator rate limits for high-impact controls.
63. Emergency stop for automation — permission-checked control to pause automated enforcement while preserving settings.
64. Scheduled protection expiry review — surface protections enabled beyond their configured incident window.
65. Join-wave visibility — show join counts in short time buckets without exposing member identities by default.
66. Bot permission change alerts — notify admins when required Telegram permissions are removed or restored.
67. Admin roster change log — record administrator additions/removals and honestly flag unavailable actor attribution.
68. Quiet moderation mode — suppress public action announcements while keeping private audit records.
69. Escalation explainability — show which active warnings and ladder rung produced an automated decision.
70. Safety policy simulator — replay synthetic messages and joins against current rules without Telegram side effects.

### Configuration and operations
71. Typed settings schema — validate every stored group setting against a versioned schema at read and write time.
72. Settings migration framework — safely migrate old configuration documents idempotently as features evolve.
73. Per-setting revision conflicts — prevent unrelated edits from conflicting while protecting against stale writes.
74. Configuration diff viewer — compare current settings with a named snapshot or previous revision.
75. Snapshot retention policy — cap snapshot count and age with clear owner-controlled retention.
76. Configuration validation report — identify unsupported values, missing permissions and obsolete keys before import.
77. Import portability checks — detect source-specific IDs or unavailable features before applying settings elsewhere.
78. Group settings ownership transfer — let current admins designate a new configuration contact without transferring bot ownership.
79. Per-group feature health — show whether each configured feature is active, not merely switched on.
80. Deployment compatibility banner — warn when frontend and backend API/schema versions differ.
81. Maintenance window scheduler — plan backend maintenance notices with timezone-aware start/end times.
82. Database index health check — detect missing or failed indexes needed by active group features.
83. Backup verification — parse and validate generated backups before offering download.
84. Restore recovery point — keep a bounded pre-restore snapshot and provide a tested rollback path.
85. Background job registry — expose safe status, last run, duration and failure reason for scheduled workers.
86. Job retry policy controls — make retries bounded, observable and safe for non-idempotent operations.
87. Multi-instance coordination — use leases or atomic claims so only one bot instance runs singleton jobs.
88. Operational incident log — group related service failures into a timeline with recovery markers.
89. Feature flags by group — roll out risky features to selected groups and disable them quickly if needed.
90. Read-only service mode — let the panel inspect state while blocking mutations during maintenance.

### Privacy, identity and member controls
91. Member data inventory page — explain stored data categories and purposes in plain language.
92. Export request status — give members a private status and completion notice for data exports.
93. Deletion preview — show which records will be removed and which audit obligations remain before deletion.
94. Pseudonymized analytics mode — aggregate trends without retaining user IDs in analytics records.
95. Private-message consent controls — let users opt out of nonessential bot-initiated private messages.
96. Notification delivery preferences — choose message, digest or no delivery per notification category.
97. Member notification unsubscribe — provide a one-step way to stop optional bot messages.
98. Data access audit — record moderator access to sensitive member records and case details.
99. Privacy-safe case exports — omit user IDs and message references unless the exporter has explicit permission.
100. Member-facing action explanation — privately explain moderation actions when policy allows it.
101. Appeal deadline and status — show eligibility, submission limits and outcome state clearly.
102. Duplicate appeal protection — prevent spam while allowing a new appeal after meaningful change.
103. Member self-service warning view — let members privately see their active warning count and appeal route.
104. Consent-aware onboarding — explain verification data and retention before asking a member to complete checks.
105. Accessible verification alternatives — offer an admin-configured fallback when a member cannot use the default challenge.
106. Temporary data hold — pause automatic deletion for a case with visible expiry and audit record.
107. Data deletion completion receipt — report deleted categories and retained audit metadata without exposing unrelated records.
108. Privacy-safe public links — use expiring, scoped links for case or event views instead of exposing internal IDs.
109. Account session management — list and revoke active web sessions with clear device/time metadata.
110. Private profile data minimization — store only fields required by a feature and discard transient Telegram profile data.

### Studio, API and developer experience
131. Accessible status announcements — expose loading, success and error changes to assistive technology consistently.
132. Keyboard-first moderation queues — support predictable focus, shortcuts and visible focus states without accidental actions.
133. Unified empty/error states — distinguish no data, unavailable backend, missing permission and partial results.
134. API contract tests — verify request/response schemas across Flask backend and Next.js routes.
135. API rate-limit headers — expose retry timing and remaining capacity without leaking internal infrastructure.
136. Correlation IDs — connect UI operations, API requests and backend logs with a redacted request identifier.
137. Structured redacted logs — standardize event fields while preventing secrets and private message content entering logs.
138. Request timeout budgets — give each upstream API call a bounded timeout and truthful failure response.
139. Circuit breakers for providers — pause repeated calls to failing services and recover gradually.
140. Dependency inventory and update report — track direct dependencies, licenses and known stale versions.
142. Cross-site request protection audit — cover every state-changing route with origin/session checks and regression tests.
143. Webhook signing and replay defense — authenticate event deliveries with signatures, timestamps and bounded replay windows.
144. Webhook delivery controls — support test events, pause/resume, bounded retries and secret rotation.
145. Event schema versioning — version audit and webhook payloads so integrations can evolve safely.
146. Data export job progress — produce large exports asynchronously with expiry and scoped download access.
147. Saved analytics filters — let owners reuse date range and group filters without changing data visibility rules.
148. Dashboard performance budget — track slow panel calls and reduce redundant requests with safe caching.
149. Owner-configurable alert thresholds — set bounded thresholds with cooldowns to prevent alert floods.
150. Feature capability registry — expose what is enabled, required permissions, dependencies and limitations from one accurate source.

## Current-code review and engineering improvements

These are concrete hardening and maintenance tasks for the existing repository, not claims that current behavior is broken. Check referenced flows before changing them and preserve behavior unless an item explicitly calls for a change.

### Runtime, routing and correctness
151. Finish the unified command registry migration — move remaining legacy handlers into the declarative router or document why each must stay legacy; prevent duplicate handlers.
152. Make command discovery authoritative — generate BotFather menus, web guide, `/help`, and command reference from the installed manifest; fail CI on missing/stale entries.
153. Add command dispatch integration tests — exercise parsing, permissions, group blocks, disabled-command rules, callbacks and the single-send boundary.
154. Test with the actual pinned Telegram client in CI — install the supported Kurigram/PyTgCalls set in a clean test job.
155. Audit blocking I/O in async handlers — move synchronous Mongo, filesystem and network operations off the event loop.
156. Standardize “not confirmed” outcomes — distinguish rejection from timeout/unknown delivery and never retry ambiguous side effects automatically.
157. Add race tests for high-impact flows — cover duplicate callbacks, concurrent approvals, simultaneous state changes, stale settings and worker restarts.
158. Graceful shutdown for every worker — cancel and await background tasks before closing clients; restore only safe pending jobs.
159. Bound process-local state — inventory caches, queues, maps and dedupe tables; set explicit size/age limits and safe eviction.
161. Persist only restart-safe queue data — separate durable request metadata from temporary files and active voice state.
162. Improve settings round-trip coverage — ensure new settings such as welcome checklist, FAQ and retention survive backup/export/import with validation and safe defaults.
163. Add a database migration dry run — report schema/index changes and conflicts before applying idempotent migrations.
164. Review collection indexes against real queries — measure before adding indexes and handle index-option migrations safely.
165. Create reusable authorization tests — prove sudo never substitutes for Telegram admin status and owner-only controls remain private.
166. Inventory every command’s required bot rights — define Telegram permissions and explain missing rights before attempted mutations.
167. Validate persisted documents at boundaries — reject malformed, oversized or legacy-shaped Mongo values before use.
168. Standardize size limits and pagination — bound command responses, DB cursors, exports, keyboards and API payloads.
169. Add API contract and generated-schema checks — detect drift between Flask, Next.js, TypeScript and Studio assumptions.
170. Add end-to-end release smoke checks — validate clean install, bot boot, web build, route health, migrations and shutdown in CI.

### Everyday features worth evaluating
171. Group-specific member FAQ setup wizard — guide admins through short Q&A entries, preview and reset/export.
172. FAQ topic search and deep links — search questions or open one numbered answer without dumping the full FAQ.
173. Welcome checklist completion hints — aggregate opens/completions without exposing member-level checklists.
174. Group-specific locale — choose language for group-authored onboarding separately from member private language.
175. Translation fallback disclosure — identify untranslated strings and let members switch to English without losing settings.
176. Direct admin-contact route — privately send a short member request to opted-in group admins.
177. Admin contact availability and rate limits — prevent contact tools from spamming moderators.
178. Topic-aware reminder controls — let members choose original topic, private chat or another selected destination.
179. Reminder edit and snooze — change or delay one pending reminder with idempotent update and clear expiry.
180. Group event RSVP helper — create dated events with timezone clarity, attendee counts and admin cancellation.
181. Meeting/time-zone helper — convert between selected zones across midnight and daylight-saving boundaries.
182. Temporary trusted-member exemptions — grant a narrowly scoped, expiring filter or slowmode exemption without moderator rights.
183. Slowmode status and remaining-time feedback — explain the active limit without exposing private activity.
184. Pinned-resource index — provide a compact admin-maintained index of rules, FAQ, links and pinned posts.
185. Group-specific custom command aliases — add validated aliases while preserving original authorization and argument checks.
186. Command “what can I do here?” check — show actions available based on live bot rights and caller status.
187. Member-facing moderation receipt — privately explain an action, relevant rule and appeal path when privacy allows.
188. Member language-aware examples — translate descriptions while leaving command names, arguments, IDs and URLs unchanged.
195. User-facing status and incident banner — show known service outages, affected features and next update time without unverified recovery promises.
196. Chat-specific command aliases and disabled-command explainers — explain intentional command disablement and how admins can re-enable it.
197. Temporary announcement scheduling — schedule one announcement with preview, timezone, cancel and duplicate-send protection.
198. Group migration assistant — help admins move settings while excluding memberships, audit identities and private records.
199. New-admin guided handoff — provide a concise checklist of bot rights, enabled protections and retention choices without private content.
200. Common support bundles — send a redacted diagnostic summary with app version, command, time and correlation ID, never tokens or message contents.

## Priority focus: security, administrators, group management and webapp

### Security and access control
201. Security threat model and attack-surface map — document bot, webapp, callback, worker, storage and deployment boundaries, owners and trust assumptions.
202. Unified authorization policy tests — test every command, callback and web mutation against anonymous users, members, admins, owners, sudo operators and stale roles.
204. Secret and personal-data leak checks — scan logs, errors, exports, URLs and frontend bundles; add redaction regression tests with synthetic secrets.
205. High-risk mutation confirmation — require clear previews and explicit confirmation for destructive or broad group changes; log actor and outcome.

### Administrator experience and group management
207. Complete group settings inventory — expose each supported group-level option in a searchable, permission-aware settings hub with a clear owner and default.
208. Admin action audit explorer — filter group changes by actor, action and date while minimizing member data and supporting bounded exports.
209. Group management health overview — combine bot rights, active protections, onboarding, pending admin work and storage health without exposing private member details.
210. Admin task inbox — collect pending approvals, reports, appeals and setup warnings with live permissions and per-action confirmation.
211. Safer bulk group operations — preview affected settings/members, require fresh admin authorization and provide an auditable result.
212. Group settings validation and recovery — detect invalid combinations, explain consequences and offer a validated restore point before applying changes.
213. Bot-rights guided setup — identify missing Telegram rights for selected features and link to user-performed corrections; never promote the bot automatically.

### Webapp focus
214. Webapp authorization matrix — test every page and API route for anonymous, member, group admin, owner and sudo access; deny by default.
215. Accessible responsive admin workspace — verify keyboard, screen-reader, reduced-motion, contrast and narrow mobile layouts across every management screen.
216. Unified webapp navigation and task flows — organize group setup, moderation, analytics and owner tools without leaking owner-only controls into group admin views.
217. Frontend/backend contract enforcement — generate or validate shared schemas and fail CI on route, type or permission drift.
218. End-to-end webapp security tests — cover authentication, CSRF/origin, object-level authorization, rate limits and session revocation on real route handlers.
219. Webapp performance and resilience — measure key flows, bound client retries, provide honest offline/error states and preserve recoverable drafts.
220. Visual regression and interaction coverage — test primary admin journeys, empty/error/loading states and destructive-action previews at desktop and mobile sizes.
221. Webapp accessibility and privacy review — audit labels, focus, motion, analytics and telemetry for sensitive data before release.
222. Admin dashboard release checklist — verify deployment compatibility, migrations, feature flags, health checks, rollback and preview-before-production workflow.
