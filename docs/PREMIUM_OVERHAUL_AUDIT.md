# Videl premium-overhaul audit and implementation plan

**Audit snapshot:** branch `arena/042d6599-videl0`, commit `f2b6f835dba1f2c7c53629e30055fcb55684f6f6`. PR #5 is open against `main`. This document records the source-backed baseline audit and the staged plan; Stage A was subsequently implemented and is recorded at the end. This is not an implementation-complete report. The CSV retains the 215-command baseline, with six Stage A removals explicitly marked; 209 command names remain registered.

## 1. Executive summary

- The active AI footprint is not a single isolated feature. Gemini is used by six registered group commands, the private guest-mention reply handler, and the settings toggle; references also appear in the generated web command guide, command-reference source, configuration/example environment, and secret-redaction allowlist.
- The six AI commands are `/faqassist`, `/faqcancel`, `/guardianai`, `/guardianjoin`, `/guardiansummary`, and `/safetycheck`. In particular, `guardianjoin` and `guardiansummary` also send data to Gemini; despite their names, they are not non-AI utilities.
- Keep ordinary `/faq` and `/setfaq`, published `/rules`, anti-spam/raid/CAPTCHA/locks, moderation history/reports, approved members, welcome flows, and other independent group-safety/“Guardian Bot” functionality. `videl/plugins/guardian.py` currently contains only Gemini-dependent handlers; its module-level removal is likely safe after reference checks and command unregistration, but independent safety/moderation modules and their data must remain.
- The Gemini helper is a small custom HTTPX client, not a dedicated AI SDK. HTTPX has other application uses and must remain. The redaction module is used by general logs and URL diagnostics; preserve it and remove only its Gemini-specific token label if no longer needed.
- No AI-specific MongoDB collection/index or recurring background job was found in the scanned references. The group toggle is a field in the shared settings document; old values should be left inert rather than bulk-deleted. FAQ, notes, audit, and pending join-request data are shared/non-AI data and must not be removed.
- The command system is mixed: `videl/utils/command_catalog.py` discovers both declarative router commands and legacy Pyrogram decorators; `routes.py` supplies policy metadata for the former, while legacy command authorization also lives in filters/handlers. Help, `/commands`, the webapp guide and reference docs derive from this catalog. Telegram's BotCommand menu is separately hand-curated in `videl/utils/bot_commands.py` and contains no AI commands at this snapshot.
- Current catalog: **215 distinct registered command names**, current categories `manage` 117, `music` 45, `tools` 27, `owner` 26. Current contexts reported by discovery: group 145, chat 48, private 19, group+private 3. These discovery labels are not a substitute for handler-level availability/permission review.
- The full 215-row baseline is in [`COMMAND_INVENTORY_AUDIT.csv`](COMMAND_INVENTORY_AUDIT.csv), including description, present/proposed category, handler, permission evidence, availability, imported internal dependencies, and initial disposition. The inventory is a working audit artifact; legacy filter/decorator-derived permissions are marked for handler-level validation rather than being treated as authoritative.

## 2. AI dependency and reference map

| Area | Current dependency/use | Planned treatment |
|---|---|---|
| `videl/utils/gemini.py` | Bounded one-shot and SSE generation via shared `httpx`; imports `config.GEMINI_API_KEY` and `GEMINI_MODEL` | Remove after all inbound references are removed and focused absence/import tests exist. |
| `videl/plugins/guardian.py` | Six `Command` entries. All six handlers depend on Gemini: FAQ answer, cancellation of its stream, toggle/disclosure, safety triage, join-review guide and aggregate summary. The module currently contains no non-AI handler. | Remove all six routes and the module only after repository-wide inbound-reference confirmation. Preserve the separate FAQ/rules, moderation, onboarding, reports, join approval and safety modules. |
| `videl/modules/telegram_features.py` | Guest mention flow optionally calls Gemini. Shared capability helpers are in the separate `videl/utils/telegram_features.py` module. | Remove only the guest generation branch. Keep the guest response/module and preserve the separate shared capability-helper module. Guest answers should explain Videl's non-AI capabilities and not advertise AI setup. |
| `videl/plugins/settings.py` | `gemini_guardian_enabled` toggle, copy, callback pattern/allowlist and enabling-time API-key check; shared reset defaults/settings revisions also contain the key. | Remove user-facing/runtime toggle and AI gate. Do not delete existing documents or revise shared settings schema; leave historical field values inert. Preserve all other Safety settings and callbacks. |
| `config.py`, `.env.example` | `GEMINI_API_KEY` and `GEMINI_MODEL` config and setup notes. | Remove both definitions and example variables; audit deployment docs/templates for indirect setup references. Do not inspect or expose actual `.env` values. |
| `videl/utils/redaction.py` | Includes the literal `GEMINI_API_KEY` in a shared secret-name list. | Keep shared redaction and its tests; remove only this provider-specific name if no remaining supported credential uses it. |
| `scripts/build_webapp_commands.py`, `webapp/src/lib/commands.ts` | Generated command guide includes all six; generator also has usage/summary text for them. | Remove AI rows/usages from source and regenerate the committed guide; keep the bot command source of truth and verify no ghost entries. |
| `docs/COMMAND_REFERENCE.md` | Generated reference contains all six commands. | Regenerate after unregistration, retaining `/faq` and unrelated safety commands. |
| Tests | `test_gemini_provider.py`, `test_gemini_stream.py`, `test_guardian_assistance.py`; Gemini-specific guest assertions in `test_telegram_guest.py`; toggle test in `test_settings_telegram_revision.py`. | Remove provider-only suites; replace with no-AI-registration/guest-copy/settings-callback regression coverage. Keep and adapt the non-AI guest tests and settings revision tests. Keep shared `test_redaction.py`. |
| `todo.md` | Historical records mention past Gemini delivery and test results. | Preserve historical records per scope; clearly label them as historical/removed rather than active setup or capability. |
| Collections, indexes, scheduled jobs, webapp API | No provider-specific collection/index/job/API was found in the repository-wide active-reference sweep. Shared `mgmt_audit`, `mgmt_join_requests`, FAQ/rules/notes and group settings are not AI-only. | No collection drop, data purge, index change, or unrelated route removal. Confirm with a second post-implementation source scan. |

No `google-generativeai`, OpenAI, Anthropic, or other provider SDK was found in `requirements.txt`; the custom Gemini module uses `httpx`, which is shared and must not be removed. The active standalone guest handler is a separate entry point and must be audited even after command unregistering.

## 3. Command inventory and menu audit

The catalog generated 215 unique command names at the audit commit. The full initial record is [`COMMAND_INVENTORY_AUDIT.csv`](COMMAND_INVENTORY_AUDIT.csv). Important qualifications:

1. `Command.policy` and required rights are authoritative for declarative router entries. Some commands perform additional per-target checks in handlers; these checks are not fully expressed by the manifest.
2. Legacy commands are discovered from Pyrogram decorators. Their filter expressions and obvious handler checks are recorded as evidence in the CSV, but must be inspected before any permission change. Never infer that a command is public merely because its filter is broad.
3. `scripts/build_webapp_commands.py` and `docs/COMMAND_REFERENCE.md` derive from the discovered catalog. `PUBLIC_COMMANDS` / `OWNER_COMMANDS` are a separate curated BotCommand menu. Preserve established aliases unless tests and downstream usage prove a behavior-compatible removal.
4. The six AI commands above are the only removal candidates identified in the initial command manifest. The ordinary `/faq` command and FAQ editing, Guardian-independent moderation/safety, and shared guest capability handling are retained.
5. The premium target taxonomy is broader than the current `manage/music/tools/owner` labels. Apply a new taxonomy only after mapping every row in the CSV, retaining registration names and handler behavior; verify that help/search, webapp rendering, owner/private contexts, and Telegram's 100-command-per-scope limit still agree.

## 4. Settings and connected-DM redesign plan

### Existing base to preserve

- `videl/plugins/settings.py` already has category navigation, a single saved connected-group entry/open flow, connected group name/ID banner, a separate `/preferences`, revision-tagged callbacks and content-lock pagination.
- Connection storage is one saved group per user. Do not represent that as a multi-group picker without an approved schema and a migration plan; for this pass make the one-group constraint explicit and focus search/list/detail experience around it.
- Existing filter CRUD, welcome/rules/FAQ editors, warning escalation, reports, approved-member list, presets and listening-session controls use distinct established stores and checks. Reuse them; do not clone their state into a new generic settings collection.

### Safe category mapping against actual implementations

- **Group Security:** anti-flood, raid mode, CAPTCHA/join protection, approved members, existing content locks and blacklist/sticker controls. Bot-right-dependent enablement must remain method-specific. Suspicious-join and automatic-lockdown claims require confirming existing implementations before surfacing them as settings.
- **Moderation:** warnings/escalation, bans/mutes, reports, group/admin activity and audit views, notes, history, cleanup. Reuse current command/editor/report/activity surfaces; do not add decorative controls without behavior.
- **Member Management:** approved members, welcome/goodbye, rules, FAQ and join/leave flows. Tag management and join/leave notification controls need a source audit before being exposed.
- **Content Control:** existing text filters, rules and typed content locks. No URL whitelist was found; URL blacklist/whitelist, duplicate-message, mention and sticker controls require a specific capability audit. Do not claim these exist from generic lock labels.
- **Automation:** keyword filters, existing scheduled listening announcements, reminders and warning escalation. There is no existing generic scheduled group-message/custom-rule builder in the audited command/settings surface; do not invent a parallel automation engine in this pass.
- **Telegram Tools:** reuse existing file/media, IDs, profile, group and bot information commands; settings should link/navigate to them rather than duplicate their configuration.
- **Group Administration:** settings, permission diagnostics, group metadata, statistics and audit history already exist in separate command/API domains. Integrate navigation only where safe.
- **Appearance & Preferences:** preserve personal `/preferences` separation; reuse existing welcome text/media/checklist/button configuration. Night mode and arbitrary menu preferences have no verified group setting implementation.

For both group and DM: make current status and permission needs explicit, preserve revision/CAS, bind actor/chat/target, freshly resolve connected groups, reauthorize sensitive writes, keep destructive confirmation and error states, and add return-to-home/back behavior without publishing owner-only options to groups. Use existing Telegram button primitives and webapp styles; avoid a large new UI framework.

## 5. Engineering, performance and security risk assessment

| Risk / finding | Why it matters | Planned mitigation / validation |
|---|---|---|
| Broad cleanup spans the entire application, backend API, vendored libraries and Next.js app. | A global rewrite or deletion based only on text search can break stable group/moderation/media workflows. | Small domain commits; stage-specific tests; inspect inbound references before deleting any module or dependency. |
| Legacy and declarative command systems coexist. | Handler filters, authorization, help and BotCommand menus can drift independently. | Keep the catalog audit; add registration/handler/context consistency checks; change policy only with exact regression coverage. |
| Gemini toggle may exist in stored group documents. | Removing a field from runtime code is safe; bulk deletion/migration is not justified and can lose user data. | No DB mutation. Treat the old key as unconsumed inert data. Test callback rejection after route removal. |
| `telegram_features.py` owns the guest-info handler; shared capability APIs live in `videl/utils/telegram_features.py`. | Deleting the guest module or shared utility indiscriminately could remove useful non-AI guest info or break ephemeral replies/Telegram capability detection. | Keep the guest-info handler without provider calls, retain the separate shared utility, and run connected-DM/ephemeral and guest regressions. |
| `redaction.py`, `httpx`, audit and group-manager stores are shared. | Removing them as “AI dependencies” would weaken security or break unrelated features. | Keep shared modules/dependencies; remove only provider-specific config labels. |
| One-group connection model. | A true multi-group overview/select flow is a persistence/consumer/API migration, not just UI work. | Respect and disclose current limit; no schema expansion in this incremental pass. |
| Wishlist includes features with no identified backing implementation (URL whitelists, generic custom rules/scheduling, some mention/duplicate controls). | UI could falsely promise protection or require a parallel engine/schema. | Inventory capabilities first; implement only within existing stores/APIs and report unsupported items honestly. |
| Broad performance/reliability/security scope. | There are existing leases, single-instance protections, task guards, retries and process lifecycle behavior that should not be weakened. | Audit those mechanisms and add focused tests; do not change them absent a measured defect. No production performance claims without profiling/live validation. |
| External validation is unavailable in this source-only pass. | Telegram Bot API, production MongoDB, Vercel deployment and browser/device behavior cannot be inferred from mocks. | Label all automated tests as offline/mocked and leave live/staging/browser checks outstanding. |

## 6. Incremental implementation plan

1. **Stage A — AI removal (implemented; focused offline validation passed):** unregister six commands; remove Gemini guest generation while preserving guest info and the separate capability-helper module; strip the settings toggle and associated callbacks/help; remove provider config/environment examples and Gemini helper; update generated command guide/reference; keep FAQ/rules, safety/moderation, shared redaction, HTTPX, group data and shared helpers. Tests prove the removed commands fail registration/dispatch, no generated/menu entries remain, and no runtime provider import/config remains. No data deletion.
2. **Stage B — command catalog and menus:** rerun and validate the inventory; inspect permission/filter details command by command; map current commands to the requested categories; retain established aliases; correct descriptions/context menus where provably wrong; test BotCommand scopes/counts, handler coverage and generated webapp/docs parity. This is a broad change and should be separate from AI removal.
3. **Stage C — category navigation/settings:** refine existing settings pages/search/status/back/home; reuse current editors, rights checks and group storage. No new generic automation engine or multi-group migration in this stage.
4. **Stage D — DM dashboard and group UX:** incrementally add available overview/report/task/permission links and safe group back/home/status behavior using existing interaction engine and connected auth; identify unsupported capability gaps rather than displaying inert controls.
5. **Stage E — engineering/security/performance:** inventory task lifecycle, worker/retry/lease/single-instance behavior, webapp auth/routes, shared DB access, duplicate handlers/imports and dependency use. Fix only high-confidence defects with targeted tests and measured benefit.
6. **Stage F — documentation and final verification:** update README, command/settings/architecture/environment/dependency/deployment/security docs only after verified changes; preserve historical backlog; run AI absence/registration tests, inventory consistency, settings/moderation/auth/connected-DM/database tests, webapp typecheck/tests, Python compile/import checks and `git diff --check`. Review full diff, commit and push only to this branch, then verify PR #5 remains open/unmerged.

## 7. Initial verification and known limits

- Source inspection and repository-wide text searches found the dependencies listed above; no source, configuration, database, test or generated UI files have been modified for feature removal yet.
- Command discovery executed locally and returned 215 unique names, 28 legacy modules in `ALL_MODULES`, and the category/context counts above. Discovery imports warn that `API_HASH`, `BOT_TOKEN`, `STRING_SESSION` and `MONGO_DB_URL` are not set in this sandbox; no secret values were read or printed.
- Do not treat the CSV's static permission evidence as a completed manual audit of 215 handlers. Handler-by-handler authorization and actual BotCommand/webapp behavior remain part of the implementation/test stages.
- No live Telegram, production MongoDB, staging, Vercel deployment, browser or device validation was performed.

## Stage A implementation record (2026-11-01)

- Removed all six Gemini-dependent group commands and their handlers by removing `videl/plugins/guardian.py` from the command manifest/plugin list and deleting the module. All six had provider calls; no non-AI handler lived in that module. Ordinary `/faq`, `/setfaq`, `/rules`, `/safetystats`, `/rulefeedback`, and the independent anti-spam, raid, CAPTCHA, lock, reports, moderation, and join-management implementations remain registered.
- Removed the guest-mention text-generation path. The guest response now identifies Videl as a utility/group-management bot and accurately states its limited context. No guest text is sent to an external model. The separate `videl/utils/telegram_features.py` capability helpers and shared HTTPX dependency are untouched.
- Removed the Gemini group-settings toggle, callback grammar/allowlist path, UI copy, key configuration and `.env.example` entries, provider helper, Gemini-specific secret label, webapp command-guide usage overrides, and generated command rows. Existing `gemini_guardian_enabled` values in group settings are not read, migrated, or deleted; a regression test confirms the old value remains inert and untouched.
- Removed provider-only tests (`test_gemini_provider.py`, `test_gemini_stream.py`, `test_guardian_assistance.py`) and replaced the guest, settings callback and command registry assertions with non-AI/removed-command regressions. Shared `test_redaction.py` and normal FAQ tests remain.
- Regenerated `docs/COMMAND_REFERENCE.md` and `webapp/src/lib/commands.ts`. The registry now reports 209 names (down from 215); current categories are manage 111, music 45, tools 27, owner 26. The curated Telegram BotCommand menus remain at 34 public and 45 owner entries, both below Telegram's 100-command-per-scope ceiling, and all menu entries remain registered.
- The inventory CSV intentionally retains all 215 baseline rows for traceability; the six retired entries have explicit removal status. It is a source snapshot, not a claim that those six commands remain active.

Focused offline validation: guest flow 2 passed; Telegram settings revision 6 passed; command registry audit 11 passed (including every removed command rejected by the router, handler/source consistency, generated webapp-guide parity, and menu-name validity); connected settings dashboard 16 passed; settings revision 14 passed; plugin/help tests 19 passed. Python compilation passed for the changed Python files. These tests use mocks and do not validate live Telegram, production MongoDB, staging, Vercel, browser, or device behavior. `todo.md` historical issue notes are retained and explicitly superseded; they are not current setup or capability documentation.

**Next stage:** validate and reconcile all 209 active command registrations, permissions, contexts, descriptions, aliases, and dependencies against the requested taxonomy before changing command categories or menu behavior. Keep the remaining settings/dashboard redesign, broad code cleanup, performance work, webapp security review, and live validations open; none is complete by this Stage A slice.


## Current status (2026-10-19)

At the user’s explicit direction to preserve Gemini/GuardianAI/FAQAssist, the opt-in Gemini provider, Guardian command module, provider tests, configuration and redaction entries, settings callback, and route registration are restored. The six commands are present in current command references and inventory. Historical Stage A removal analysis above remains as a record of the earlier change; it is not the current runtime state. The provider is offline/mock-tested only, remains opt-in and advisory, and has not been verified against Google or a deployed bot. Guest mention generation remains disabled.

## Current status (2026-10-19)

At the user's explicit direction to preserve Gemini/GuardianAI/FAQAssist, the opt-in Gemini provider, Guardian command module, provider tests, configuration and redaction entries, settings callback, and route registration are restored. The six commands are present in the current command registry and generated references. This supersedes the earlier Stage A runtime-removal status while preserving its historical rationale. Provider operation has only mock/offline test coverage; no live API credentials or production behavior were tested. Guest mention generation remains disabled.
