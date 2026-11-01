"""Safe per-group moderation reason templates (plain text, never HTML)."""
from __future__ import annotations

ACTIONS = ("warn", "ban", "tban", "kick", "mute", "tmute")
DEFAULTS = {
    "warn": "Please follow the group rules.",
    "ban": "Removed for violating the group rules.",
    "tban": "Temporarily removed for violating the group rules.",
    "kick": "Removed for violating the group rules.",
    "mute": "Muted for violating the group rules.",
    "tmute": "Temporarily muted for violating the group rules.",
}
MAX_LENGTH = 240


def normalize(raw) -> dict:
    result = dict(DEFAULTS)
    if isinstance(raw, dict):
        for name in ACTIONS:
            value = raw.get(name)
            if isinstance(value, str) and value.strip():
                result[name] = value.strip()[:MAX_LENGTH]
    return result


def render(template: str, member: str) -> str:
    """Expand only the documented member placeholder; preserve unknown braces."""
    return str(template).replace("{member}", str(member)[:80])[:MAX_LENGTH]


def select_reason(tokens, action: str, templates: dict, member: str, fallback: str) -> str:
    """Use `template` as the whole argument to request the saved action text."""
    if len(tokens) == 1 and tokens[0].casefold() == "template":
        return render(normalize(templates).get(action, fallback), member)
    reason = " ".join(tokens).strip()
    return reason[:MAX_LENGTH] if reason else fallback
