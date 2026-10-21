"""The one writer for ``mgmt_chat_settings``, with an edit revision.

A group's configuration is edited from two places that are rarely open at the
same time: the web panel and Telegram commands. Two panels pointed at the same
group would otherwise overwrite each other silently — the last save wins and a
switch flips back with no explanation.

Every owner-facing write therefore advances an integer ``revision`` on the
document, and a panel sends back the revision it read alongside its change. A
stale revision is refused with the current one instead of being applied, so the
panel can show the truth and let the owner decide again.

Runtime state is written around this module on purpose: a protection-window
tick is not an owner edit and must not turn an open panel's next save into a
conflict.
"""
from __future__ import annotations

from videl.utils.db import get_db

COLLECTION = "mgmt_chat_settings"
MESSAGE = (
    "This group's settings were changed elsewhere after this page loaded. "
    "The latest values are shown; check them before saving again."
)


class SettingsConflict(Exception):
    """The document moved on since the caller read it."""

    def __init__(self, expected: int, revision: int):
        super().__init__(MESSAGE)
        self.expected = expected
        self.revision = revision


def _collection(db=None):
    database = db if db is not None else get_db()
    return None if database is None else database[COLLECTION]


def revision(chat_id, db=None) -> int:
    """Current revision; 0 for a group that has never been written."""
    collection = _collection(db)
    if collection is None:
        return 0
    try:
        document = collection.find_one({"chat_id": int(chat_id)}, {"revision": 1}) or {}
    except Exception:
        return 0
    try:
        return max(0, int(document.get("revision") or 0))
    except (TypeError, ValueError):
        return 0


def _guard(chat_id, expected):
    """A filter that only matches while the document is still at ``expected``."""
    if expected == 0:
        # Documents written before revisions existed have no field at all;
        # treating "missing" as zero avoids inserting a second document.
        return {"chat_id": chat_id, "$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
    return {"chat_id": chat_id, "revision": expected}


def check(chat_id, expected, db=None) -> int:
    """Raise SettingsConflict unless the document is still at ``expected``."""
    if expected is None:
        return revision(chat_id, db)
    current = revision(chat_id, db)
    if current != expected:
        raise SettingsConflict(expected, current)
    return current


def write(chat_id, values, expected=None, db=None) -> int:
    """Apply ``values`` atomically and return the new revision.

    ``expected=None`` keeps the historic behaviour for bot-side callers that
    do not track revisions, but still advances the counter so a panel that is
    open elsewhere notices on its next write.
    """
    chat_id = int(chat_id)
    collection = _collection(db)
    if collection is None:
        raise RuntimeError("MongoDB is not connected")
    values = dict(values or {})
    # The counter belongs to this module; a caller cannot set it as a setting.
    values.pop("revision", None)
    update = {"$inc": {"revision": 1}}
    if values:
        update["$set"] = values
    if expected is None:
        collection.update_one({"chat_id": chat_id}, update, upsert=True)
        return revision(chat_id, db)
    result = collection.update_one(_guard(chat_id, expected), update)
    if result.matched_count:
        return revision(chat_id, db)
    # Nothing matched. Either this is the first write (based on the empty
    # revision) or somebody else wrote first.
    if expected == 0 and collection.find_one({"chat_id": chat_id}, {"_id": 1}) is None:
        try:
            collection.insert_one({"chat_id": chat_id, **values, "revision": 1})
            return 1
        except Exception:
            pass  # a concurrent insert won the race; report the conflict
    raise SettingsConflict(expected, revision(chat_id, db))
