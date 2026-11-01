"""Conflict-safe mutations for the existing ``mgmt_filters`` collection.

There is intentionally no unique keyword index: older installations may
contain normalized duplicates and this checkout has no production DB with which
to census them. All current bot and Group Manager writers use a short per-chat
lease stored as an ignored sentinel row in this same collection. Edits also
compare the exact row snapshot captured when the interactive draft began.
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

COLLECTION = "mgmt_filters"
MAX_KEYWORD = 64
MAX_REPLY = 400
LEASE_SECONDS = 120


class FilterStoreConflict(ValueError):
    """A concurrent write, ambiguous duplicate, or stale filter snapshot."""


class FilterStoreError(RuntimeError):
    """The filter collection could not safely complete a mutation."""


def normalize_keyword(value) -> str:
    if not isinstance(value, str):
        raise ValueError("Filter keywords must be text.")
    keyword = value.strip().casefold()
    if not keyword:
        raise ValueError("A filter keyword cannot be empty.")
    if len(keyword) > MAX_KEYWORD:
        raise ValueError(f"Filter keywords must be {MAX_KEYWORD} characters or fewer.")
    return keyword


def normalize_reply(value) -> str:
    if not isinstance(value, str):
        raise ValueError("Filter responses must be plain text.")
    reply = value.strip()
    if not reply:
        raise ValueError("A filter response cannot be empty.")
    if len(reply) > MAX_REPLY:
        raise ValueError(f"Filter responses must be {MAX_REPLY} characters or fewer.")
    return reply


def _collection(db):
    if db is None:
        raise FilterStoreError("The filters database is unavailable; nothing changed.")
    try:
        return db[COLLECTION]
    except Exception:
        raise FilterStoreError("The filters database is unavailable; nothing changed.") from None


@contextmanager
def _group_lease(collection, chat_id: int):
    """Serialize cooperating writers across bot processes using Mongo's _id."""
    chat_id = int(chat_id)
    lock_id = f"__filter_mutation_lock__:{chat_id}"
    token = secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc)
    try:
        lease = collection.find_one_and_update(
            {"_id": lock_id, "$or": [{"lease_until": {"$lte": now}},
                                       {"lease_until": {"$exists": False}}]},
            {"$set": {"_filter_lock": True, "lease_token": token,
                      "lease_until": now + timedelta(seconds=LEASE_SECONDS)}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise FilterStoreConflict("Another filter change is in progress for this group; try again shortly.") from None
    except Exception:
        raise FilterStoreError("Could not coordinate a safe filter change; nothing changed.") from None
    if not isinstance(lease, dict) or lease.get("lease_token") != token:
        raise FilterStoreConflict("Another filter change is in progress for this group; try again shortly.")
    try:
        yield
    finally:
        try:
            collection.delete_one({"_id": lock_id, "lease_token": token})
        except Exception:
            # The expiring lease is a safe fallback if a release hits an outage.
            pass


def _matching_rows(collection, chat_id: int, keyword: str):
    """Find all legacy case/space variants; never pick an arbitrary duplicate."""
    rows = []
    try:
        for row in collection.find({"chat_id": int(chat_id)}):
            raw = row.get("keyword")
            if isinstance(raw, str):
                try:
                    if normalize_keyword(raw) == keyword:
                        rows.append(row)
                except ValueError:
                    continue
    except Exception:
        raise FilterStoreError("Could not inspect this group’s filters; nothing changed.") from None
    return rows


def list_filters(db, chat_id: int):
    collection = _collection(db)
    try:
        return list(collection.find({"chat_id": int(chat_id)}).sort("keyword", 1))
    except Exception:
        raise FilterStoreError("Could not load this group’s filters.") from None


def put_filter(db, chat_id: int, keyword, reply, *, mode: str = "upsert"):
    """Add or compatibility-upsert one normalized text filter under a lease."""
    if mode not in {"create", "upsert"}:
        raise ValueError("Unsupported filter write mode.")
    chat_id = int(chat_id)
    keyword = normalize_keyword(keyword)
    reply = normalize_reply(reply)
    collection = _collection(db)
    with _group_lease(collection, chat_id):
        matches = _matching_rows(collection, chat_id, keyword)
        if len(matches) > 1:
            raise FilterStoreConflict(
                "Multiple saved filters normalize to that keyword. Nothing changed; review the existing list and remove duplicates individually."
            )
        if matches:
            if mode == "create":
                raise FilterStoreConflict("That keyword already has a filter. Edit the existing filter instead.")
            row = matches[0]
            try:
                result = collection.update_one(
                    {"_id": row["_id"], "chat_id": chat_id,
                     "keyword": row.get("keyword"), "reply": row.get("reply")},
                    {"$set": {"keyword": keyword, "reply": reply}},
                )
            except Exception:
                raise FilterStoreError("Could not save the filter; nothing was reported as saved.") from None
            if result.matched_count != 1:
                raise FilterStoreConflict("That filter changed elsewhere. Reopen the filter list and try again.")
            return {"_id": row["_id"], "chat_id": chat_id, "keyword": keyword, "reply": reply}, "updated"
        try:
            result = collection.insert_one({"chat_id": chat_id, "keyword": keyword, "reply": reply})
            return {"_id": result.inserted_id, "chat_id": chat_id, "keyword": keyword, "reply": reply}, "created"
        except Exception:
            raise FilterStoreError("Could not save the filter; nothing was reported as saved.") from None


def edit_filter(db, chat_id: int, original: dict, keyword, reply):
    """Compare the original row and target keyword before one atomic update."""
    chat_id = int(chat_id)
    if not isinstance(original, dict) or "_id" not in original:
        raise FilterStoreConflict("This filter edit is no longer available. Reopen the filter list.")
    keyword = normalize_keyword(keyword)
    reply = normalize_reply(reply)
    collection = _collection(db)
    with _group_lease(collection, chat_id):
        try:
            current = collection.find_one({"_id": original["_id"], "chat_id": chat_id})
        except Exception:
            raise FilterStoreError("Could not verify the original filter; nothing changed.") from None
        if (current is None or current.get("keyword") != original.get("keyword")
                or current.get("reply") != original.get("reply")):
            raise FilterStoreConflict("This filter changed or was removed while you were editing. Nothing changed; reopen the filter list.")
        old_keyword = normalize_keyword(current.get("keyword"))
        old_matches = _matching_rows(collection, chat_id, old_keyword)
        if len(old_matches) != 1 or old_matches[0].get("_id") != original["_id"]:
            raise FilterStoreConflict("Duplicate filters share this keyword. Nothing changed; remove duplicates individually before editing.")
        target_matches = [row for row in _matching_rows(collection, chat_id, keyword)
                          if row.get("_id") != original["_id"]]
        if target_matches:
            raise FilterStoreConflict("Another filter already uses that keyword. Choose a different keyword or edit that filter.")
        try:
            result = collection.update_one(
                {"_id": original["_id"], "chat_id": chat_id,
                 "keyword": current.get("keyword"), "reply": current.get("reply")},
                {"$set": {"keyword": keyword, "reply": reply}},
            )
        except Exception:
            raise FilterStoreError("Could not save the filter edit; nothing was reported as saved.") from None
        if result.matched_count != 1:
            raise FilterStoreConflict("This filter changed elsewhere. Nothing was saved; reopen the filter list.")
        return {"_id": original["_id"], "chat_id": chat_id, "keyword": keyword, "reply": reply}


def _delete_locked(collection, chat_id: int, original: dict) -> bool:
    try:
        result = collection.delete_one({"_id": original["_id"], "chat_id": chat_id,
                                        "keyword": original.get("keyword"),
                                        "reply": original.get("reply")})
    except Exception:
        raise FilterStoreError("Could not remove the filter; no success was reported.") from None
    if result.deleted_count != 1:
        raise FilterStoreConflict("This filter changed or was already removed. Reopen the filter list.")
    return True


def delete_filter_by_id(db, chat_id: int, original: dict) -> bool:
    """Delete exactly the row shown to the admin, conditional on its snapshot."""
    chat_id = int(chat_id)
    if not isinstance(original, dict) or "_id" not in original:
        raise FilterStoreConflict("This filter button is invalid. Reopen the filter list.")
    collection = _collection(db)
    with _group_lease(collection, chat_id):
        return _delete_locked(collection, chat_id, original)


def delete_filter_by_keyword(db, chat_id: int, keyword) -> bool:
    """Compatibility deletion; refuses to guess when normalized duplicates exist."""
    chat_id = int(chat_id)
    keyword = normalize_keyword(keyword)
    collection = _collection(db)
    with _group_lease(collection, chat_id):
        matches = _matching_rows(collection, chat_id, keyword)
        if not matches:
            return False
        if len(matches) > 1:
            raise FilterStoreConflict(
                "Multiple saved filters normalize to that keyword. Use /filters to review and remove each duplicate individually."
            )
        return _delete_locked(collection, chat_id, matches[0])
