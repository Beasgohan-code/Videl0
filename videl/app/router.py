"""Declarative command routing with explicit policies and a single render boundary."""
from __future__ import annotations
import asyncio
import logging
import config
import re
from collections import OrderedDict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Awaitable, Callable
from pyrogram.enums import ChatMemberStatus
from videl.utils.command_ui import notice, rich_reply

log=logging.getLogger(__name__)
OWNER_ID=6265999542
COMMAND_PREFIXES = config.COMMAND_PREFIXES
_PATTERN=re.compile(r'^([' + re.escape(COMMAND_PREFIXES) + r'])' + r'([a-zA-Z0-9_]{1,32})(?:@([a-zA-Z0-9_]{1,32}))?(?:\s+([\s\S]*))?$')


class CommandError(ValueError):
    """A safe validation failure; never a raw provider/credential error."""


@dataclass(frozen=True)
class Parsed:
    name:str
    arguments:str


def parse(text, username=''):
    if not isinstance(text,str) or len(text)>65536:return None
    match=_PATTERN.fullmatch(text.strip())
    if not match:return None
    _prefix,name,mention,args=match.groups()
    if mention and (not username or mention.casefold()!=username.lstrip('@').casefold()):return None
    return Parsed(name.casefold(),(args or '').strip())


def chat_kind(message):
    value=getattr(getattr(message,'chat',None),'type','')
    return str(getattr(value,'value',value))


def private_owner(message,actor=None):
    user=actor or getattr(message,'from_user',None)
    return bool(user and user.id==OWNER_ID and chat_kind(message)=='private')


@dataclass(frozen=True)
class Screen:
    html:str
    keyboard:object=None
    animation:bytes|None=None


@dataclass(frozen=True)
class Context:
    client:object
    message:object
    command:Parsed
    actor:object=None

    @property
    def user(self):return self.actor if self.actor is not None else getattr(self.message,"from_user",None)

    @property
    def owner(self):return private_owner(self.message,self.user)


@dataclass(frozen=True)
class Command:
    name:str
    handler:Callable[[Context],Awaitable[Screen|None]]
    summary:str
    category:str='tools'
    policy:str='public'
    rights:tuple[str,...]=()
    block_policy:str="none"

    def __post_init__(self):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',self.name):raise ValueError('Invalid command name')
        if self.policy not in {'public','group','admin','owner'}:raise ValueError('Invalid command policy')
        if self.category not in {'tools','music','manage','owner'}:raise ValueError('Invalid command category')
        if self.block_policy not in {'none','user','chat'}:raise ValueError('Invalid block policy')
        if self.rights and (self.policy!='admin' or any(right not in {'can_restrict_members','can_delete_messages','can_manage_topics','can_pin_messages','can_promote_members','can_invite_users','can_change_info'} for right in self.rights)):
            raise ValueError('Invalid command administrator rights')


async def authorize(command,ctx):
    if command.block_policy!='none':
        from videl.utils.db import is_group_blocked,is_user_blocked_db
        def blocked():
            user=ctx.user
            return (user is not None and is_user_blocked_db(user.id)) or (command.block_policy=='chat' and is_group_blocked(ctx.message.chat.id))
        if await asyncio.to_thread(blocked):return False
    if command.policy=='owner':return ctx.owner
    if command.policy in {'group','admin'} and chat_kind(ctx.message) not in {'group','supergroup'}:return False
    if command.policy=='admin':
        user=ctx.user
        if not user:return False
        try:
            member=await ctx.client.get_chat_member(ctx.message.chat.id,user.id)
            if member.status==ChatMemberStatus.OWNER:return True
            return member.status==ChatMemberStatus.ADMINISTRATOR and all(bool(getattr(getattr(member,'privileges',None),right,False)) for right in command.rights)
        except Exception:return False
    return True


class Router:
    """No Telegram effects during construction; registration is explicit and unique."""
    def __init__(self,commands):
        table={}
        for command in commands:
            if command.name in table:raise ValueError('Duplicate command: '+command.name)
            table[command.name]=command
        self.commands=MappingProxyType(table)
        # Runtime-only deduplication, bounded to 4096 completed update IDs.
        self._active=set()
        self._completed=OrderedDict()
        self._limit=128

    async def dispatch(self,client,message):
        me=getattr(client,'me',None)
        parsed=parse(getattr(message,'text',None),getattr(me,'username','') or '')
        if parsed is None or parsed.name not in self.commands:return False
        command=self.commands[parsed.name]
        original_message=message
        actor=getattr(message,'from_user',None)
        # Only the explicit connected-command allowlist may use a saved group
        # context. Keep the real Telegram actor and retain private reply target.
        if chat_kind(message)=='private':
            from videl.app.connections import CONNECTED_COMMANDS, connected_message
            if parsed.name in CONNECTED_COMMANDS:
                proxy,error=await connected_message(client,message,parsed.name)
                if error:
                    await rich_reply(message,notice(error,status='warning',title='Connected group'),client=client)
                    return True
                if proxy is None:
                    return False
                message=proxy
        ctx=Context(client,message,parsed,actor)
        if not await authorize(command,ctx):
            requirement = {
                'group': 'a group chat',
                'admin': 'current group administrator privileges',
                'owner': 'the verified owner in a private chat',
            }.get(command.policy, 'the required permission')
            if command.policy == 'admin' and command.rights:
                labels = {
                    'can_restrict_members': 'Restrict members',
                    'can_delete_messages': 'Delete messages',
                    'can_manage_topics': 'Manage topics',
                    'can_pin_messages': 'Pin messages',
                    'can_promote_members': 'Promote members',
                    'can_invite_users': 'Invite users',
                    'can_change_info': 'Change group info',
                }
                requirement += ' and the Telegram right: ' + ', '.join(labels.get(right, right) for right in command.rights)
            await rich_reply(
                original_message,
                notice(
                    f'This command requires {requirement}. Blocked users or chats cannot use this action.',
                    status='error', title='Access restricted',
                ),
                client=client,
            )
            return True
        # A group admin may disable a command for their own group from the panel.
        # Owners are never locked out of their own bot.
        if command.policy!='owner' and chat_kind(message) in {'group','supergroup'}:
            try:
                from videl.utils.db import is_disabled
                disabled=await asyncio.to_thread(is_disabled,message.chat.id,command.name)
            except Exception:disabled=False
            if disabled:
                await rich_reply(original_message,notice('The group administrators have turned this command off. Ask an admin to re-enable it in the group manager.',status='warning',title='Command turned off'),client=client)
                return True
        # A repeated Telegram update must not overlap a still-running action.
        key=(original_message.chat.id,getattr(original_message,'id',None))
        if key in self._active or key in self._completed:return True
        if len(self._active)>=self._limit:
            await rich_reply(original_message,notice('The bot is handling several requests. Please try again shortly.',status='warning',title='Busy'),client=client)
            return True
        self._active.add(key)
        try:
            try:
                screen=await command.handler(ctx)
            except CommandError as error:
                from html import escape
                screen=Screen(notice(escape(str(error)),status='warning',title='Check command details'))
            except asyncio.CancelledError:raise
            except Exception as error:
                log.warning('Command %s unconfirmed (%s); no automatic retry to avoid duplicate effects',command.name,type(error).__name__,exc_info=True)
                screen=Screen(notice('Something went wrong while processing this command, so I cannot confirm whether it completed. Check the destination first; retry only if the action did not happen.',status='warning',title='⚠️ Action unconfirmed'))
            # Rendering is outside the action exception handler: a render error
            # cannot trigger a second send or reinterpret an acknowledged action.
            if screen is not None:
                if screen.animation is None:
                    await rich_reply(original_message,screen.html,reply_markup=screen.keyboard,client=client,navigation=False)
                else:
                    # GIF delivery is a single media send. Retry only a definite
                    # visual rejection; never send a second copy after a timeout.
                    from io import BytesIO
                    from pyrogram.enums import ParseMode
                    from pyrogram.errors import BadRequest
                    from videl.utils.bot_ui import visual_call
                    animation=BytesIO(screen.animation)
                    animation.name='videl-fun.gif'
                    options={
                        'chat_id':original_message.chat.id,
                        'animation':animation,
                        'caption':screen.html,
                        'parse_mode':ParseMode.HTML,
                        'reply_to_message_id':getattr(original_message,'id',None),
                    }
                    thread=getattr(message,'message_thread_id',None)
                    if thread is not None:options['message_thread_id']=thread
                    if screen.keyboard is not None:
                        options['reply_markup']=screen.keyboard
                    try:
                        await visual_call(client.send_animation,**options)
                    except BadRequest:
                        await rich_reply(
                            original_message,
                            notice('Telegram rejected the animation, so here is the reaction as a text reply.',status='warning',title='GIF unavailable'),
                            client=client,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        log.warning('Animation delivery unconfirmed (%s); no second send',type(error).__name__)

        finally:
            self._active.discard(key)
            self._completed[key]=None
            while len(self._completed)>4096:self._completed.popitem(last=False)
        return True
