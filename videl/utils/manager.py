"""The group manager a group's own admins may use.

This is a *scoped* view of ``GroupView``: the actor is the admin who signed in,
not the bot owner, and the actions are limited to the work admins actually do.
Backup import, message recording and history purging stay in the owner console.
"""
from __future__ import annotations

from videl.utils.chat_admins import check as admin_check
from videl.utils.group_view import GroupView, ViewError


def require_admin(db, api, chat, actor):
    answer = admin_check(db, api, chat, actor)
    if not answer.get("admin"):
        raise ViewError("You must currently be an administrator of this group.", 403)
    return answer


def describe(db, api, chat, actor):
    answer = require_admin(db, api, chat, actor)
    view = GroupView(db, api, actor=actor, scope="admin")
    result = view.describe(chat)
    result["scope"] = "admin"
    result["actor"] = int(actor)
    result["rights"] = answer.get("rights") or {}
    result["checked_at"] = answer["checked_at"].isoformat() if answer.get("checked_at") else None
    return result


def act(db, api, chat, actor, body):
    require_admin(db, api, chat, actor)
    view = GroupView(db, api, actor=actor, scope="admin")
    payload = dict(body)
    payload["chat_id"] = int(chat)
    return view.act(payload, source="web")


def history(db, api, chat, actor, *, limit=40, before=None, kind=None):
    require_admin(db, api, chat, actor)
    view = GroupView(db, api, actor=actor, scope="admin")
    return view.events(chat, limit=limit, before=before, kind=kind)
