# Webapp and admin-dashboard release checklist

Use this for releases that change the Next.js panel, Flask routes, Mongo-backed group settings, or authorization. A passing build is necessary, but does not prove that Telegram permissions, the live backend, or a production deployment work.

## 1. Verify the exact candidate

- [ ] Record the branch and full commit SHA being reviewed.
- [ ] CI passes: Python compile and offline tests; Python and npm advisory audits; webapp typecheck, tests, production build, and public-bundle secret scan.
- [ ] The Vercel preview reports **Ready** and its source SHA matches the candidate. Keep preview and production URLs distinct; do not treat a production URL returning HTTP 200 as proof that the preview deployed.
- [ ] Run the available browser smoke suite against the preview when a Chromium runner is available. It mocks Telegram and backend requests; separately plan a permissioned live smoke test for a canary group.

## 2. Check compatibility and configuration

- [ ] Compare the frontend/API contract with the backend revision. The Render backend currently deploys from `main`; a branch preview may intentionally be ahead. Confirm whether the change is backward-compatible before enabling the preview against the live backend.
- [ ] Confirm required environment variables exist in the correct server-side host and environment. `WEBAPP_SECRET` must match between Vercel and Render; provider and database credentials must never use `NEXT_PUBLIC_*`.
- [ ] If database fields or indexes change, deploy additive/backward-compatible changes first. Verify index creation and migration status; defer destructive cleanup until old code is no longer serving traffic.
- [ ] Confirm new admin functionality is disabled by default or protected by a tested feature gate until its required backend, permissions and data are ready.

## 3. Validate operations and rollback

- [ ] Backend `/health` is reachable and reports the expected revision, bot state and database status. A live web process alone is not proof that Telegram polling or voice is available.
- [ ] Verify group actions in a dedicated test group with current admin rights. Confirm the UI disables unsupported actions and the backend rechecks permissions at mutation time.
- [ ] Verify backup/restore previews and a recovery point before any configuration migration or broad settings rollout.
- [ ] Identify the previous Ready Vercel deployment and previous healthy Render deploy. Confirm the rollback operation and owner are known before release; do not rely on “redeploy latest” if latest is the failing candidate.
- [ ] Stage risky behavior behind a group-level feature flag or canary. Expand only after the health checks and audit trail look correct.

## 4. Promote and observe

- [ ] Promote only after preview review and required approval. Keep the preview URL available for comparison.
- [ ] After promotion, verify the production deployment SHA, backend compatibility, `/health`, sign-in, and one harmless read in the admin panel.
- [ ] Review deployment events for build failures, stale-commit serving, database errors, authorization denials and repeated Telegram connection failures.
- [ ] If health or compatibility regresses, disable the feature flag or roll back to the recorded healthy deployment, then preserve logs and audit evidence for diagnosis.

## Release record

| Field | Value |
|---|---|
| Candidate branch / SHA | |
| Vercel preview deployment / state | |
| Render backend revision / state | |
| Schema or index changes | |
| Feature flags / canary groups | |
| Previous healthy deployment(s) | |
| Smoke-test owner / result | |
| Promotion decision / time | |
