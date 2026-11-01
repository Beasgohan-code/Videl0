"""Conservative lookalike-name matching for a manual moderator alert only."""
from __future__ import annotations

from difflib import SequenceMatcher
import re


def _key(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())[:80]


def _similar(left: str, right: str) -> float:
    a, b = _key(left), _key(right)
    if len(a) < 5 or len(b) < 5:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def lookalike(member, administrators, *, threshold: float = 0.88) -> dict | None:
    """Return a coarse admin-name match; callers must not take action on it."""
    threshold = max(0.85, min(float(threshold), 0.98))
    member_name = " ".join(filter(None, [getattr(member, "first_name", ""), getattr(member, "last_name", "")]))
    member_username = getattr(member, "username", None)
    best = None
    for admin in administrators:
        if int(getattr(admin, "id", 0) or 0) == int(getattr(member, "id", 0) or 0):
            continue
        admin_name = " ".join(filter(None, [getattr(admin, "first_name", ""), getattr(admin, "last_name", "")]))
        admin_username = getattr(admin, "username", None)
        candidates = [(_similar(member_name, admin_name), "display name", admin_name)]
        if member_username and admin_username:
            candidates.append((_similar(member_username, admin_username), "username", "@" + str(admin_username)[:64]))
        for score, field, label in candidates:
            if score >= threshold and (best is None or score > best["score"]):
                best = {"score": score, "field": field, "reference": label[:80]}
    if best is None:
        return None
    return {"field": best["field"], "reference": best["reference"], "confidence": round(best["score"], 2)}
