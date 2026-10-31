# Security model and release checklist

This document records Videl's intended trust boundaries. It is a review aid, not a claim that every route or deployment has been independently audited.

## Principals and trust boundaries

- **Telegram group members** may use only commands explicitly exposed to members. Group settings mutations require a fresh Telegram lookup proving the actor is a current group administrator; saved bot sudo access does not substitute for Telegram admin status.
- **Temporary group roles** (such as the music DJ) are scoped to their group and must be revalidated against current membership. They do not grant administrator or owner powers.
- **Webapp guests** may use public Studio pages and endpoints only. Owner APIs require a server-verified, signed, expiring owner cookie; player/arcade APIs use a separate Telegram-verified player session. Client-side state is presentation only and never authorizes a server action.
- **Telegram, the bot backend, MongoDB and the webapp host** are separate trust zones. Browser code calls relative webapp APIs; the server-side webapp proxies authenticated requests to the backend. Internal service credentials are never sent to the browser.
- **Stored group settings and queued payloads** are untrusted input at read boundaries. Validate shapes, lengths, identifiers and allowed values before using them in commands, callbacks, exports or database updates.

## Security invariants

1. Check authorization on the server at every command/callback/API mutation; hide controls in the UI only as a secondary usability measure.
2. Re-check current Telegram group membership/admin status for sensitive actions. Never let bot sudo, a stale panel, a cached role or a caller-supplied ID bypass group permissions.
3. Keep owner-only fleet, deployment, backup and recording controls out of group-admin surfaces.
4. Reject cross-site state-changing web requests and use HttpOnly, Secure, appropriately scoped cookies. Do not trust `initDataUnsafe`, browser storage or request-body role claims.
5. Bound request bodies, settings arrays, callback data, exports, in-memory state and retry loops. Treat timeouts as unconfirmed, not success.
6. Redact tokens, internal URLs, message contents and unnecessary member identifiers from logs, diagnostics and exports.
7. Preserve audit attribution for admin-driven settings and actions; audit failure must not silently grant permission or reverse an already-confirmed Telegram effect.

## Deployment secrets and session handling

- `WEBAPP_SECRET` must be identical only between the webapp and backend components that verify its signatures, unique in production, and absent from browser bundles and logs.
- Telegram bot/assistant credentials and MongoDB connection strings remain server-side. Never copy them into Vercel public environment variables or client-prefixed build variables.
- Owner and player web sessions are distinct. Rotate the signing secret to invalidate outstanding signed sessions; deploy coordinated rotations so healthy logins are not left unable to validate sessions.
- Production cookies require HTTPS. Cross-site embedded Telegram contexts need the partitioned cookie variant; browser and embedded cookies must both be cleared on logout.

## Phase 1 review checklist

- Run the API route authorization inventory and unauthenticated route tests.
- Check every new callback for message/chat binding, actor authorization, stale-state handling and bounded input.
- Run `pip-audit` and `npm audit`, publish CycloneDX dependency SBOMs as CI artifacts, then typecheck, run unit tests and build the webapp with synthetic secret sentinels before scanning public assets.
- Run backend compile and offline permission tests with the pinned Telegram client installed.
- Review changed workflows, dependency lockfiles, environment examples and telemetry for secrets or unsafe defaults.
- For any destructive group-wide action, require a clear scope preview, fresh authorization and auditable confirmation.

## Dashboard release checklist

For the webapp preview-to-production sequence, backend/schema compatibility, feature gating, health checks and rollback record, use the [webapp release checklist](WEBAPP_RELEASE_CHECKLIST.md). It is a go/no-go aid, not evidence that a deployment has passed.
