"""Reusable secret redaction for diagnostics and logs."""
from __future__ import annotations

import os
import re
from logging import Filter, LogRecord
from typing import Any

import config

_SECRET_FIELDS = (
    "BOT_TOKEN",
    "WEBAPP_SECRET",
    "MONGO_DB_URL",
    "STRING_SESSION",
    "ELDIAN_API_KEY",
    "INTERNAL_SECRET",
    "API_HASH",
    "GEMINI_API_KEY",
    "ANALYTICS_SALT",
)

_PATTERNS = (
    (re.compile(r"(?i)(mongodb(?:\+srv)?://)[^/@\s]+:[^/@\s]+@"), r"\1<redacted>@"),
    (re.compile(r"(?i)\b(bot\d{5,}:)[A-Za-z0-9_-]{12,}"), r"\1<redacted>"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/-]+=*"), r"\1<redacted>"),
    (re.compile(r"(?i)([?&](?:token|secret|session|api[_-]?key)=)[^&\s]+"), r"\1<redacted>"),
)


def redact_secrets(value: Any, *, limit: int = 2000) -> str:
    """Remove configured credentials and common credential-bearing URL forms."""
    text = str(value or "")
    secrets = {
        str(candidate or "").strip()
        for name in _SECRET_FIELDS
        for candidate in (os.getenv(name), getattr(config, name, ""))
    }
    for secret in sorted((item for item in secrets if len(item) >= 6), key=len, reverse=True):
        text = text.replace(secret, "<redacted>")
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    # Exception messages occasionally include opaque session/authorization
    # values without a recognizable key; preserve short diagnostic wording.
    text = re.sub(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{40,}(?![A-Za-z0-9])", "<redacted>", text)
    return text[: max(0, limit)]


class RedactingFilter(Filter):
    """Sanitize the rendered message before any handler persists or emits it."""

    def filter(self, record: LogRecord) -> bool:
        try:
            record.msg = redact_secrets(record.getMessage())
        except Exception:
            record.msg = "<log message redacted>"
        record.args = ()
        return True
