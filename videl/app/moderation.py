"""Fresh moderation actions: validated targets, finite durations and honest outcomes.

Uses existing Mongo collections without migrations or data deletion. Telegram
acknowledgement and best-effort audit persistence are separate outcomes.
"""
import asyncio
import logging
import re
from datetime import datetime,timedelta,timezone
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions
from videl.utils.command_ui import result,notice
from videl.utils.db import get_db
from .router import CommandError,Screen

log=logging.getLogger(__name__)


def duration(value):
    match=re.fullmatch(r'([1-9][0-9]{0,7})([smhdw])',value)
    if not match:raise CommandError('Temporary actions need a duration such as 10m, 2h or 7d.')
    seconds=int(match[1])*{'s':1,'m':60,'h':3600,'d':86400,'w':604800}[match[2]]
    if not 60<=seconds<=365*86400:raise CommandError('Choose a duration from 1 minute to 365 days.')
    return seconds


async def resolve(ctx):
    reply=getattr(ctx.message,'reply_to_message',None)
    tokens=ctx.command.arguments.split()
    user=getattr(reply,'from_user',None) if reply else None
    if user is None:
        if not tokens:raise CommandError('Reply to a user or provide @username/numeric user ID.')
        identifier=tokens.pop(0)
        if not (identifier.startswith('@') or identifier.isascii() and identifier.isdecimal()):
            raise CommandError('Use @username or a positive numeric user ID.')
        try:user=await ctx.client.get_users(int(identifier) if identifier.isdecimal() else identifier)
        except Exception:raise CommandError('Telegram could not resolve the target. No action was taken.') from None
    if user.id<=0:raise CommandError('Channel/anonymous senders cannot be targeted as users.')
    return user,tokens


async def require_bot_rights(ctx):
    me=getattr(ctx.client,'me',None) or await ctx.client.get_me()
    member=await ctx.client.get_chat_member(ctx.message.chat.id,me.id)
    if member.status==ChatMemberStatus.OWNER:return
    rights=getattr(member,'privileges',None)
    required=['can_restrict_members']+(['can_delete_messages'] if ctx.command.name in {'dban','dkick'} else [])
    if member.status!=ChatMemberStatus.ADMINISTRATOR or not all(getattr(rights,key,False) for key in required):
        raise CommandError('The bot needs Restrict members'+(' and Delete messages' if len(required)>1 else '')+' administrator permissions.')


def record_ban(chat_id,user_id,reason,remove=False):
    db=get_db()
    if db is None:return False
    collection=db['mgmt_banned_users']
    selector={'chat_id':chat_id,'user_id':user_id}
    if remove:collection.delete_one(selector)
    else:collection.update_one(selector,{'$set':{'reason':reason,'ts':datetime.now(timezone.utc).isoformat()}},upsert=True)
    return True


async def moderate(ctx):
    user,tokens=await resolve(ctx)
    name=ctx.command.name
    until=None
    if name in {'tban','tmute'}:
        if not tokens:raise CommandError('Add a temporary duration, for example /'+name+' @user 10m reason.')
        until=datetime.now(timezone.utc)+timedelta(seconds=duration(tokens.pop(0)))
    reason=' '.join(tokens)[:500] or 'No reason supplied'
    me=getattr(ctx.client,'me',None) or await ctx.client.get_me()
    if user.id in {me.id,6265999542}:raise CommandError('The bot and bot owner are protected targets.')
    # Unknown target membership is an error, not evidence that the target is not admin.
    member=await ctx.client.get_chat_member(ctx.message.chat.id,user.id)
    if member.status in {ChatMemberStatus.OWNER,ChatMemberStatus.ADMINISTRATOR}:
        raise CommandError('Group owners and administrators are protected targets.')
    await require_bot_rights(ctx)
    cid=ctx.message.chat.id
    notes=[]
    if name in {'ban','tban','dban','kick','dkick'}:
        expiry=datetime.now(timezone.utc)+timedelta(seconds=60) if name in {'kick','dkick'} else until
        acknowledged=await ctx.client.ban_chat_member(cid,user.id,until_date=expiry)
        if acknowledged is False:raise RuntimeError('Ban not acknowledged')
        title='Member banned'
        if name in {'kick','dkick'}:
            try:
                if await ctx.client.unban_chat_member(cid,user.id) is False:raise RuntimeError()
                title='Member removed'
            except Exception:
                title='Removal partly confirmed'
                notes.append('Temporary ban was acknowledged; release was not confirmed. Check membership before retrying. The ban expires in about one minute.')
        else:
            try:
                if not await asyncio.to_thread(record_ban,cid,user.id,reason):notes.append('Telegram confirmed the action, but the audit database is unavailable.')
            except Exception:notes.append('Telegram confirmed the action; the audit record could not be saved.')
    elif name=='unban':
        if await ctx.client.unban_chat_member(cid,user.id) is False:raise RuntimeError('Unban not acknowledged')
        title='Member unbanned'
        try:
            if not await asyncio.to_thread(record_ban,cid,user.id,reason,True):notes.append('Telegram confirmed the action; the local ban record could not be updated.')
        except Exception:notes.append('Telegram confirmed the action; the local ban record could not be updated.')
    elif name in {'mute','tmute','unmute'}:
        permissions=ChatPermissions(can_send_messages=False)
        if name=='unmute':
            chat=await ctx.client.get_chat(cid)
            permissions=chat.permissions
            if permissions is None:raise CommandError('Group default permissions could not be read. No permissions were changed.')
        if await ctx.client.restrict_chat_member(cid,user.id,permissions,until_date=until) is False:raise RuntimeError('Restriction not acknowledged')
        title='Member unmuted' if name=='unmute' else 'Member muted'
    else:raise CommandError('Unknown moderation action.')
    if name in {'dban','dkick'} and getattr(ctx.message,'reply_to_message',None):
        try:
            if await ctx.client.delete_messages(cid,ctx.message.reply_to_message.id) is False:raise RuntimeError()
        except Exception:notes.append('Membership action was confirmed; message deletion was not confirmed.')
    rows=[('User',getattr(user,'first_name','Unknown')),('User ID',user.id),('Reason',reason)]
    if until:rows.append(('Until (UTC)',until.isoformat()))
    return Screen(result(title,rows,body=' '.join(notes) or 'Telegram acknowledged the requested action.'))
