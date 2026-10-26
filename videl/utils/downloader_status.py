"""Safe, secret-free summary of configured media downloader providers."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

DEFAULT_SHRUTI_URL = "https://api.shrutibots.in"


def downloader_status(environ=None) -> dict:
    """Return configuration readiness without exposing credentials or probing APIs."""
    env = os.environ if environ is None else environ
    url = (env.get("YT_API_URL") or DEFAULT_SHRUTI_URL).strip().rstrip("/")
    key_set = bool((env.get("YT_API_KEY") or "").strip())
    try:
        parsed = urlsplit(url)
        valid_url = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid_url = False

    shruti_state = "configured" if key_set and valid_url else (
        "needs_api_key" if valid_url else "invalid_url"
    )
    return {
        "primary": "shruti",
        "shruti": {"state": shruti_state, "configured": key_set and valid_url},
        "fallbacks": ["eldian", "local_yt_dlp"],
    }
