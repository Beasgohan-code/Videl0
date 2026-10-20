"""Every current group admin can stop recording, even if not the bot owner."""
import asyncio
import uuid
from videl.utils.db import get_db
from videl.utils.command_ui import result
from .router import Screen,CommandError


async def recording(ctx):
    action=ctx.command.arguments.lower()
    if action not in {'','status','off'}:raise CommandError('Use /groupview status or /groupview off. Enabling is opt-in through the owner webapp.')
    def change():
        db=get_db()
        if db is None:raise CommandError('MongoDB is unavailable. Recording status could not be confirmed.')
        if action=='off':db['group_view_settings'].update_one({'_id':ctx.message.chat.id},{'$set':{'enabled':False,'epoch':str(uuid.uuid4())}},upsert=True)
        return db['group_view_settings'].find_one({'_id':ctx.message.chat.id}) or {}
    settings=await asyncio.to_thread(change)
    return Screen(result('Group viewer recording',[
        ('Recording','Enabled' if settings.get('enabled') else 'Off'),
        ('Retention',str(settings.get('retention_days',7))+' days'),
    ],body='Use /inbox off in a private chat or /groupview off as a group admin. Existing snapshots expire under the retention policy; this does not delete Telegram messages.'))


async def private_recording(ctx):
    from .router import chat_kind
    if chat_kind(ctx.message)!='private' or ctx.user.id!=ctx.message.chat.id:
        raise CommandError('Use /inbox off or /inbox status in your private conversation with this bot.')
    return await recording(ctx)
