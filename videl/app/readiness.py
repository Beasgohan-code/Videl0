"""Read-only onboarding diagnostics. Missing evidence never becomes 'ready'."""
import asyncio
from pyrogram.types import InlineKeyboardMarkup
from videl.utils.bot_ui import button
from videl.utils.command_ui import result
from videl.utils.permission_diagnostics import permission_rows
from .router import Screen,chat_kind


async def inspect_setup(client,message):
    keyboard=InlineKeyboardMarkup([[button('Music guide',callback_data='v2:section:music',style='primary'),
                                   button('Back',callback_data='help:home')]])
    if chat_kind(message) not in {'group','supergroup'}:
        return Screen(result('Set up your group',body='Add the bot to your group, make it an admin, then open this check in that group. For music, the bot and assistant need access to its voice chat. No settings were changed.'),keyboard)
    try:
        me=getattr(client,'me',None) or await asyncio.wait_for(client.get_me(),8)
        member=await asyncio.wait_for(client.get_chat_member(message.chat.id,me.id),8)
    except Exception:
        return Screen(result('Setup could not be checked',body='Telegram did not confirm the bot’s current permissions. Try /permissions in this group. No settings or memberships were changed.'),keyboard)
    rows=permission_rows(member)
    missing=any(value=='Missing' for _,value in rows)
    body=('Open group settings → Administrators → this bot to grant the permissions needed for your chosen features. ' if missing else 'The listed bot permissions are granted. ')
    body+='Assistant membership, an active voice chat and music-provider access are not verified by this check. Start a voice chat and try /play song name. No permissions, settings or memberships were changed.'
    return Screen(result('Group setup · bot permissions',rows,body=body),keyboard)
