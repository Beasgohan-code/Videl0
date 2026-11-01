# Stage C — command-by-command improvement plan

**Status:** In progress on `arena/042d6599-videl0` (PR #5 remains open).
**Inventory source:** the running registry assembled by `videl.utils.command_catalog.commands()`, reconciled with the declarative manifest in `videl.app.routes.COMMANDS`. Refresh the historical inventory with `PYTHONPATH=. ./.venv/bin/python scripts/build_command_inventory.py`.

## Runtime baseline (2026-11-01)

- **209 live commands:** `manage=111`, `music=45`, `tools=27`, `owner=26`.
- Runtime catalog context hints (after Batch 1 handler-boundary corrections): `group=139`, `chat=42`, `private=25`, `group_private=3`. These are discovery hints, not authorization guarantees; each handler's actual policy and Telegram checks remain authoritative.
- **126 declarative manifest entries**; the other live registrations are legacy handlers. The inventory calls out declarative policy/rights/block settings when present and links legacy checks to their handler/decorator evidence rather than inventing an equivalent policy.
- The reconciled CSV retains **215 rows**: 209 live plus six Stage A-retired historical rows. Retired AI-related rows remain marked historical only; no AI/Gemini/GuardianAI/FAQAssist command is registered or planned for restoration.
- `docs/COMMAND_INVENTORY_AUDIT.csv` is the complete per-command ledger. Its runtime fields include live/removed status, current discovery category and context hint, summary, handler, manifest authorization/block policy and Telegram rights, and public/owner BotCommand-menu scope.

## Prioritized batches

| Priority | Batch | Registry scope | Status |
|---|---|---|---|
| 0 | Inventory, registry parity and baseline verification | All 209 live commands + six historical removals | Inventory refreshed; add automated parity checks and keep it synchronized during each batch. |
| 1 | General utilities, help and command discovery | All 27 live `tools` commands: `about`, `afk`, `afklist`, `back`, `commands`, `copy`, `feedback`, `forget`, `help`, `id`, `inbox`, `kang`, `mydata`, `ping`, `poll`, `pollstop`, `preferences`, `quiz`, `react`, `remind`, `reminders`, `repo`, `start`, `stats`, `stickerid`, `sudohelp`, `whois` | Complete for this batch (source audit + offline validation); findings and command ledger are in `docs/STAGE_C_BATCH_1_AUDIT.md`. Improvements: private reminder controls and DB error recovery; same-process per-sender admission serialization; atomic AFK notice cooldown and paginated/scope-disclosed `/afklist`; fail-closed `/inbox`; accurate `/whois` API errors; corrected private-only catalog contexts. Residual limitations: cross-instance reminder cap and at-most-once delivery crash recovery; full repository suite and live validation remain open. |
| 2 | Music, playback, queue and playlists | All 45 live `music` commands | Pending. Preserve player state, DJ/admin/owner boundaries, queue identity and callback expiry/replay behavior. |
| 3 | Group management, moderation and member tools | Remaining `manage` commands for moderation, member lifecycle, admin actions and group settings | Pending. Recheck current Telegram admin status/rights for protected writes; preserve audit and appeal boundaries. |
| 4 | Filters, protection, locks and automation | Remaining `manage` commands for filters, locks, safety, anti-spam and scheduled automation | Pending. Exercise callbacks, actor/target scope, duplicate/race behavior, and storage/API failures. |
| 5 | Analytics, broadcasts, downloads and owner tools | Remaining `manage`/`owner` commands in these domains | Pending. Verify privacy, recipient selection, current owner/sudo scope, rate/size bounds and delivery uncertainty. |
| 6 | Settings, connected-group, plugins and other remaining commands | Every live command not covered above, including connected administration and plugin controls | Pending. Preserve connected target/group authorization, actor/target binding, snapshot/current-auth and safe write invariants. |
| 7 | Cross-command final audit | All 209 live commands, menu aliases, callbacks and legacy handlers | Pending. Check duplicates/dead code, docs/webapp parity, regressions, performance and unresolved findings; document any residual risk. |

Batches are assigned by actual live registration, not by historical category labels. If a command spans areas, it is audited in its primary batch and cross-checked in the final audit. No command is silently omitted because it is legacy, absent from a menu, or difficult to test.

## Batch acceptance criteria

1. Record each command's handler, aliases/arguments, contexts, role/rights checks, side effects, callback surfaces and known limitations against source and tests.
2. Add or update tests before behavioral edits. Cover valid/invalid inputs, relevant roles/contexts, callback ownership/staleness/replay, repeated requests and database/API failure behavior.
3. Improve only genuine UX, reliability or security defects; preserve established compatibility unless a safety issue requires a documented change. Do not add redundant commands.
4. Synchronize `docs/COMMAND_REFERENCE.md`, `webapp/src/lib/commands.ts`, the inventory, `todo.md`, tests and developer documentation where applicable.
5. Run focused tests and the broadest feasible Python/webapp checks. Report offline/mock checks separately from any live Telegram, database, staging or device verification.
6. Commit and push each tested meaningful batch only to `arena/042d6599-videl0`; verify branch/remote/PR and leave PR #5 open and unmerged.

## Batch 1 audit checklist

For each of the 27 `tools` registrations, inspect the live handler and all reachable callbacks/utilities; record context and access behavior, inputs/aliases, storage/API effects, failure handling, help/menu discoverability, and existing tests. Include the routed tools (`help`, `commands`, polls/quizzes, reminders/preferences, data export/feedback, AFK, identifiers/profile/health/source/stickers) and legacy API-tool handlers (`copy`, `pollstop`, `react`). Do not treat a category or menu entry as authorization.
