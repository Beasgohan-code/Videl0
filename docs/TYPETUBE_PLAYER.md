# TypeTube source in Videl Music Studio

**Status:** implemented and offline-tested; live TypeTube connectivity and browser audio are not verified.
**Boundary:** this adds an optional source to Videl's existing personal browser player. It is not Telegram voice-chat playback, a synchronized room, or a Playeon code/asset port.

## How it works

- Music Studio has separate **Videl** and **TypeTube** search-source buttons. Videl remains the default and its existing search/download route is unchanged.
- TypeTube search and resolve use owner-protected same-origin Next.js routes. The TypeTube SDK is imported only by the server-side adapter; browser code never receives the optional API key or TAP connection details.
- Search results are normalized to a bounded metadata schema. Resolve accepts only an 11-character YouTube ID and returns a media URL only when it is HTTPS on `googlevideo.com` or a subdomain. Other schemes, hosts, credentials in URLs, and malformed values are refused.
- The existing single `<audio>` element plays the resolved stream in the browser. Every track change pauses and unloads the old source before asynchronous resolution, so a failed TypeTube lookup cannot leave the prior track available under new metadata. TypeTube favorites/history are provider-namespaced so they do not collide with Videl entries for the same YouTube ID. Async resolution is protected by the existing latest-request gate.
- TypeTube streams are external and may expire, be region-restricted, or be unavailable; switching back to Videl remains available. Browser playback is still separate from Telegram `/play`.

## Server configuration

The Next.js Node runtime uses the TypeTube public cluster by default (`sg.clusters.typetube.xyz:8443`). Optional server-only settings:

- `TYPETUBE_ENABLED=0` makes the protected TypeTube API return an unavailable response; the source button remains visible in the Studio.
- `TYPETUBE_HOST` may set a DNS host with an optional numeric port. Request parameters cannot choose or override it.
- `TYPETUBE_API_KEY` is optional and must remain private; it is never returned to the browser.

The deployed Vercel Node runtime must permit the TypeTube TAP TCP connection (default port 8443). This sandbox could not make that live connection and no deployed configuration was inspected. If egress is blocked, TypeTube returns a bounded unavailable response; this does not affect Videl search/playback.

## License and attribution

The Videl integration uses the `typetube` npm package pinned at `1.1.4`; its published package declares MIT and includes the TypeTube copyright/license notice. No TypeTube SDK implementation or Playeon application source/assets were copied into Videl. TypeTube upstream: https://github.com/playeon/typetube. Playeon's separate repository license is personal/non-commercial with attribution requirements; this Videl adaptation remains independently implemented and does not port the Playeon app. Usage must also respect applicable provider terms and rights; those were not reviewed or live-tested here.

## Offline validation

`webapp/tests/typetube-source.test.ts` covers metadata normalization (including dropping stream fields from search results and bounding unusual durations), ID and stream-host validation, owner-only search, bounded result counts, rejection of unsafe streams, and valid stream response shaping. `webapp/scripts/check-public-bundle.mjs` also rejects the server-only API key/host markers and TypeTube cluster/TAP client identifiers in public build assets. The full web test suite and typecheck/build passed during implementation. No live TypeTube handshake, actual CDN audio playback, browser/device test, staging test, or production check is claimed.
