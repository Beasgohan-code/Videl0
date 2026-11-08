# Playeon repository review for Videl

**Review date:** 2026-11-06 (Asia/Kolkata)
**Purpose:** evaluate the full upstream repository as a product/design reference for Videl, not as a source to transplant.
**Reference inspected:** `playeon/playeon`, shallow clone at review time; web and bot source trees, package manifests, root/readme files, deployment files, and license. The clone is outside the Videl repository at `/tmp/playeon-reference` and is not part of Videl's deliverable.

## Executive decision

Use the repository broadly as a reference for product ideas and interaction patterns, but implement only Videl-native, evidence-backed adaptations. Do **not** copy or port Playeon source, assets, architecture, or a substantial portion of its implementation. Videl's existing Studio Music page remains its browser-local player; Telegram group voice playback remains separate. The already implemented Focus Player presentation mode is an independent adaptation for that existing page, not a synchronized Playeon room.

## What was reviewed

The inspected repository is materially broader than its 2D player screen. It includes:

- **Web client:** Next.js App Router app; home and room entry/join flows; room/session providers and actions; a 2D room player with participant lane, queue, lyrics, playback controls, tabs/sheets and live provider; a separate 3D lounge with scene/canvas, screen/stage, seating, chat, reactions, diagnostics, performance tuning and input/gesture helpers.
- **Web services:** Telegram initialization/authentication, room join/access/token helpers, Mongo persistence, lyrics route, media engine and room protocol/store/style utilities.
- **Telegram bot:** command registration and policies; playback and room commands; auth/authorized-user management; queue, media acquisition/download/cache/playlist and provider services; room callbacks, tokens, server and room lifecycle; stats, models and operational/dev commands.
- **Operations/deployment:** root and package manifests, environment examples, Docker Compose, deployment script, PM2 ecosystem config, and Nginx config.
- **License:** root `LICENSE` states personal, non-commercial use only and requires explicit attribution for copies, substantial portions, or derived works; commercial or monetized deployments require prior written permission. This is not a permissive open-source license.

This is a source-tree/product-structure review, not a claim that each upstream feature works, is secure, or is suitable for Videl. No upstream service was run and no Telegram/provider/live test was attempted.

## Applicability to Videl

| Upstream area | Videl evidence / boundary | Decision |
|---|---|---|
| 2D player presentation, track focus and compact controls | `webapp/src/components/studio/screens/Music.tsx` is already Videl's browser player and supports its own local controls. | Retain Videl components and styling; Focus Player is the independently built design adaptation. Use upstream only as a visual/product reference. |
| Synchronized room state, room tokens, presence, reactions, chat and multi-user queue | Videl Studio browser playback and Telegram voice queues are different systems; no approved shared-room protocol or matching backend is established. | Do not present browser playback as shared or Telegram playback. No room protocol, presence, or queue-sync port. Requires a separate product/security design and explicit approval. |
| Playeon's 3D lounge and scene | Videl has existing Studio and Arcade routes; user direction explicitly preserves them. 3D adds rendering, device and interaction complexity. | No route replacement or 3D port. Consider only if Videl requests a distinct, tested feature later. |
| Lyrics, media metadata and upstream provider integration | Videl has its own downloader and browser player, with distinct server and Telegram playback paths. | After an explicit user request, TypeTube was added as an optional, owner-gated browser-player source through its MIT-licensed SDK. It does not replace Videl's provider or Telegram playback. See `docs/TYPETUBE_PLAYER.md`; live TAP/CDN validation remains outstanding. No Playeon provider or app source was copied. |
| Telegram bot commands, auth and room control | Videl already has its own bot, authorization rules, actor/target checks and callback controls. Playeon's policy/room implementation is not evidence for Videl's threat model. | Do not port bot code or change Videl's authorization policy. Preserve the existing both-bound linked-channel rule and fresh target/source checks. |
| Deployment, env/config and persistence architecture | Videl has its own Render backend and Vercel webapp boundaries. Upstream deployment config is project-specific. | No deployment/config transplant and no new secrets/services. Preserve Videl's server-side secret boundaries and verify against Videl's own tests. |

## License and attribution handling

The Focus Player work is an independent implementation; no Playeon source code, image, icon, font, or other asset was copied into Videl. The review uses the upstream repository as a reference and records its identity and license here. If any Playeon-licensed material or substantial derived implementation is later proposed, stop for an explicit scope/license review first; retain the required unaltered attribution and copyright/license notice, and do not deploy it commercially or monetized without the rightsholder's prior written permission. The personal/non-commercial selection for this design adaptation does not convert the license into an open-source license or authorize wholesale reuse.

## Validation boundaries

This review does not validate browser rendering, device performance, Playeon or Videl live rooms, media provider availability, Telegram voice calls, staging, or production. Videl's Focus Player remains an offline/source-and-test validated presentation feature. It is not a synchronized lounge, and must not be described as one.
