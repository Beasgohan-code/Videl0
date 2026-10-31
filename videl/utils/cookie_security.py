"""Strict opt-in resolution for deployment-mounted YouTube cookie credentials."""
from __future__ import annotations

import os
from pathlib import Path


_COOKIE_ENV_KEYS = (
    "YTDLP_COOKIES",
    "YT_COOKIES_FILE",
    "COOKIES_PATH",
    "YOUTUBE_COOKIES_FILE",
)
_AUTH_COOKIE_NAMES = {
    "SID", "HSID", "SSID", "LOGIN_INFO", "SAPISID", "APISID",
    "__Secure-1PSID", "__Secure-3PSID", "__Secure-1PAPISID", "__Secure-3PAPISID",
}
_MAX_COOKIE_FILE_BYTES = 5 * 1024 * 1024
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _has_youtube_auth_cookie(contents: str) -> bool:
    """Accept only Netscape cookie rows for Google/YouTube auth-cookie names."""
    for line in contents.splitlines():
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            continue
        domain, _include_subdomains, _path, _secure, _expiry, name, value = fields
        domain = domain.lstrip(".").lower()
        if (
            (domain == "youtube.com" or domain.endswith(".youtube.com")
             or domain == "google.com" or domain.endswith(".google.com"))
            and name in _AUTH_COOKIE_NAMES
            and value.strip()
        ):
            return True
    return False


def configured_cookie_path(environ=None) -> str | None:
    """Return a validated cookie jar only from an explicit absolute external path.

    Relative paths and paths resolving inside the checkout are rejected, even if
    explicitly set, so a leaked ``cookies.txt`` in the repository can never be
    silently used by a downloader.
    """
    env = os.environ if environ is None else environ
    for key in _COOKIE_ENV_KEYS:
        raw_path = str(env.get(key) or "").strip()
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(_REPOSITORY_ROOT)
            continue  # Do not allow cookie jars from the source tree or image.
        except ValueError:
            pass  # The resolved path is outside the repository.
        except (OSError, RuntimeError):
            continue
        try:
            if not resolved.is_file() or resolved.stat().st_size > _MAX_COOKIE_FILE_BYTES:
                continue
            contents = resolved.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _has_youtube_auth_cookie(contents):
            return str(resolved)
    return None
