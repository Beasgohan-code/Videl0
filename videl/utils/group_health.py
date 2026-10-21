"""Fleet health for the group manager's "needs attention" queue.

Every input is something the bot already stores or Telegram already answered:
availability from the last ``getChat``, administrator status from
``getChatMember``, explicit locks and counts from MongoDB. Nothing is guessed
and no score is invented for a group the bot has never read.

A score is a sorting aid, not a guarantee. Each deduction carries the reason,
and the UI shows the reasons rather than the number alone.
"""
from __future__ import annotations

from videl.utils.automation import normalize

MAX_SCORE = 100
ATTENTION_BELOW = 70


GUARD_KEYS = ("antispam", "captcha_enabled", "welcome_enabled", "goodbye_enabled")


def _explicit_guards(settings, explicit=None) -> int:
    """Switches the owner actually turned on — defaults do not count.

    ``settings`` is the effective view (defaults filled in). When the caller can
    also supply the raw stored values, those win: a group that never saved a
    setting is not protected just because welcomes default to on.
    """
    if isinstance(explicit, dict):
        return sum(1 for key, value in explicit.items()
                   if value is True and (key.startswith("lock_") or key in GUARD_KEYS))
    if not isinstance(settings, dict):
        return 0
    keys = [key for key in settings if key.startswith("lock_")] + list(GUARD_KEYS)
    return sum(1 for key in keys if settings.get(key) is True)


def evaluate(row: dict) -> dict:
    """Return ``{score, issues, attention}`` for one /internal/chats row."""
    issues: list[dict] = []
    score = MAX_SCORE

    def deduct(points: int, code: str, message: str) -> None:
        nonlocal score
        score -= points
        issues.append({"code": code, "message": message})

    if not row.get("available", False):
        deduct(45, "unreachable", "Telegram did not confirm this chat. The bot may have been removed.")
    elif row.get("bot_admin") is False:
        deduct(35, "not_admin", "The bot is not an administrator, so locks cannot be enforced.")

    settings = row.get("settings") or {}
    guards = _explicit_guards(settings, row.get("explicit"))
    members = row.get("members")
    if guards == 0:
        deduct(25, "no_protection", "No protection switch is on for this group.")
    elif guards <= 2 and isinstance(members, int) and members >= 500:
        deduct(10, "thin_protection", "Only a couple of locks are on in a large group.")

    if not settings.get("antispam") and isinstance(members, int) and members >= 200:
        deduct(8, "no_antispam", "Anti-flood is off in a group this size.")

    counts = row.get("counts") or {}
    if (counts.get("warns") or 0) and not (counts.get("blacklist") or 0):
        deduct(6, "warns_without_blacklist", "Members have warnings but no blacklisted word is configured.")

    pending_joins = counts.get("pending_joins") or 0
    if pending_joins:
        noun = "request" if pending_joins == 1 else "requests"
        deduct(5, "pending_joins", f"{pending_joins} join {noun} waiting for review in the inbox.")

    automation = normalize(row.get("automation"))
    if not automation["quiet_hours"]["enabled"] and isinstance(members, int) and members >= 1000:
        issues.append({
            "code": "no_quiet_hours",
            "message": "Quiet hours are off. Consider a window for a group this large.",
            "advisory": True,
        })

    score = max(0, min(score, MAX_SCORE))
    pending = int(pending_joins)
    # A waiting join request is work, not a health failure: the score stays
    # high, but the queue must still surface it so it is not forgotten.
    return {
        "score": score,
        "issues": issues,
        "attention": score < ATTENTION_BELOW or not row.get("available", False) or pending > 0,
    }


def summarize(rows) -> dict:
    """Fleet totals used by the panel header."""
    total = len(rows)
    attention = sum(1 for row in rows if (row.get("health") or {}).get("attention"))
    unreachable = sum(1 for row in rows if not row.get("available", False))
    protected = sum(1 for row in rows
                    if _explicit_guards(row.get("settings") or {}, row.get("explicit")) > 0)
    scores = [int((row.get("health") or {}).get("score", 0)) for row in rows]
    return {
        "total": total,
        "attention": attention,
        "unreachable": unreachable,
        "protected": protected,
        "average": round(sum(scores) / total) if total else 0,
    }
