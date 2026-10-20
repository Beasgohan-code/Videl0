# Eldian Music API downloader integration

The downloader implementation in `app/youtube.py` is vendored from
[Eldian-Network/eldian-music-api](https://github.com/Eldian-Network/eldian-music-api)
(MIT; upstream copyright and license are preserved in `LICENSE`). Videl uses
its retry-safe yt-dlp extraction for audio fallback and speaks the upstream
`POST /v1/track/by-video-id` API contract when `ELDIAN_API_URL` and
`ELDIAN_API_KEY` are configured. The separate Eldian Telegram bot and API-key
management bot are not run here; Videl's existing owner controls and MongoDB
remain the single control plane.

Videl-specific changes: default proxy/cookie example files are disabled rather
than passed as fake credentials; settings are mapped from Videl's existing
`YTDLP_COOKIES`, `PROXY_URL`, and `PROXY_LIST` environment configuration.
