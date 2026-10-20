"""Player buttons share command authorization and domain logic, not a second engine.

Callback-query IDs suppress duplicate updates in-process, not across restarts.
Answer transport errors never retry an already acknowledged voice action.
"""
from collections import OrderedDict
import asyncio
import logging
from .router import Context,Parsed,CommandError,authorize
from . import music
from videl.utils.command_ui import rich_reply

log=logging.getLogger(__name__)
_ACTIONS={'pause':'pause','resume':'resume','clear':'clear','cycle_loop':'loop','show_queue':'queue','skip':'skip','stop':'stop','replay':'replay'}
_inflight=set()
_completed=OrderedDict()


async def handle(client,query):
    name=_ACTIONS.get(query.data)
    if name is None:return False
    if not query.message or not query.from_user:
        await query.answer('Open the player in a group chat.',show_alert=True)
        return True
    key=getattr(query,'id',None)
    if key is not None and (key in _inflight or key in _completed):return True
    if len(_inflight)>=128:
        await query.answer('Player controls are busy. Please try again shortly.',show_alert=True)
        return True
    if key is not None:_inflight.add(key)
    try:
        from .routes import COMMANDS
        command=next(item for item in COMMANDS if item.name==name)
        ctx=Context(client,query.message,Parsed(name,''),actor=query.from_user)
        if not await authorize(command,ctx):
            await query.answer('Current group admin permission is required; blocked chats/users cannot use these controls.' if name!='queue' else 'This queue is not available here.',show_alert=True)
            return True
        screen=None
        try:
            if name=='queue':
                screen=await music.view_queue(ctx)
                feedback='Queue opened';alert=False
            else:
                await music.control(ctx,cycle=query.data=='cycle_loop')
                feedback={'pause':'Player is paused','resume':'Player is playing','clear':'Upcoming tracks cleared; current track kept','loop':'Repeat: '+music.player.get_loop(query.message.chat.id),'skip':'Track skipped','stop':'Playback stopped; queue cleared','replay':'Track restarted'}[name]
                alert=False
        except CommandError as error:
            feedback=str(error);alert=True
        except asyncio.CancelledError:raise
        except Exception as error:
            log.warning('Player button %s unconfirmed (%s); no retry',name,type(error).__name__)
            feedback='The change could not be confirmed. Check the voice chat before retrying.';alert=True
        # Deliberately outside the action exception handler. A lost callback answer
        # cannot cause another voice request or a contradictory "failed" answer.
        await query.answer(feedback,show_alert=alert)
        if screen is not None:await rich_reply(query,screen.html,reply_markup=screen.keyboard,client=client)
        return True
    finally:
        if key is not None:
            _inflight.discard(key);_completed[key]=None
            while len(_completed)>4096:_completed.popitem(last=False)
