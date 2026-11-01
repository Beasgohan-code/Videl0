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
    # Telegram intentionally does not provide bots with a full member directory.
    # Show the administrators Telegram does expose, without pretending it is a list of everyone.
    try:
        admins = view.call("getChatAdministrators", {"chat_id": int(chat)})
        result["members"] = [{
            "user_id": int(row.get("user", {}).get("id") or 0),
            "name": " ".join(filter(None, [row.get("user", {}).get("first_name"), row.get("user", {}).get("last_name")]))[:100],
            "username": str(row.get("user", {}).get("username") or "")[:64],
            "status": str(row.get("status") or "member"),
        } for row in admins if isinstance(row, dict) and isinstance(row.get("user"), dict)]
        result["members_available"] = True
    except Exception:
        result["members"] = []
        result["members_available"] = False
    return result


def act(db, api, chat, actor, body):
    require_admin(db, api, chat, actor)
    view = GroupView(db, api, actor=actor, scope="admin")
    payload = dict(body)
    payload["chat_id"] = int(chat)
    action = payload.get("action")
    if action == "member_action":
        verb = str(payload.get("verb") or "")
        if verb not in {"kick", "ban", "mute", "unmute"}:
            raise ViewError("Choose kick, ban, mute or unmute.")
        try:
            target = int(payload.get("user_id"))
        except (TypeError, ValueError):
            raise ViewError("Enter a numeric Telegram user ID.") from None
        if target <= 0 or target == int(actor):
            raise ViewError("Choose another valid member ID.")
        _, actor_member = view.access(int(chat))
        view.rights(int(chat), actor_member, ["can_restrict_members"])
        member = view.call("getChatMember", {"chat_id": int(chat), "user_id": target})
        if member.get("status") in {"creator", "administrator"}:
            raise ViewError("Group admins and the group owner cannot be moderated here.", 403)
        if verb == "ban":
            view.call("banChatMember", {"chat_id": int(chat), "user_id": target})
        elif verb == "kick":
            view.call("banChatMember", {"chat_id": int(chat), "user_id": target})
            view.call("unbanChatMember", {"chat_id": int(chat), "user_id": target, "only_if_banned": True})
        elif verb == "mute":
            try:
                minutes = int(payload.get("minutes", 60))
            except (TypeError, ValueError):
                raise ViewError("Mute duration must be between 1 and 10080 minutes.") from None
            if not 1 <= minutes <= 10080:
                raise ViewError("Mute duration must be between 1 and 10080 minutes.")
            import time
            view.call("restrictChatMember", {"chat_id": int(chat), "user_id": target,
                "permissions": {"can_send_messages": False, "can_send_audios": False,
                    "can_send_documents": False, "can_send_photos": False, "can_send_videos": False,
                    "can_send_video_notes": False, "can_send_voice_notes": False,
                    "can_send_polls": False, "can_send_other_messages": False,
                    "can_add_web_page_previews": False}, "until_date": int(time.time()) + minutes * 60})
        else:
            view.call("restrictChatMember", {"chat_id": int(chat), "user_id": target,
                "permissions": {"can_send_messages": True, "can_send_audios": True,
                    "can_send_documents": True, "can_send_photos": True, "can_send_videos": True,
                    "can_send_video_notes": True, "can_send_voice_notes": True,
                    "can_send_polls": True, "can_send_other_messages": True,
                    "can_add_web_page_previews": True}})
        view.log(int(chat), "member_action", {"verb": verb, "user_id": target}, "web")
        return {"ok": True, "verb": verb, "user_id": target}
    if action == "invite_link":
        _, actor_member = view.access(int(chat))
        view.rights(int(chat), actor_member, ["can_invite_users"])
        invite = view.call("createChatInviteLink", {"chat_id": int(chat), "name": "Videl manager"})
        view.log(int(chat), "invite_link", {}, "web")
        return {"ok": True, "invite_link": str(invite.get("invite_link") or "")}
    return view.act(payload, source="web")


def history(db, api, chat, actor, *, limit=40, before=None, kind=None, query=None,
            actor_filter=None, date_from=None, date_through=None):
    require_admin(db, api, chat, actor)
    view = GroupView(db, api, actor=actor, scope="admin")
    return view.events(chat, limit=limit, before=before, kind=kind,
                       query=query, actor=actor_filter,
                       after=date_from, until=date_through)
