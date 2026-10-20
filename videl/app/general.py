"""Fresh general-command implementations; presentation is independent of dispatch."""
import asyncio
import time
from datetime import timedelta
from html import escape
from pyrogram.types import InlineKeyboardMarkup,WebAppInfo
import config
from videl import bot_start_time
from videl.utils.bot_ui import button
from videl.utils.command_ui import result,notice
from videl.utils.help_catalog import guide
from .router import Screen,CommandError,chat_kind


def studio_url():
    from urllib.parse import urlsplit
    value=(getattr(config,'WEBAPP_URL','') or 'https://videl-studio.vercel.app').rstrip('/')
    parsed=urlsplit(value)
    return value if parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password else 'https://videl-studio.vercel.app'


def start_keyboard(is_private=True,owner=False,username=''):
    import re
    root=studio_url()
    open_action={'web_app':WebAppInfo(url=root)} if is_private else {'url':root}
    first=[button('How to play',callback_data='v2:section:music',style='primary')]
    if is_private and re.fullmatch(r'[a-zA-Z0-9_]{5,32}',username or ''):
        first.insert(0,button('Add to your group',url=f'https://t.me/{username}?startgroup=true',style='primary'))
    elif not is_private:
        first.append(button('View queue',callback_data='show_queue'))
    rows=[first,
          [button('Check group setup',callback_data='v2:setup',style='primary'),
           button('Moderation guide',callback_data='v2:section:manage')],
          [button('All commands',callback_data='cmds:all:0'),button('Telegram tools',callback_data='v2:section:tools')],
          [button('Open Post Studio',**open_action)]]
    if owner and is_private:
        rows.insert(0,[button('Owner workspace',web_app=WebAppInfo(url=root+'/?tab=settings'),style='primary'),
                       button('Owner commands',callback_data='cmds:owner:0')])
    return InlineKeyboardMarkup(rows)


def start_caption(uid,name,is_private=True):
    name=escape(str(name or 'there'))
    if uid!=6265999542:
        return result('Videl · Music & groups',[
            ('Play a track','/play song name or YouTube link'),
            ('Your queue','/queue · /pause · /resume · /skip'),
            ('Group protection','/setup · /permissions'),
        ],body=f'Hey {name}. '+('Add me to your group, then open Check group setup. Music plays in the group voice chat, not in this private chat.' if is_private else 'Start a voice chat and send /play with a song name. If setup is incomplete, Check group setup shows the bot rights that need attention.'))
    from videl.utils.db import read_live_totals
    try:
        totals=read_live_totals()
        values=[('Groups',totals['chats']),('Users',totals['users']),('Streams',totals['plays'])]
    except Exception:values=[('Database totals','Unavailable')]
    values.append(('Uptime',str(timedelta(seconds=max(0,int(time.time()-bot_start_time))))))
    return result('Videl · Owner workspace',values,body=f'Welcome, {name}. Your owner controls are private. Use /watchdog for maintenance health.')


async def start(ctx):
    user=getattr(ctx.message,'from_user',None)
    uid=user.id if user else 0
    # Owner totals are synchronous MongoDB calls; never block the event loop.
    caption=await asyncio.to_thread(start_caption,uid,getattr(user,'first_name','there')) if ctx.owner else start_caption(0,getattr(user,'first_name','there'),chat_kind(ctx.message)=='private')
    return Screen(caption,start_keyboard(chat_kind(ctx.message)=='private',ctx.owner,getattr(getattr(ctx.client,'me',None),'username','')))


async def help_command(ctx):
    section=ctx.command.arguments.casefold() or 'home'
    if section not in {'home','music','manage','protect','tools'}:
        raise CommandError('Use /help music, /help manage, /help protect or /help tools.')
    text,keyboard=guide(section)
    return Screen(text,keyboard)


async def directory_command(ctx):
    from videl.utils.command_catalog import directory,LABELS
    query=ctx.command.arguments.casefold()
    category=query if query in LABELS else 'all'
    text,keyboard=directory(category,owner=ctx.owner,query='' if query in LABELS else query)
    return Screen(text,keyboard)


async def ping(ctx):
    begin=time.perf_counter()
    await asyncio.wait_for(ctx.client.get_me(),timeout=8)
    latency=round((time.perf_counter()-begin)*1000)
    return Screen(result('Connection status',[
        ('Telegram identity round trip',f'{latency} ms'),
        ('Uptime',str(timedelta(seconds=max(0,int(time.time()-bot_start_time))))),
    ],body='This measures an acknowledged Telegram identity request, not voice-stream quality.'))


async def identifiers(ctx):
    message=ctx.message
    user=getattr(message,'from_user',None)
    rows=[('Chat ID',message.chat.id),('Message ID',message.id),('Your user ID',user.id if user else 'Anonymous sender')]
    argument=ctx.command.arguments
    if argument:
        if len(argument.split())!=1:raise CommandError('Use /id @username or /id numeric_user_id, or reply to a message.')
        try:target=await ctx.client.get_users(int(argument) if argument.isdecimal() else argument)
        except Exception:raise CommandError('Telegram could not resolve that user.') from None
        rows.extend([('Resolved user ID',target.id),('Name',getattr(target,'first_name','Unknown'))])
    reply=getattr(message,'reply_to_message',None)
    if reply:
        rows.append(('Replied message ID',reply.id))
        author=getattr(reply,'from_user',None) or getattr(reply,'sender_chat',None)
        if author:rows.append(('Replied author ID',author.id))
    return Screen(result('Telegram identifiers',rows))


async def source(ctx):
    return Screen(notice('Videl by Beasgohan-code. Rich UI uses the MIT-licensed Badmunda05 Richgram fork. Eldian music components retain their original attribution. See the repository licenses.',title='Source & credits'),
                  InlineKeyboardMarkup([[button('Source & licenses',url='https://github.com/Beasgohan-code/Videl0',style='primary')]]))
