"""Warning counting, decay and the escalation ladder.

Two surfaces hand out warnings — ``/warn`` in the bot and the report triage
button in the owner panel — and both must reach the same verdict for the same
member. That verdict lives here, once.

Two rules are easy to get wrong:

* **Decay.** A warning is a signal about now, not a permanent criminal record.
  With ``decay_days`` set, only reasons newer than the window count. Rows
  written before reasons carried timestamps are counted as active: we cannot
  prove they are old, so we do not pretend they expired.
* **The ladder.** Reaching the limit the first time should not always mean the
  harshest action. ``ladder`` names the actions in order — the first time the
  limit is reached applies ``ladder[0]``, the next ``ladder[1]``, and the last
  action repeats. An empty ladder keeps the single ``action`` behaviour every
  existing group already has.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Actions the ladder may contain, easiest first. "none" is intentionally absent:
# a rung that does nothing is indistinguishable from a broken ladder.
LADDER_ACTIONS = ("mute", "kick", "ban")
MAX_LADDER = len(LADDER_ACTIONS)
DECAY_RANGE = (0, 365)


def parse_ts(value) -> datetime | None:
    """Parse a stored ISO timestamp, tolerating a trailing ``Z`` and no zone."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def warning_entries(document) -> list[dict]:
    """Normalise the stored reasons list: ``{"reason", "ts"}`` (or legacy text)."""
    entries = []
    for item in (document or {}).get("reasons") or []:
        if isinstance(item, dict):
            entries.append({"reason": str(item.get("reason") or ""), "ts": parse_ts(item.get("ts"))})
        else:
            text = str(item or "")
            if text:
                entries.append({"reason": text, "ts": None})
    return entries


def case_file(document, decay_days: int = 0, now: datetime | None = None) -> dict:
    """Every warning on record, with whether it still counts.

    Returns ``{"count", "total", "decayed", "expires_at", "entries"}``. ``total``
    is what is stored, ``count`` is what a fresh limit check would use, and
    ``expires_at`` is the moment the active count would drop by one. Each entry
    carries ``{reason, ts, active}``, so a moderator can see the whole history
    rather than only the part still counting.
    """
    moment = now or datetime.now(timezone.utc)
    entries = warning_entries(document)
    try:
        days = int(decay_days or 0)
    except (TypeError, ValueError):
        days = 0
    days = max(DECAY_RANGE[0], min(days, DECAY_RANGE[1]))
    cut = moment - timedelta(days=days) if days else None
    annotated = [
        {**entry, "active": cut is None or entry["ts"] is None or entry["ts"] >= cut}
        for entry in entries
    ]
    active = [entry for entry in annotated if entry["active"]]
    # The next lapse is the oldest active warning that actually has a timestamp.
    stamps = sorted(entry["ts"] for entry in active if entry["ts"] is not None)
    expires_at = stamps[0] + timedelta(days=days) if (stamps and days) else None
    return {
        "count": len(active),
        "total": len(entries),
        "decayed": len(entries) - len(active),
        "expires_at": expires_at,
        "entries": annotated,
    }


def active_warnings(document, decay_days: int = 0, now: datetime | None = None) -> dict:
    """How many warnings still count, and when the next one lapses.

    The same shape as :func:`case_file`, with ``entries`` narrowed to the ones
    that still count — the verdict a limit check actually uses.
    """
    state = case_file(document, decay_days, now)
    return {**state, "entries": [entry for entry in state["entries"] if entry["active"]]}


def ladder_action(escalation, stage: int) -> str:
    """The action for this rung. ``stage`` is 0 for the first time the limit is hit."""
    escalation = escalation if isinstance(escalation, dict) else {}
    ladder = [action for action in (escalation.get("ladder") or []) if action in LADDER_ACTIONS]
    try:
        index = max(0, int(stage))
    except (TypeError, ValueError):
        index = 0
    if ladder:
        return ladder[min(index, len(ladder) - 1)]
    action = escalation.get("action")
    return action if action in ("ban", "mute", "kick", "none") else "ban"


def ladder_summary(escalation) -> list[str]:
    """The rungs that will actually be used, for the panel and the bot reply."""
    escalation = escalation if isinstance(escalation, dict) else {}
    ladder = [action for action in (escalation.get("ladder") or []) if action in LADDER_ACTIONS]
    if ladder:
        return ladder
    action = escalation.get("action")
    return [action] if action in ("ban", "mute", "kick") else []


def next_stage(document, limit: int, decay_days: int = 0, now: datetime | None = None) -> dict:
    """Decide what one more warning does for this member.

    Returns ``{"count", "limit", "reached", "stage", "action", "total",
    "decayed"}`` with ``stage`` counting how many times the limit has already
    been crossed (kept in the stored document as ``stages``).
    """
    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 3
    state = active_warnings(document, decay_days, now)
    count = state["count"] + 1
    stored_stage = int((document or {}).get("stages") or 0)
    if state["total"] and state["count"] == 0:
        # Every warning lapsed. The record is empty, so the ladder starts over:
        # a member should not resume at a rung earned years ago, one step at a
        # time. This is the whole point of a decay window.
        stored_stage = 0
    reached = count >= limit
    return {
        "count": count,
        "limit": limit,
        "reached": reached,
        "stage": stored_stage if reached else max(0, stored_stage - 1),
        "next_stage": stored_stage + 1 if reached else stored_stage,
        "total": state["total"] + 1,
        "decayed": state["decayed"],
        "expires_at": state["expires_at"],
    }
