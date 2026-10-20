"""Map actual Telegram member rights to actionable diagnostics."""
from pyrogram.enums import ChatMemberStatus
REQUIRED_RIGHTS = {
    "can_delete_messages": "Delete messages — locks, filters and cleanup",
    "can_restrict_members": "Restrict members — bans, mutes and join verification",
    "can_invite_users": "Invite users — invite links and join requests",
    "can_pin_messages": "Pin messages — pin/unpin commands",
    "can_manage_video_chats": "Manage video chats — voice-chat creation/control",
}


def permission_rows(member):
    owner = member.status == ChatMemberStatus.OWNER
    admin = member.status == ChatMemberStatus.ADMINISTRATOR
    rights = getattr(member, "privileges", None)
    return [(description, "Granted" if owner or admin and bool(getattr(rights, key, False))
             else "Missing") for key, description in REQUIRED_RIGHTS.items()]
