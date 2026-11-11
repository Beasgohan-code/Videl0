# Playeon full-repository integration map

**Source snapshot:** `playeon/playeon`, commit `6ec6097`, cloned for review to `/tmp/playeon-full` (not included in Videl).
**Target decision:** integrate Playeon functionality into Videl while retaining Videl’s routes, Arcade, auth boundaries, Telegram group playback and independent implementation. This is a feature map, not a code/asset transplant.

## Feature domains and Videl disposition

| Playeon domain | Representative functionality in the cloned source | Videl status / integration approach |
|---|---|---|
| Personal 2D player | Track search, player controls, progress, queue, favorites/history, compact and immersive presentation | Videl Music Studio already provides its own browser player; Focus Player and queue reorder are independent adaptations. TypeTube is an optional source. Keep browser state distinct from Telegram playback. |
| Lyrics | LRCLIB search, plain/synchronized lyrics and playback-position highlighting | Videl Studio now has owner-protected, bounded LRCLIB lookup and time-synchronized lines; provider terms and live availability are not verified. |
| Saved listening sets | Queue/playback content organized for repeat listening | Videl now saves bounded named playlists in localStorage (20 playlists, 50 tracks each) and can append them to a bounded browser queue. Persistence is browser-local; no Playeon persistence code is used. |
| Shared rooms | Invite/join links, room identity, participants, shared queue/playback, live room protocol and synchronized controls | Not implemented. Requires a separate non-owner Telegram identity/session flow, room lifecycle and actor/host authorization, race-safe state, persistence/expiry, abuse limits and cross-client tests. Keep distinct from Telegram voice-chat groups. |
| 3D lounge | Three.js scene, stage/screen, seats, gestures, reactions, chat, diagnostics and performance tuning | Not implemented. Keep Videl Arcade and routes intact. Treat as a later opt-in feature only after the 2D room lifecycle works and mobile/WebView performance is validated. |
| Telegram bot playback and control | Room/playback commands, access lists, queue/media acquisition, bot room callbacks and helper services | Videl already has its own Telegram player, downloader, channel binding and both-bound control policy. Preserve those paths; do not transplant Playeon handlers or merge their authorization model. |
| Server and persistence | Telegram Mini App validation, signed room access, Mongo-backed room state and room protocol | Videl has separate owner web auth, bot API and Mongo persistence. Reuse established Videl primitives only after a dedicated threat model; never pass Playeon tokens or secrets through the browser. |
| Deployment and assets | Playeon-specific Next.js, bot, relay, Docker, Nginx and media services | Not portable as a bundle. No deployment files, runtime secrets, branding, fonts or media assets are copied into Videl. |

## Integration sequence

1. **Personal player completeness:** bounded browser-local named playlists (20 playlists, 50 tracks each), queue append, plus existing queue, history and favorites. Import/export is not included; persistence remains browser-local.
2. **Shared 2D room design:** documented in `docs/PLAYEON_SHARED_LISTENING_ROOMS_DESIGN.md`; establishes a player-session boundary, separate Mongo room model, host/member policy, bounded polling, expiry and playback intent. Pure policy helpers/tests, a Mongo store, internal player-actor backend routes, and player-authenticated Next proxy routes now exist (`videl/web_music_rooms.py`, `videl/listening_room_store.py`, `videl/api/listening_room_routes.py`, `/api/music/rooms/*`). The Studio UI, client polling/playback, and live DB/browser validation are not implemented.
3. **Shared 2D room implementation:** backend and proxy foundations are present, with tests still needed around mocked persistence/routes. Next add the Music Studio invite/join panel and bounded polling/reconciliation, then deterministic multi-client tests. Keep playback intent server-authoritative; add presence/chat/reactions only as separately reviewed capabilities.
4. **3D lounge:** decide only after shared 2D rooms are secure and tested; add a Videl-native route and progressively enhanced WebGL with explicit low-performance fallbacks. Do not replace Arcade.
5. **Cross-cutting verification:** auth, replay, stale callbacks, rate/storage limits, cleanup, browser/device and mobile-WebView behavior, accessibility, external provider terms, and deployment configuration. Live checks remain distinct from mocks.

## License and attribution

The cloned Playeon `LICENSE` is a custom personal/non-commercial attribution license, not a permissive OSI license. It requires unaltered attribution for copies, substantial portions or derived works and prohibits commercial/monetized use without prior written permission. This plan follows the user-selected integration approach by implementing Videl-native features rather than copying substantial upstream source or assets. If later work must use actual Playeon code/assets or a substantially derived implementation, stop and review license/attribution requirements before copying or deploying it.

## Validation scope

The clone was inspected at source-tree and documentation level. This is not a claim that Playeon was built, run, or security-audited. Videl live Telegram, browser-device, shared-room and provider behavior are not verified by this map.
