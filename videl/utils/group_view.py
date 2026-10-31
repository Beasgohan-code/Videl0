"""Opt-in bot-visible group messages and permission-checked owner operations.

No user account, history scraping, media downloads or getUpdates consumer.
Snapshots keep the raw text/caption (which may include Telegram HTML); Mongo TTL
is supplemented by read-time expiration, and outbound text is sanitized.
"""
import asyncio
from datetime import datetime,timedelta,timezone
import html as _html
import logging
import re
import time
import uuid
from pymongo.errors import DuplicateKeyError

from videl.utils import audit as audit_log, settings_store
from videl.utils.automation import (DECAY_RANGE, ESCALATION_ACTIONS, ESCALATION_LADDER, MUTE_RANGE,
                                    normalize, normalize_escalation, normalize_protection,
                                    normalize_quiet, parse_hhmm)
from videl.utils.moderation import LOCK_TYPES

OWNER_ID=6265999542
RETENTION=(1,7,30)

# Every lock the enforcement pass in videl.plugins.locks honours. The key is
# what the watcher reads (``lock_<kind>``), with the historic plural used for
# forwards so existing groups keep their setting.
LOCK_KEYS=tuple('lock_forwards' if kind=='forward' else f'lock_{kind}' for kind in LOCK_TYPES)
PROTECTION=set(LOCK_KEYS)|{'antispam','welcome_enabled','goodbye_enabled','captcha_enabled'}

# Types the admin surface may write. Only keys the bot actually reads belong
# here — a switch that saves a value nothing consumes is a lie in the UI.
BOOL_SETTINGS=tuple(sorted(PROTECTION))
INT_SETTINGS={'warn_threshold':(1,10)}
INT_DEFAULTS={'warn_threshold':3}
TEXT_SETTINGS={'welcome_message':1000,'goodbye_message':1000,'rules':2000}
ENUM_SETTINGS={'blacklist_mode':{'off','del','warn','mute','ban','kick'}}
SETTING_DEFAULTS={'welcome_enabled':True}

PRESETS={
 'relaxed':{'label':'Relaxed','description':'Greetings stay on, every lock is released.','settings':{
     'antispam':False,**{key:False for key in LOCK_KEYS},'welcome_enabled':True,'goodbye_enabled':False,'captcha_enabled':False}},
 'balanced':{'label':'Balanced','description':'Flood control, links and forwards only.','settings':{
     'antispam':True,**{key:key in {'lock_links','lock_forwards'} for key in LOCK_KEYS},'welcome_enabled':True,'goodbye_enabled':False,'captcha_enabled':False}},
 'strict':{'label':'Strict','description':'Media, stickers, mentions, bots and polls blocked.','settings':{
     'antispam':True,**{key:key in {'lock_links','lock_forwards','lock_media','lock_stickers','lock_mentions','lock_bots','lock_polls'} for key in LOCK_KEYS},'welcome_enabled':True,'goodbye_enabled':False,'captcha_enabled':True}},
 'lockdown':{'label':'Lockdown','description':'Every content lock on; greetings paused.','settings':{
     'antispam':True,**{key:True for key in LOCK_KEYS},'welcome_enabled':False,'goodbye_enabled':False,'captcha_enabled':True}},
}


def _revision() -> str:
    """Which backend wrote the file, so a stale import is obvious later."""
    import os
    return (os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or 'dev')[:12]


def coerce_bool(value):
    return value if type(value) is bool else bool(value)
REACTIONS=('👍','❤️','🔥','🎉','😁','🤔','👏','🙏','💯','⚡')
_PARSE_ERROR=re.compile(r'parse|entit|tag|nest',re.I)


def parse_error(status,description):
    return status==400 and bool(_PARSE_ERROR.search(str(description or '')))
log=logging.getLogger(__name__)

_AUDIT_TEXT_FIELDS={'welcome','goodbye','rules','text'}


def audit_detail(action,body):
    """A short human summary of a change, without dumping message bodies."""
    body=body if isinstance(body,dict) else {}
    parts=[]
    if action=='settings' and isinstance(body.get('settings'),dict):
        on=[key for key,value in body['settings'].items() if value is True]
        off=[key for key,value in body['settings'].items() if value is False]
        if on:parts.append('on: '+', '.join(sorted(on)))
        if off:parts.append('off: '+', '.join(sorted(off)))
    for key in ('preset','mode','limit','trigger','command','name','keyword','user_id','status','decision','verb'):
        value=body.get(key)
        if value not in (None,''):parts.append(f'{key}: {value}')
    for key in _AUDIT_TEXT_FIELDS:
        if isinstance(body.get(key),str):parts.append(f'{key}: {len(body[key])} characters')
    if isinstance(body.get('settings'),dict) and action=='automation':
        parts.append('automation updated')
    if isinstance(body.get('quiet_hours'),dict):parts.append('quiet hours updated')
    if isinstance(body.get('escalation'),dict):parts.append('escalation updated')
    return '; '.join(parts)



class ViewError(ValueError):
    def __init__(self,message,status=400):super().__init__(message);self.status=status


class TelegramError(ViewError):
    """A rejected Bot API call. A 400 response is explicit: nothing was sent."""

    def __init__(self,description,status=502):
        super().__init__('Telegram rejected this action. Check the destination and try again.',502)
        self.description=str(description or '')
        self.api_status=status

    @property
    def parse_error(self):
        return self.api_status==400 and bool(_PARSE_ERROR.search(self.description))


def integer(value,*,positive=False):
    if isinstance(value,bool) or not re.fullmatch(r'-?[0-9]{1,16}',str(value)):raise ViewError('A numeric Telegram ID is required.')
    value=int(value)
    if abs(value)>9007199254740991 or (positive and value<=0):raise ViewError('Invalid Telegram ID.')
    return value


def now():return datetime.now(timezone.utc)


def aware(value):
    if not isinstance(value,datetime):return now()
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def case_timestamp(value):
    """Normalize legacy ISO strings, Mongo datetimes and epoch seconds."""
    try:
        if isinstance(value, datetime):
            stamp=aware(value)
        elif isinstance(value, (int,float)):
            stamp=datetime.fromtimestamp(float(value),timezone.utc)
        elif isinstance(value,str):
            stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
            stamp=aware(stamp)
        else:return None
        return stamp.isoformat()
    except (TypeError,ValueError,OverflowError,OSError):
        return None


_ENTITY_MARKS={'BOLD':'b','ITALIC':'i','UNDERLINE':'u','STRIKETHROUGH':'s','SPOILER':'tg-spoiler','CODE':'code','PRE':'pre','BLOCKQUOTE':'blockquote'}


def _utf16_positions(text):
    """Map UTF-16 code-unit offsets (Telegram's unit) to Python string indexes."""
    positions=[];index=0
    for char in text:
        positions.append(index)
        index+=2 if ord(char)>0xFFFF else 1
    positions.append(index)
    return positions


def entities_html(text,entities):
    """Recreate Telegram formatting captured from message entities as HTML.

    Pyrogram hands us plain text plus offsets, so formatting — including custom
    (premium) emoji — would otherwise be lost the moment a message is stored.
    Returns (html, used); improperly overlapping entities are dropped rather
    than emitted as broken markup, and the result is passed through
    :func:`normalize_rich` so it is always safe to send back to Telegram.
    """
    text=str(text or '')
    if not text or not entities:return text,False
    units=_utf16_positions(text)
    def to_index(offset):
        offset=max(0,int(offset or 0))
        for index,unit in enumerate(units):
            if unit>=offset:return index
        return len(text)
    spans=[]
    for entity in entities:
        kind=str(getattr(getattr(entity,'type',None),'name',getattr(entity,'type','')) or '').upper()
        start=to_index(getattr(entity,'offset',0));end=to_index(getattr(entity,'offset',0)+getattr(entity,'length',0))
        if end<=start or start<0 or end>len(text):continue
        mark=_ENTITY_MARKS.get(kind)
        if mark:
            spans.append((start,end,f'<{mark}>',f'</{mark}>'))
            continue
        if kind=='TEXT_LINK':
            url=str(getattr(entity,'url','') or '')
            if _HREF.match(url):spans.append((start,end,f'<a href="{_html.escape(url,quote=True)}">','</a>'))
            continue
        if kind=='CUSTOM_EMOJI':
            emoji_id=str(getattr(entity,'custom_emoji_id','') or '')
            fallback=text[start:end]
            if _EMOJI_ID.fullmatch(emoji_id) and fallback and len(fallback)<=8 and not re.search(r'\s',fallback):
                spans.append((start,end,f'<tg-emoji emoji-id="{emoji_id}">','</tg-emoji>'))
    if not spans:return text,False

    def build(start,end,pool):
        parts=[];cursor=start
        while cursor<end:
            candidate=None
            for span in pool:
                if span[0]<cursor or span[1]>end:continue
                if candidate is None or span[0]<candidate[0] or (span[0]==candidate[0] and span[1]>candidate[1]):candidate=span
            if candidate is None:break
            if candidate[0]>cursor:parts.append(_escape(text[cursor:candidate[0]]))
            inner=build(candidate[0],candidate[1],[span for span in pool if span is not candidate])
            if inner:parts.append(candidate[2]+inner+candidate[3])
            cursor=candidate[1]
        if cursor<end:parts.append(_escape(text[cursor:end]))
        return ''.join(parts)

    html=build(0,len(text),spans)
    normalized,_,_=normalize_rich(html)
    return normalized,bool(normalized!=_escape(text))


def is_rich(text):
    return bool(re.search(r'</?(?:b|i|u|s|code|pre|blockquote|a|tg-spoiler|tg-emoji)\b',str(text or '')))


def snapshot(message):
    chat=getattr(message,'chat',None)
    kind=str(getattr(getattr(chat,'type',None),'value',getattr(chat,'type','')))
    if kind not in {'group','supergroup','private'}:return None
    raw_text=str(getattr(message,'text',None) or getattr(message,'caption',None) or '')[:4096]
    entities=getattr(message,'entities',None) or getattr(message,'caption_entities',None) or []
    text,rich=False,False
    try:text,rich=entities_html(raw_text,entities)
    except Exception:text,rich=raw_text,False
    if not isinstance(text,str) or not text:text=raw_text
    media=None
    for key in ('photo','video','document','audio','voice','sticker','animation','video_note','poll'):
        item=getattr(message,key,None)
        if item:
            media={'kind':key,'name':str(getattr(item,'file_name','') or '')[:160],
                   'file_id':getattr(item,'file_id',None),'size':getattr(item,'file_size',None),
                   'mime':getattr(item,'mime_type',None)}
            break
    poll=None
    raw_poll=getattr(message,'poll',None)
    if raw_poll is not None:
        try:
            options=[str(getattr(option,'text',''))[:100] for option in (getattr(raw_poll,'options',None) or [])][:10]
            poll={'question':str(getattr(raw_poll,'question',''))[:300],'options':options,
                'anonymous':bool(getattr(raw_poll,'is_anonymous',True)),
                'multiple':bool(getattr(raw_poll,'allows_multiple_answers',False))}
        except Exception:poll=None
    if not text and media is None:return None
    user=getattr(message,'from_user',None)
    sender=user or getattr(message,'sender_chat',None)
    reply=getattr(message,'reply_to_message',None)
    return {'chat_id':chat.id,'chat_type':kind,'chat_title':str(getattr(chat,'title',None) or getattr(chat,'first_name',None) or getattr(sender,'first_name',None) or chat.id)[:100],'message_id':message.id,'text':text,'media':media,
        'sender_id':getattr(sender,'id',None),'sender_is_user':user is not None,
        'sender_name':str(getattr(sender,'first_name',None) or getattr(sender,'title',None) or 'Anonymous')[:100],
        'sender_username':str(getattr(sender,'username','') or '')[:64],
        'is_bot':bool(getattr(user,'is_bot',False)),
        'reply_to_id':getattr(reply,'id',None),'thread_id':getattr(message,'message_thread_id',None),'poll':poll,
        'date':aware(getattr(message,'date',None)),'edited':bool(getattr(message,'edit_date',None)),
        'deleted':False,'rich':bool(rich)}


_ALLOWED_RICH={'b','strong','i','em','u','ins','s','strike','del','code','pre','blockquote','a','tg-spoiler','tg-emoji'}
_ALIASES={'strong':'b','em':'i','ins':'u','strike':'s','del':'s'}
_BLOCK_TAGS={'p','div','section','article','tr','li','h1','h2','h3','h4','h5','h6'}
_TAG_TOKEN=re.compile(r'</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>')
_ATTRIBUTE=re.compile(r'([A-Za-z_][\w-]*)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)')
_EMOJI_ID=re.compile(r'^[0-9]{1,20}$')
_EMPTY_PAIR=re.compile(r'<([A-Za-z][\w-]*)((?:\s[^<>]*)?)></\1>')
_HREF=re.compile(r'^(?:https?://|tg://)',re.I)


def _escape(value):
    return value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')


def _decode(value):
    return _html.unescape(value)


def _attributes(raw):
    return {match.group(1).lower():_decode(match.group(2).strip('"\'')) for match in _ATTRIBUTE.finditer(raw)}


def _open_tag(name,attrs):
    if name=='a':return f'<a href="{_html.escape(attrs.get("href",""),quote=True)}">'
    if name=='tg-emoji':return f'<tg-emoji emoji-id="{attrs.get("emoji-id","")}">'
    return f'<{name}>'


_TAG_SHAPE=re.compile(r"<\s*(/?)\s*([A-Za-z][\w-]*)((?:\"[^\"]*\"|'[^']*'|[^<>])*?)\s*(/?)\s*>$",re.S)


def normalize_rich(value):
    """Rewrite arbitrary HTML-ish text into Telegram-safe, correctly nested HTML.

    Telegram only accepts well-formed nesting. Bold/italic/underline/strike/
    spoiler may nest with each other, but code/pre may not share characters with
    them, blockquotes cannot nest, and links cannot contain code. This parser
    closes and reopens formatting around code, flattens tags inside code, drops
    unknown tags while keeping their text, and auto-balances mismatched tags.
    Returns (html, plain_text, used_html).
    """
    if not isinstance(value,str):raise ViewError('A text message is required.')
    out=[];plain=[];stack=[];ignored={};code=None;emoji=None
    position=0

    def emit(text):out.append(text)

    def add_text(segment):
        if not segment:return
        decoded=_decode(segment)
        if not decoded:return
        plain.append(decoded)
        if code is not None:
            emit(_escape(decoded))
        elif emoji is not None:
            emoji['buffer'].append(decoded)
        else:
            emit(_escape(decoded))

    def newline():
        if not out or out[-1].endswith('\n'):return
        emit('\n');plain.append('\n')

    def close_emoji():
        nonlocal emoji
        if emoji is None:return
        content=''.join(emoji['buffer']).strip()
        if content and len(content)<=8 and not re.search(r'\s',content):
            emit(f'<tg-emoji emoji-id="{emoji["id"]}">{_escape(content)}</tg-emoji>')
        else:
            emit(_escape(''.join(emoji['buffer'])))
        emoji=None

    for match in _TAG_TOKEN.finditer(value):
        add_text(value[position:match.start()])
        position=match.end()
        shape=_TAG_SHAPE.match(match.group(0))
        if not shape:continue
        closing=bool(shape.group(1));name=shape.group(2).lower();attr_text=shape.group(3) or ''
        name=_ALIASES.get(name,name)
        if code is not None:
            if name in {'code','pre'} and closing:
                emit(f'</{code["name"]}>')
                saved=code['saved'];code=None
                for open_name,open_attrs in saved:emit(_open_tag(open_name,open_attrs))
            # Every other tag inside code is flattened; its text is kept.
            continue
        if name=='tg-emoji' and closing:
            close_emoji();continue
        if emoji is not None:
            # Tags inside a custom emoji are dropped; only its text matters.
            continue
        if closing:
            if ignored.get(name):
                ignored[name]-=1;continue
            if name in {'code','pre'} or name=='tg-emoji':
                continue
            if name not in {open_name for open_name,_ in stack}:
                continue
            while stack and stack[-1][0]!=name:
                emit(f'</{stack[-1][0]}>');stack.pop()
            if stack:
                emit(f'</{name}>');stack.pop()
            if name in _BLOCK_TAGS:newline()
            continue
        if name=='br':
            emit('\n');plain.append('\n');continue
        if name in _BLOCK_TAGS:
            newline();continue
        if name in {'code','pre'}:
            saved=[(open_name,open_attrs) for open_name,open_attrs in stack]
            for open_name,_ in reversed(saved):emit(f'</{open_name}>')
            code={'name':name,'saved':saved}
            emit(f'<{name}>')
            continue
        if name=='tg-emoji':
            attrs=_attributes(attr_text)
            eid=attrs.get('emoji-id','')
            if not _EMOJI_ID.fullmatch(eid):continue
            emoji={'id':eid,'buffer':[]}
            continue
        if name=='a':
            attrs=_attributes(attr_text)
            if not _HREF.match(attrs.get('href','')):
                ignored['a']=ignored.get('a',0)+1;continue
            if any(open_name=='a' for open_name,_ in stack):
                ignored['a']=ignored.get('a',0)+1;continue
        if name=='blockquote' and any(open_name=='blockquote' for open_name,_ in stack):
            ignored['blockquote']=ignored.get('blockquote',0)+1;continue
        if name in {'b','i','u','s','tg-spoiler'} and any(open_name==name for open_name,_ in stack):
            ignored[name]=ignored.get(name,0)+1;continue
        if name not in _ALLOWED_RICH:continue
        stack.append((name,_attributes(attr_text) if name=='a' else {}))
        emit(_open_tag(name,_attributes(attr_text)))
    add_text(value[position:])
    if emoji is not None:close_emoji()
    if code is not None:
        emit(f'</{code["name"]}>')
        for open_name,open_attrs in code['saved']:emit(_open_tag(open_name,open_attrs))
        code=None
    while stack:
        emit(f'</{stack[-1][0]}>');stack.pop()
    html=''.join(out).rstrip('\n')
    for _ in range(6):
        cleaned=_EMPTY_PAIR.sub('',html)
        if cleaned==html:break
        html=cleaned
    used=bool(re.search(r'</?(?:b|i|u|s|code|pre|blockquote|a|tg-spoiler|tg-emoji)\b',html))
    return html,''.join(plain).rstrip('\n'),used


def plain_from_rich(value):
    """Visible text of stored Telegram-style HTML, for safe fallback sends."""
    html,plain,used=normalize_rich(value)
    return plain if used else value


def rich_text(text,limit=4096):
    """Validate and normalize Telegram HTML; returns (text,is_html).

    Plain text is returned unchanged. Formatting is normalized to Telegram's
    documented nesting rules, unknown tags are dropped, unsafe links and emoji
    IDs are rejected, and the visible UTF-16 length is enforced.
    """
    if not isinstance(text,str) or not text.strip():
        raise ViewError(f'Enter a message of 1–{limit} Telegram text units.')
    has=bool(re.search(r'<[A-Za-z/!]',text))
    if not has:
        if len(text.encode('utf-16-le'))//2>limit:
            raise ViewError(f'Enter a message of 1–{limit} Telegram text units.')
        return text,False
    for tag in re.findall(r'<tg-emoji[^>]*>',text,re.I):
        attrs=_attributes(tag[1:-1])
        if not _EMOJI_ID.fullmatch(attrs.get('emoji-id','')):
            raise ViewError('Premium emoji ID must be 1–20 digits. Copy it from @emoji or Telegram.')
    html,plain,used=normalize_rich(text)
    if not plain.strip():
        raise ViewError('A formatted message needs visible text outside its tags.')
    if len(plain.encode('utf-16-le'))//2>limit:
        raise ViewError(f'Formatted messages are limited to {limit} Telegram text units. Shorten the visible text.')
    if len(html)>min(20000,limit*8):
        raise ViewError('Formatted message is too large.')
    if not used:return plain,False
    return html,True


def indexes(db):
    db['group_view_messages'].create_index([('chat_id',1),('message_id',-1)],unique=True)
    db['group_view_messages'].create_index('expires_at',expireAfterSeconds=0)
    db['group_view_operations'].create_index('expires_at',expireAfterSeconds=0)


def store(db,item):
    if item.get('chat_type') in {'private','group','supergroup'}:
        db['bot_inbox_peers'].update_one({'_id':item['chat_id']},{'$set':{'title':item.get('chat_title',str(item['chat_id'])),'type':item['chat_type'],'seen_at':now()}},upsert=True)
    settings=db['group_view_settings'].find_one({'_id':item['chat_id']}) or {}
    if not settings.get('enabled'):return
    # Ignore queued pre-consent updates, including edits of old messages.
    if item['date']<aware(settings.get('enabled_at')):return
    days=settings.get('retention_days',7)
    if days not in RETENTION:days=7
    if item['date']<now()-timedelta(days=days):return
    epoch=settings.get('epoch')
    document={**item,'expires_at':item['date']+timedelta(days=days),'epoch':epoch}
    # Bot replies are stored as the HTML that was actually delivered, so mark
    # them textually so the viewer renders them instead of escaping the tags.
    if 'rich' not in document:document['rich']=is_rich(document.get('text'))
    key={'chat_id':item['chat_id'],'message_id':item['message_id']}
    # Preserve a local deletion marker if a late edit arrives.
    if (db['group_view_messages'].find_one(key) or {}).get('deleted'):return
    db['group_view_messages'].update_one(key,{'$set':document},upsert=True)
    current=db['group_view_settings'].find_one({'_id':item['chat_id']}) or {}
    if not current.get('enabled') or current.get('epoch')!=epoch:
        db['group_view_messages'].delete_one({**key,'epoch':epoch})


_queue=None
_worker_task=None
_dropped=0


async def capture(client,message):
    """Never await Mongo in Telegram dispatch; a bounded worker drops on overload."""
    global _queue,_worker_task,_dropped
    item=snapshot(message)
    if item is None:return
    if _queue is None:_queue=asyncio.Queue(maxsize=500)
    if _worker_task is None or _worker_task.done():_worker_task=asyncio.create_task(_worker())
    try:_queue.put_nowait(item)
    except asyncio.QueueFull:
        _dropped+=1
        if _dropped==1 or _dropped%100==0:log.warning('Group viewer capture queue full; %s snapshots dropped',_dropped)


async def _worker():
    from videl.utils.db import get_db
    ready=None
    while True:
        item=await _queue.get()
        try:
            db=get_db()
            if db is not None:
                if db is not ready:await asyncio.to_thread(indexes,db);ready=db
                await asyncio.to_thread(store,db,item)
        except Exception as error:log.warning('Group snapshot unavailable (%s)',type(error).__name__)
        finally:_queue.task_done()


class GroupView:
    #: Actions that stay with the bot owner even though a group admin could
    #: otherwise reach them. Importing a backup overwrites protection state;
    #: recording starts capturing member messages; purging destroys evidence.
    OWNER_ONLY={'backup_import','backup_restore','backup_snapshot','backup_list','recording','purge_history'}

    def __init__(self,db,api,actor=OWNER_ID,scope='owner'):
        if db is None:raise ViewError('MongoDB is not connected.',503)
        self.db=db;self.api=api
        self.actor=int(actor)
        self.scope='admin' if scope=='admin' else 'owner'

    def call(self,method,payload):
        status,body=self.api(method,payload)
        if status==400:
            raise TelegramError(body.get('description',''),400)
        if not status or not body.get('ok') or body.get('result') is False:
            raise ViewError('Telegram did not confirm this request. Check the group before retrying.',502)
        return body.get('result')

    def access(self,chat_id):
        cid=integer(chat_id)
        if cid>0:
            if self.db['bot_inbox_peers'].find_one({'_id':cid,'type':'private'}) is None:raise ViewError('This user has not opened a bot DM since inbox tracking began.',404)
            return cid,{'status':'bot_dm'}
        if cid==0 or self.db['served_chats'].find_one({'_id':cid}) is None:
            raise ViewError('Choose a group already served by this bot.',404)
        actor=self.call('getChatMember',{'chat_id':cid,'user_id':self.actor})
        if actor.get('status') not in {'creator','administrator'}:
            who='You must' if self.scope=='admin' else 'The owner account must'
            raise ViewError(f'{who} currently be a group administrator to view or manage it.',403)
        return cid,actor

    def rights(self,cid,actor,required):
        me=self.call('getMe',{})
        if cid>0:
            if required:raise ViewError('Group moderation is not available in a bot DM.',403)
            return me
        # Ordinary bot messages do not require bot admin status. Telegram checks
        # current send restrictions; only moderation demands specific admin rights.
        if not required:return me
        member=self.call('getChatMember',{'chat_id':cid,'user_id':me['id']})
        for label,person in [('Your account',actor),('The bot',member)]:
            if person.get('status')=='creator':continue
            if person.get('status')!='administrator' or any(not person.get(key) for key in required):
                raise ViewError(f'{label} lacks the required group permission: '+', '.join(required)+'.',403)
        return me

    def read(self,chat_id,*,before=None,query='',sender=None):
        cid,actor=self.access(chat_id)
        settings=self.db['group_view_settings'].find_one({'_id':cid}) or {}
        days=settings.get('retention_days',7)
        if days not in RETENTION:days=7
        criteria={'chat_id':cid,'expires_at':{'$gt':now()},'date':{'$gte':now()-timedelta(days=days)}}
        if before is not None:criteria['message_id']={'$lt':integer(before,positive=True)}
        query=str(query or '').strip()
        if len(query)>80:raise ViewError('Search is limited to 80 characters.')
        if query:criteria['text']={'$regex':re.escape(query),'$options':'i'}
        if sender is not None:criteria['sender_id']=integer(sender,positive=True)
        docs=list(self.db['group_view_messages'].find(criteria,{'_id':0,'epoch':0}).sort('message_id',-1).limit(51))
        has_more=len(docs)>50;docs=docs[:50]
        for doc in docs:
            if doc.get('media'):doc['media']={key:value for key,value in doc['media'].items() if key!='file_id'}
            for key in ('date','expires_at'):
                if isinstance(doc.get(key),datetime):doc[key]=aware(doc[key]).isoformat()
        protections=self.db['mgmt_chat_settings'].find_one({'chat_id':cid}) or {}
        return {'ok':True,'chat_id':cid,'items':list(reversed(docs)),'has_more':has_more,
            'next_before':docs[-1]['message_id'] if docs else None,
            'is_private':cid>0,'recording':bool(settings.get('enabled')),'retention_days':days,
            'capture_dropped':_dropped,'rich_text':True,'revision':self.revision(cid),
            'settings':{key:bool(protections.get(key,False)) for key in PROTECTION},
            'visibility_note':'Only messages delivered to this bot after recording was enabled. No Telegram history import; privacy mode can limit visibility. Small photos, videos and voice messages can be viewed through the owner-only media proxy. Unobserved deletions are not synchronized.'}

    def info(self,chat_id):
        """Chat profile, like a Telegram chat info screen (allowlisted fields)."""
        cid,actor=self.access(chat_id)
        me=self.call('getMe',{})
        chat=self.call('getChat',{'chat_id':cid}) or {}
        if not isinstance(chat,dict):raise ViewError('Telegram did not return this chat.',502)
        members=None
        if cid<0:
            try:members=self.call('getChatMemberCount',{'chat_id':cid})
            except ViewError:members=None
        if not isinstance(members,int) or members<0:members=None
        pinned=self._pinned(chat)
        bot_member=None
        if cid<0:
            try:bot_member=self.call('getChatMember',{'chat_id':cid,'user_id':me['id']})
            except ViewError:bot_member=None
        settings=self.db['group_view_settings'].find_one({'_id':cid}) or {}
        days=settings.get('retention_days',7)
        if days not in RETENTION:days=7
        protections=self.db['mgmt_chat_settings'].find_one({'chat_id':cid}) or {}
        photo=chat.get('photo') if isinstance(chat.get('photo'),dict) else {}
        base={'id':cid,'title':str(chat.get('title') or chat.get('first_name') or chat.get('username') or cid)[:128],
            'type':str(chat.get('type') or ('private' if cid>0 else 'supergroup'))[:20],
            'username':str(chat.get('username') or '')[:64] or None,
            'first_name':str(chat.get('first_name') or '')[:64] or None,
            'description':str(chat.get('description') or chat.get('bio') or '')[:600] or None,
            'member_count':members,'has_photo':bool(photo.get('small_file_id')),
            'is_forum':bool(chat.get('is_forum')),'slow_mode_delay':int(chat.get('slow_mode_delay') or 0),
            'linked_chat_id':chat.get('linked_chat_id'),'pinned':pinned,
            'recording':bool(settings.get('enabled')),'retention_days':days,
            'protections':{key:bool(protections.get(key,False)) for key in PROTECTION}}
        if cid<0:
            allowed=chat.get('permissions') if isinstance(chat.get('permissions'),dict) else {}
            base['permissions']={key:bool(allowed.get(key)) for key in
                ('can_send_messages','can_send_photos','can_send_videos','can_send_polls','can_send_other_messages','can_add_web_page_previews')}
            member_status=(bot_member or {}).get('status')
            base['bot']={'name':str((me or {}).get('first_name') or 'Videl')[:64],
                'username':str((me or {}).get('username') or '')[:64] or None,
                'status':member_status if member_status in {'creator','administrator','member','restricted','left','kicked'} else None,
                'is_admin':member_status in {'creator','administrator'},
                'can_manage':bool((bot_member or {}).get('can_manage_chat')) if member_status=='administrator' else False,
                'can_delete_messages':bool((bot_member or {}).get('can_delete_messages')) if member_status=='administrator' else False,
                'can_restrict_members':bool((bot_member or {}).get('can_restrict_members')) if member_status=='administrator' else False,
                'can_invite_users':bool((bot_member or {}).get('can_invite_users')) if member_status=='administrator' else False}
            base['owner']={'status':actor.get('status') if actor.get('status') in {'creator','administrator','member','restricted','left','kicked'} else None}
        invite=None
        if cid<0:
            try:invite=self.call('exportChatInviteLink',{'chat_id':cid})
            except ViewError:invite=None
            if not isinstance(invite,str) or not invite.startswith('https://t.me/'):invite=None
        base['invite_link']=invite
        return {'ok':True,'info':base,'rich_text':True}

    @staticmethod
    def _pinned(chat):
        raw=chat.get('pinned_message')
        if not isinstance(raw,dict):return None
        text=raw.get('text') or raw.get('caption') or ''
        return {'message_id':raw.get('message_id'),'text':str(text)[:280],
            'date':aware(raw.get('date')).isoformat() if raw.get('date') else None}

    def photo(self,chat_id):
        """Profile photo of a chat the bot can read, streamed by the owner proxy."""
        cid,_=self.access(chat_id)
        chat=self.call('getChat',{'chat_id':cid}) or {}
        picture=chat.get('photo') if isinstance(chat,dict) and isinstance(chat.get('photo'),dict) else {}
        file_id=picture.get('small_file_id') or picture.get('big_file_id')
        if not file_id:raise ViewError('This chat has no profile photo.',404)
        from videl.utils.premium_emoji import EmojiError,fetch_file
        try:return fetch_file(self.api,file_id)
        except EmojiError as error:raise ViewError(str(error),error.status) from None

    def snapshot(self,chat_id):
        """Typed view of every setting the admin surface may change."""
        document=self.db['mgmt_chat_settings'].find_one({'chat_id':chat_id}) or {}
        snapshot={key:coerce_bool(document.get(key,SETTING_DEFAULTS.get(key,False))) for key in BOOL_SETTINGS}
        for key,(low,high) in INT_SETTINGS.items():
            try:value=int(document.get(key,INT_DEFAULTS.get(key,low)))
            except (TypeError,ValueError):value=INT_DEFAULTS.get(key,low)
            snapshot[key]=max(low,min(value,high))
        for key in TEXT_SETTINGS:snapshot[key]=str(document.get(key) or '')
        for key,allowed in ENUM_SETTINGS.items():
            value=document.get(key)
            snapshot[key]=value if value in allowed else 'del'
        return snapshot

    # ── concurrent edits ─────────────────────────────────────────────────────
    def revision(self,chat_id):
        """Counter for owner-facing writes, so a stale panel edit is refused."""
        return settings_store.revision(chat_id,self.db)

    @staticmethod
    def _expected(body):
        """The revision a panel write was based on; None means "Do not check".

        Bot-side callers (Telegram commands, imports) do not track revisions;
        they still advance the counter, so an open panel notices afterwards.
        """
        value=body.get('revision') if isinstance(body,dict) else None
        if value is None:return None
        if type(value) is not int or not 0<=value<=9007199254740991:
            raise ViewError('A settings revision must be a non-negative integer.')
        return value

    def _stale(self,error):
        """A 409 that carries the revision the panel should reload from."""
        conflict=ViewError(str(error),409)
        conflict.conflict=True
        conflict.revision=error.revision
        return conflict

    def _write_settings(self,cid,values,body=None):
        try:
            return settings_store.write(cid,values,expected=self._expected(body),db=self.db)
        except settings_store.SettingsConflict as error:
            raise self._stale(error) from None

    def describe(self,chat_id):
        """Everything the group manager needs, in one permission-checked read."""
        cid=integer(chat_id)
        if cid>0:raise ViewError('Group management is group-only.',403)
        if self.db['served_chats'].find_one({'_id':cid}) is None:
            raise ViewError('Choose a group already served by this bot.',404)
        problems=[]
        try:info=self.info(cid)['info']
        except ViewError as error:
            problems.append(str(error))
            info={'id':cid,'title':f'Telegram chat {cid}','type':'unknown','username':None,'member_count':None,
                  'has_photo':False,'description':None,'is_forum':False,'slow_mode_delay':0,'permissions':{},
                  'bot':{'is_admin':False,'status':None},'owner':{'status':None},'available':False}
        info['available']=not problems
        try:
            notes=list(self.db['mgmt_notes'].find({'chat_id':cid},{'_id':0,'name':1,'type':1}).limit(60))
            filters=list(self.db['mgmt_filters'].find({'chat_id':cid},{'_id':0,'keyword':1,'reply':1}).limit(60))
            from videl.utils.custom_commands import list_for as list_custom_commands
            custom_commands=list_custom_commands(self.db,cid)
        except Exception:
            notes,filters,custom_commands=[],[],[]
        try:blacklist=list(self.db['blacklist'].find({'chat':cid},{'_id':0,'trigger':1,'mode':1}).limit(120))
        except Exception:blacklist=[]
        try:approved=[int(item) for item in self.db['approved'].distinct('user',{'chat':cid})][:120]
        except Exception:approved=[]
        try:disabled=[str(item.get('cmd','')) for item in self.db['disabled_cmds'].find({'chat':cid},{'_id':0,'cmd':1}).limit(80)]
        except Exception:disabled=[]
        from videl.utils.db import get_automation,list_warns,get_warn_limit
        decay=int((get_automation(cid).get('escalation') or {}).get('decay_days') or 0)
        try:warns=list_warns(cid,100,decay_days=decay)
        except Exception:warns=[]
        try:automation=get_automation(cid)
        except Exception:automation=normalize({})
        current_settings=self.snapshot(cid)
        required_rights=info.get('bot') or {}
        protection_keys=[key for key in current_settings if key.startswith('lock_')]
        protected=any(bool(current_settings.get(key)) for key in protection_keys) or bool(current_settings.get('antispam'))
        onboarding_ready=bool(current_settings.get('captcha_enabled') or current_settings.get('welcome_message') or current_settings.get('rules'))
        setup_checklist=[
            {'id':'bot_admin','label':'Bot is a group administrator','complete':bool(required_rights.get('is_admin')),
             'detail':'Needed for reliable group management.'},
            {'id':'delete_messages','label':'Bot can delete messages','complete':bool(required_rights.get('can_delete_messages')),
             'detail':'Needed for content locks and anti-flood enforcement.'},
            {'id':'restrict_members','label':'Bot can restrict members','complete':bool(required_rights.get('can_restrict_members')),
             'detail':'Needed for mutes, bans and join verification.'},
            {'id':'protection','label':'At least one protection is configured','complete':protected,
             'detail':'Enable a suitable content lock or anti-flood rule for this group.'},
            {'id':'onboarding','label':'Welcome, rules or join verification is configured','complete':onboarding_ready,
             'detail':'Set a welcome message, publish rules or enable the CAPTCHA challenge.'},
        ]
        try:cases=self.case_history(cid)
        except Exception:cases=[]
        return {'ok':True,'scope':self.scope,'chat':info,'settings':current_settings,'presets':PRESETS,
                'revision':self.revision(cid),'automation':automation,'cases':cases,
                'setup_checklist':setup_checklist,
                'inbox':self.inbox(cid),
                'community':{
                    'warns':warns,'warn_limit':get_warn_limit(cid),
                    'notes':[{'name':str(item.get('name','')),'type':str(item.get('type','text'))} for item in notes],
                    'filters':[{'keyword':str(item.get('keyword','')),'reply':str(item.get('reply',''))[:160]} for item in filters],
                    'custom_commands':custom_commands,
                    'blacklist':[{'trigger':str(item.get('trigger','')),'mode':str(item.get('mode','del'))} for item in blacklist],
                    'approved':approved,'disabled_commands':disabled,
                },
                'problems':problems}

    # ── audit trail ──────────────────────────────────────────────────────────
    AUDIT_KINDS={'settings':'settings','protect':'settings','preset':'preset','warn_limit':'warn_limit',
        'welcome':'welcome','goodbye':'goodbye','rules':'rules','blacklist_add':'blacklist',
        'blacklist_remove':'blacklist','blacklist_mode':'blacklist_mode','note_delete':'note',
        'filter_delete':'filter','filter_create':'filter','custom_command_create':'commands','custom_command_delete':'commands','note_create':'note','approved_remove':'approval','warn_reset':'warn_reset',
        'automation':'automation','command_disable':'commands','command_enable':'commands','backup_import':'backup','backup_restore':'backup','backup_snapshot':'backup',
        'join_request':'join_request','report_update':'report','case_note':'moderation','escalation_review':'escalation','member_action':'moderation','invite_link':'invite','recording':'recording','purge_history':'purge'}

    @staticmethod
    def _audit_value(value):
        if type(value) is bool:return 'on' if value else 'off'
        if value is None:return 'unset'
        if isinstance(value,str):return f'{len(value)} chars'
        if isinstance(value,(int,float)):return str(value)[:32]
        if isinstance(value,(list,tuple,set)):return f'{len(value)} items'
        return 'changed'

    def log(self,cid,action,body=None,source='web',before=None,after=None):
        """Record a successful change and privacy-safe before/after values."""
        body=body if isinstance(body,dict) else {}
        try:detail=audit_detail(action,body)
        except Exception:detail=''
        if isinstance(before,dict) and isinstance(after,dict):
            def flatten(value,prefix=''):
                output={}
                if isinstance(value,dict):
                    for key,item in value.items():
                        child=f'{prefix}.{key}' if prefix else str(key)
                        output.update(flatten(item,child))
                else:output[prefix]=value
                return output
            old_values,new_values=flatten(before),flatten(after)
            differences=[]
            for key in sorted(set(old_values)&set(new_values)):
                if old_values[key]!=new_values[key]:
                    differences.append(f'{key}: {self._audit_value(old_values[key])} → {self._audit_value(new_values[key])}')
            if differences:
                detail=(detail+'; ' if detail else '')+'previous/current: '+', '.join(differences[:5])
        try:audit_log.record(self.db,cid,self.AUDIT_KINDS.get(action,'settings'),action=action,
            detail=detail,actor=self.actor,source=source)
        except Exception:log.debug('audit record failed',exc_info=True)

    def events(self,chat_id,*,limit=40,kind=None,before=None,before_id=None,query=None,actor=None,after=None,until=None):
        # History lives in MongoDB, so it stays readable even when Telegram no
        # longer answers for the chat — that is exactly when it is needed.
        cid=integer(chat_id)
        if cid>0:raise ViewError('Audit history is group-only.',403)
        if self.db['served_chats'].find_one({'_id':cid}) is None:
            raise ViewError('Choose a group already served by this bot.',404)
        # Ask for one extra row so the panel knows whether an older page exists
        # without trusting an empty page to mean "end of history".
        rows=audit_log.recent(self.db,cid,limit=limit+1,kind=kind,before=before,
                              before_id=before_id,query=query,actor=actor,
                              after=after,until=until)
        return {'ok':True,'kind':kind or 'all','query':query or '','actor':actor,
                'kinds':list(audit_log.KINDS),
                'events':rows[:limit],'has_more':len(rows)>limit}

    # ── portable backup ──────────────────────────────────────────────────────
    # A backup is plain JSON the owner can keep. It is deliberately limited to
    # settings the bot reads: locks, automation, blacklist words and disabled
    # commands. Warnings, notes and filters stay out — they are member data,
    # not configuration, and a file like this gets copied between groups.
    BACKUP_FORMAT = 'videl-group-backup'
    BACKUP_VERSION = 1
    BACKUP_BLACKLIST_LIMIT = 300
    BACKUP_COMMAND_LIMIT = 200

    def export_group(self, chat_id):
        cid = integer(chat_id)
        if cid > 0:
            raise ViewError('Group backups are group-only.', 403)
        if self.db['served_chats'].find_one({'_id': cid}) is None:
            raise ViewError('Choose a group already served by this bot.', 404)
        from videl.utils.db import get_automation
        try:
            title = str((self.info(cid)['info'] or {}).get('title') or '')
        except Exception:
            title = ''
        try:
            blacklist = [{'trigger': str(row.get('trigger') or '')[:64],
                          'mode': str(row.get('mode') or 'del')}
                         for row in self.db['blacklist'].find({'chat': cid}, {'_id': 0})
                         .limit(self.BACKUP_BLACKLIST_LIMIT)]
        except Exception:
            blacklist = []
        try:
            commands = sorted({str(name) for name in
                               self.db['disabled_cmds'].distinct('cmd', {'chat': cid})})[:self.BACKUP_COMMAND_LIMIT]
        except Exception:
            commands = []
        return {'ok': True, 'backup': {
            'format': self.BACKUP_FORMAT,
            'version': self.BACKUP_VERSION,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'group': {'id': cid, 'title': title[:120]},
            'source_revision': _revision(),
            'settings': self.snapshot(cid),
            'automation': get_automation(cid),
            'blacklist': [row for row in blacklist if row['trigger']],
            'commands_disabled': commands,
        }}

    def save_snapshot(self, chat_id, body):
        cid = integer(chat_id)
        if cid > 0:
            raise ViewError('Group snapshots are group-only.', 403)
        label = str((body or {}).get('label') or '').strip()
        if not label or len(label) > 60:
            raise ViewError('Give this snapshot a name between 1 and 60 characters.')
        from videl.utils.db import save_backup
        document = self.export_group(cid)['backup']
        identifier = save_backup(cid, document, label=label)
        if not identifier:
            raise ViewError('The snapshot could not be saved. Check the database connection and retry.', 503)
        self.log(cid, 'backup_snapshot', {'label': label})
        return {'ok': True, 'snapshot': {'id': identifier, 'label': label, 'kind': 'named', 'time': now()},
                'snapshots': self.list_snapshots(cid)['snapshots']}

    def list_snapshots(self, chat_id):
        cid = integer(chat_id)
        if cid > 0:
            raise ViewError('Group snapshots are group-only.', 403)
        from videl.utils.db import list_backups
        rows = list_backups(cid, 12)
        return {'ok': True, 'snapshots': [
            {'id': str(row.get('_id') or ''),
             'label': str(row.get('label') or ('Before last import' if row.get('kind') != 'named' else 'Saved snapshot'))[:60],
             'kind': str(row.get('kind') or 'automatic'),
             'time': row.get('time')}
            for row in rows
        ]}

    def _read_backup(self, payload):
        """Accept only the documented shape; unknown keys are ignored, not applied."""
        document = payload.get('backup') if isinstance(payload, dict) and isinstance(payload.get('backup'), dict) else payload
        if not isinstance(document, dict):
            raise ViewError('Upload a Videl group backup JSON file.')
        if document.get('format') != self.BACKUP_FORMAT:
            raise ViewError('This file is not a Videl group backup.')
        try:
            version = int(document.get('version'))
        except (TypeError, ValueError):
            version = 0
        if version != self.BACKUP_VERSION:
            raise ViewError(f'Backup version {version or "unknown"} is not supported by this backend.')
        raw_settings = document.get('settings')
        if not isinstance(raw_settings, dict):
            raise ViewError('The backup has no settings block.')
        settings = {}
        for key, value in raw_settings.items():
            if key in BOOL_SETTINGS and type(value) is bool:
                settings[key] = value
            elif key in INT_SETTINGS and not isinstance(value, bool):
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                low, high = INT_SETTINGS[key]
                settings[key] = max(low, min(number, high))
            elif key in TEXT_SETTINGS and isinstance(value, str):
                settings[key] = value[:TEXT_SETTINGS[key]]
            elif key in ENUM_SETTINGS and value in ENUM_SETTINGS[key]:
                settings[key] = value
        if not settings:
            raise ViewError('The backup settings block contains nothing this bot can apply.')
        automation = normalize(document.get('automation') if isinstance(document.get('automation'), dict) else {})
        blacklist, seen = [], set()
        for row in (document.get('blacklist') or [])[:self.BACKUP_BLACKLIST_LIMIT]:
            if not isinstance(row, dict):
                continue
            trigger = str(row.get('trigger') or '').strip().casefold()[:64]
            if not trigger or trigger in seen:
                continue
            seen.add(trigger)
            mode = str(row.get('mode') or 'del')
            blacklist.append({'trigger': trigger,
                              'mode': mode if mode in ENUM_SETTINGS['blacklist_mode'] else 'del'})
        commands = []
        for item in (document.get('commands_disabled') or [])[:self.BACKUP_COMMAND_LIMIT]:
            name = str(item or '').strip().lower()
            if re.fullmatch(r'[a-z0-9_]{1,32}', name) and name not in commands:
                commands.append(name)
        return settings, automation, blacklist, commands

    def _backup_changes(self, cid, settings, automation, blacklist, commands):
        current = self.snapshot(cid)
        changed = {key: value for key, value in settings.items() if current.get(key) != value}
        before = {key: current.get(key) for key in changed}
        from videl.utils.db import get_automation
        live_automation = get_automation(cid)
        automation_changed = [key for key in ('quiet_hours', 'escalation', 'protection')
                              if automation.get(key) != live_automation.get(key)]
        try:
            live_words = {str(row.get('trigger') or '') for row in self.db['blacklist'].find({'chat': cid})}
        except Exception:
            live_words = set()
        wanted_words = {row['trigger'] for row in blacklist}
        try:
            live_commands = {str(name) for name in self.db['disabled_cmds'].distinct('cmd', {'chat': cid})}
        except Exception:
            live_commands = set()
        wanted_commands = set(commands)
        return {
            'settings': {'before': before, 'after': changed},
            'automation': automation_changed,
            'blacklist': {'add': sorted(wanted_words - live_words),
                          'remove': sorted(live_words - wanted_words)},
            'commands': {'disable': sorted(wanted_commands - live_commands),
                         'enable': sorted(live_commands - wanted_commands)},
        }

    def _apply_backup(self, cid, settings, automation, blacklist, commands, expected=None, sections=None):
        from videl.utils.db import disable_cmd, enable_cmd, set_automation
        # Check once, up front: an import writes settings and automation in two
        # steps, so a per-write guard would conflict with its own first write.
        try:
            settings_store.check(cid, expected, self.db)
        except settings_store.SettingsConflict as error:
            raise self._stale(error) from None
        sections = set(sections or {'settings','automation','blacklist','commands'})
        if 'settings' in sections and settings:
            settings_store.write(cid, settings, db=self.db)
        if 'automation' in sections:
            set_automation(cid, quiet_hours=automation['quiet_hours'],
                           escalation=automation['escalation'], protection=automation['protection'])
        if 'blacklist' in sections:
            wanted = {row['trigger'] for row in blacklist}
            try:
                self.db['blacklist'].delete_many({'chat': cid, 'trigger': {'$nin': sorted(wanted)}})
                for row in blacklist:
                    self.db['blacklist'].update_one(
                        {'chat': cid, 'trigger': row['trigger']},
                        {'$set': {'chat': cid, 'trigger': row['trigger'], 'mode': row['mode']}},
                        upsert=True)
            except Exception:
                log.debug('blacklist restore partially failed', exc_info=True)
        if 'commands' in sections:
            wanted_commands = set(commands)
            try:
                live_commands = {str(name) for name in self.db['disabled_cmds'].distinct('cmd', {'chat': cid})}
            except Exception:
                live_commands = set()
            for name in sorted(wanted_commands - live_commands):
                disable_cmd(cid, name)
            for name in sorted(live_commands - wanted_commands):
                enable_cmd(cid, name)

    def import_group(self, chat_id, actor, body, *, source='web'):
        """Dry-run by default: the panel previews a diff, then confirms."""
        cid = integer(chat_id)
        if cid > 0:
            raise ViewError('Group backups are group-only.', 403)
        if self.db['served_chats'].find_one({'_id': cid}) is None:
            raise ViewError('Choose a group already served by this bot.', 404)
        body = body if isinstance(body, dict) else {}
        allowed_sections={'settings','automation','blacklist','commands'}
        raw_sections=body.get('sections')
        if raw_sections is None:
            sections=set(allowed_sections)
        elif isinstance(raw_sections,list) and all(isinstance(item,str) for item in raw_sections):
            sections=set(raw_sections)
            if not sections or not sections<=allowed_sections:
                raise ViewError('Choose one or more valid configuration sections.')
        else:
            raise ViewError('Configuration sections must be a list.')
        settings, automation, blacklist, commands = self._read_backup(body.get('document') or body)
        from videl.utils.db import get_automation
        if 'settings' not in sections:settings={}
        if 'automation' not in sections:automation=get_automation(cid)
        if 'blacklist' not in sections:
            try:blacklist=[{'trigger':str(row.get('trigger') or ''),'mode':str(row.get('mode') or 'del')}
                           for row in self.db['blacklist'].find({'chat':cid}) if row.get('trigger')]
            except Exception:blacklist=[]
        if 'commands' not in sections:
            try:commands=sorted({str(name) for name in self.db['disabled_cmds'].distinct('cmd',{'chat':cid})})
            except Exception:commands=[]
        changes = self._backup_changes(cid, settings, automation, blacklist, commands)
        empty = not (changes['settings']['after'] or changes['automation']
                     or changes['blacklist']['add'] or changes['blacklist']['remove']
                     or changes['commands']['disable'] or changes['commands']['enable'])
        if body.get('dry_run') is not False:
            return {'ok': True, 'dry_run': True, 'empty': empty, 'changes': changes}
        if empty:
            return {'ok': True, 'dry_run': False, 'empty': True, 'changes': changes,
                    'settings': self.snapshot(cid), 'backup_id': None}
        # Keep the state being replaced: an import is a bulk change and must be
        # reversible even when the uploaded file was made for another group.
        from videl.utils.db import save_backup
        previous = self.export_group(cid)['backup']
        previous['exported_at'] = datetime.now(timezone.utc).isoformat()
        backup_id = save_backup(cid, previous) or None
        self._apply_backup(cid, settings, automation, blacklist, commands,
                           expected=self._expected(body), sections=sections)
        summary = []
        if changes['settings']['after']:
            summary.append(f"{len(changes['settings']['after'])} settings")
        if changes['automation']:
            summary.append(', '.join(changes['automation']))
        if changes['blacklist']['add'] or changes['blacklist']['remove']:
            summary.append(f"blacklist +{len(changes['blacklist']['add'])}/-{len(changes['blacklist']['remove'])}")
        if changes['commands']['disable'] or changes['commands']['enable']:
            summary.append(f"commands +{len(changes['commands']['disable'])}/-{len(changes['commands']['enable'])}")
        audit_log.record(self.db, cid, 'backup', action='backup_import',
                         detail='restored: ' + '; '.join(summary), actor=OWNER_ID, source=source)
        return {'ok': True, 'dry_run': False, 'empty': False, 'changes': changes,
                'backup_id': backup_id, 'settings': self.snapshot(cid),
                'automation': self._automation_read(cid)}

    def restore_saved(self, chat_id, actor, body, *, source='web'):
        """Undo an import using the snapshot it stored server-side."""
        cid = integer(chat_id)
        if cid > 0:
            raise ViewError('Group backups are group-only.', 403)
        identifier = str((body or {}).get('backup_id') or '').strip()
        if not identifier or not re.fullmatch(r'[0-9a-f]{1,32}', identifier):
            raise ViewError('A saved backup id is required.')
        from videl.utils.db import get_backup
        row = get_backup(identifier)
        if not row or int(row.get('chat') or 0) != cid:
            raise ViewError('That saved snapshot no longer exists for this group.', 404)
        document = row.get('data')
        if not isinstance(document, dict):
            raise ViewError('That saved snapshot is unreadable.', 409)
        request = {'document': document, 'dry_run': False}
        if isinstance(body, dict) and 'revision' in body:
            request['revision'] = body.get('revision')
        return self.import_group(cid, actor, request, source=source)

    def _automation_read(self, cid):
        from videl.utils.db import get_automation
        try:
            return get_automation(cid)
        except Exception:
            return normalize({})

    # ── per-member case timeline ────────────────────────────────────────────
    def case_history(self,cid,*,limit=40):
        """Merge warnings, reports, moderator actions and case notes by member."""
        cid=integer(cid)
        if cid>0:raise ViewError('Case history is group-only.',403)
        grouped={}
        open_reports={}
        def add(user_id,kind,action,detail,at,actor=None,source='bot',event_id=''):
            try:user_id=int(user_id)
            except (TypeError,ValueError):return
            if user_id<=0:return
            when=case_timestamp(at)
            event={'id':str(event_id or f'{kind}:{user_id}:{len(grouped.get(user_id,[]))}'),
                   'kind':str(kind)[:32],'action':str(action)[:48],
                   'detail':str(detail or '')[:400],'at':when,'actor':actor if isinstance(actor,int) else None,
                   'source':str(source)[:16]}
            grouped.setdefault(user_id,[]).append(event)

        try:
            for doc in self.db['mgmt_warnings'].find({'chat_id':cid}).sort('updated',-1).limit(80):
                user=doc.get('user_id')
                for index,item in enumerate((doc.get('reasons') or [])[-30:]):
                    if isinstance(item,dict):reason=item.get('reason') or 'Warning issued';stamp=item.get('ts') or doc.get('updated')
                    else:reason=str(item or 'Warning issued');stamp=doc.get('updated')
                    add(user,'warning','warn',reason,stamp,source='bot',event_id=f"warn:{user}:{index}")
        except Exception:pass
        try:
            for row in self.db['mgmt_reports'].find({'chat_id':cid}).sort('ts',-1).limit(120):
                target=row.get('target',row.get('target_id'))
                report_id=str(row.get('_id') or '')
                if str(row.get('status') or 'open')=='open':
                    try:open_reports[int(target)]=open_reports.get(int(target),0)+1
                    except (TypeError,ValueError):pass
                reason=str(row.get('reason') or row.get('text') or 'Reported message')
                add(target,'report','report submitted',reason,row.get('ts'),row.get('reporter'),source='report',event_id='report:'+report_id)
                if row.get('status') not in {None,'open','pending'}:
                    add(target,'report',str(row.get('decision') or row.get('status')),
                        'Report outcome recorded',row.get('resolved') or row.get('updated') or row.get('ts'),
                        row.get('resolved_by'),source='report',event_id='report-outcome:'+report_id)
        except Exception:pass
        try:
            for row in self.db['mgmt_banned_users'].find({'chat_id':cid}).sort('ts',-1).limit(80):
                add(row.get('user_id'),'moderation','ban record',row.get('reason') or 'Ban recorded',row.get('ts'),source='bot',event_id='ban:'+str(row.get('user_id')))
        except Exception:pass
        try:
            for row in self.db['mgmt_audit'].find({'chat_id':cid,'kind':{'$in':['moderation','warn_reset']}}).sort('ts',-1).limit(180):
                if row.get('action')=='case_note':continue
                detail=str(row.get('detail') or '')
                match=re.search(r'(?:member|user(?:_id)?)\s*(?:[:#]\s*)?(\d+)',detail,re.I)
                if not match:continue
                add(match.group(1),row.get('kind'),row.get('action'),detail,row.get('ts'),row.get('actor'),
                    source=row.get('source','bot'),event_id=str(row.get('_id') or ''))
        except Exception:pass
        pending_by_user={}
        try:
            for row in self.db['mgmt_escalations'].find({'chat_id':cid}).sort('created_at',-1).limit(120):
                user=row.get('user_id')
                action=str(row.get('action') or 'ban')
                status=str(row.get('status') or 'open')
                stamp=row.get('created_at') or row.get('updated_at')
                detail=f"{action} after {int(row.get('warning_count') or 0)} warnings"
                if row.get('reason'):detail+=f": {str(row.get('reason'))[:240]}"
                add(user,'escalation','review requested' if status=='open' else f"review {status}",detail,
                    stamp if status=='open' else row.get('resolved_at') or stamp,
                    row.get('requested_by') if status=='open' else row.get('resolved_by'),
                    source='bot',event_id='escalation:'+str(row.get('_id') or ''))
                if status=='open':
                    try:user_key=int(user)
                    except (TypeError,ValueError):continue
                    pending_by_user.setdefault(user_key,[]).append({
                        'id':str(row.get('_id') or ''),'action':action,
                        'warning_count':int(row.get('warning_count') or 0),
                        'reason':str(row.get('reason') or '')[:300],
                        'at':case_timestamp(stamp),
                    })
        except Exception:pass
        try:
            for row in self.db['mgmt_case_notes'].find({'chat_id':cid}).sort('ts',-1).limit(200):
                add(row.get('user_id'),'note','moderator note',row.get('text'),row.get('ts'),row.get('actor'),
                    source='studio',event_id='case-note:'+str(row.get('_id') or ''))
        except Exception:pass
        output=[]
        for user,events in grouped.items():
            events.sort(key=lambda event:event.get('at') or '',reverse=True)
            output.append({'user_id':user,'event_count':len(events),'open_reports':open_reports.get(user,0),
                           'pending_escalations':pending_by_user.get(user,[]),
                           'latest':events[0]['at'] if events else None,'events':events[:40]})
        output.sort(key=lambda case:case.get('latest') or '',reverse=True)
        try:limit=max(1,min(int(limit),80))
        except (TypeError,ValueError):limit=40
        return output[:limit]

    def review_escalation(self,cid,body):
        from bson import ObjectId
        cid=integer(cid)
        if cid>0:raise ViewError('Escalation reviews are group-only.',403)
        raw=str((body or {}).get('id') or '')
        try:identifier=ObjectId(raw)
        except Exception:raise ViewError('A valid pending escalation ID is required.') from None
        decision=str((body or {}).get('decision') or '')
        if decision not in {'approve','reject'}:raise ViewError('Choose approve or reject.')
        query={'_id':identifier,'chat_id':cid,'status':'open'}
        row=self.db['mgmt_escalations'].find_one(query)
        if row is None:raise ViewError('That escalation is already reviewed or belongs to another group.',404)
        _,actor=self.access(cid)
        self.rights(cid,actor,['can_restrict_members'])
        claimed=self.db['mgmt_escalations'].update_one(query,{'$set':{'status':'reviewing','reviewed_by':self.actor}})
        if not getattr(claimed,'modified_count',0):raise ViewError('Another admin is already reviewing this action.',409)
        action=str(row.get('action') or '')
        target=integer(row.get('user_id'),positive=True)
        if decision=='approve':
            try:
                if action=='ban':self.call('banChatMember',{'chat_id':cid,'user_id':target})
                elif action=='kick':
                    self.call('banChatMember',{'chat_id':cid,'user_id':target})
                    self.call('unbanChatMember',{'chat_id':cid,'user_id':target,'only_if_banned':True})
                else:raise ViewError('The pending escalation has an unsupported action.',409)
            except Exception:
                self.db['mgmt_escalations'].update_one({'_id':identifier,'status':'reviewing'},
                    {'$set':{'status':'open'},'$unset':{'reviewed_by':''}})
                raise
        resolved='approved' if decision=='approve' else 'rejected'
        result=self.db['mgmt_escalations'].update_one({'_id':identifier,'status':'reviewing'},
            {'$set':{'status':resolved,'resolved_at':now(),'resolved_by':self.actor}})
        if not getattr(result,'modified_count',0):
            raise ViewError('Telegram may have confirmed the action, but the review record could not be finalized. Check the group before retrying.',503)
        self.log(cid,'escalation_review',{'user_id':target,'decision':decision,'verb':action})
        return {'ok':True,'id':raw,'status':resolved,'cases':self.case_history(cid)}

    def case_note(self,cid,body):
        cid=integer(cid)
        if cid>0:raise ViewError('Case notes are group-only.',403)
        user=integer((body or {}).get('user_id'),positive=True)
        text=(body or {}).get('text')
        if not isinstance(text,str) or not text.strip() or len(text.strip())>600:
            raise ViewError('A moderator note must contain 1–600 characters.')
        self.db['mgmt_case_notes'].insert_one({'chat_id':cid,'user_id':user,'text':text.strip(),
            'actor':self.actor,'ts':now()})
        self.log(cid,'case_note',{'user_id':user},source='web')
        return {'ok':True,'cases':self.case_history(cid)}

    # ── owner inbox: reports and join requests ───────────────────────────────
    def inbox(self,cid):
        reports,requests=[],[]
        try:
            for row in self.db['mgmt_reports'].find({'chat_id':cid,'status':'open'}).sort('ts',-1).limit(30):
                reports.append({'id':str(row.get('_id')),'reporter':row.get('reporter'),
                    'target':row.get('target'),'message_id':row.get('message_id'),
                    'text':str(row.get('text') or row.get('reason') or '')[:180],
                    'at':aware(row.get('ts')).isoformat() if row.get('ts') else None})
        except Exception:reports=[]
        try:
            for row in self.db['mgmt_join_requests'].find({'chat_id':cid,'status':'pending'}).sort('ts',-1).limit(30):
                requests.append({'user_id':int(row.get('user') or 0),'name':str(row.get('name') or '')[:80],
                    'username':str(row.get('username') or '')[:64] or None,
                    'at':aware(row.get('ts')).isoformat() if row.get('ts') else None})
        except Exception:requests=[]
        return {'reports':reports,'join_requests':requests}

    def _join_request(self,cid,body):
        decision=str(body.get('decision') or '')
        if decision not in {'approve','decline'}:raise ViewError('Choose approve or decline.')
        user=integer(body.get('user_id'),positive=True)
        row=self.db['mgmt_join_requests'].find_one({'chat_id':cid,'user':user,'status':'pending'})
        if row is None:raise ViewError('This join request is no longer pending.',404)
        method='approveChatJoinRequest' if decision=='approve' else 'declineChatJoinRequest'
        _,actor=self.access(cid)
        self.rights(cid,actor,['can_invite_users'])
        try:self.call(method,{'chat_id':cid,'user_id':user})
        except TelegramError as error:
            # Telegram answers 400 when the request expired; mark it rather than
            # leaving a row the panel would offer forever.
            if error.api_status==400:
                self.db['mgmt_join_requests'].update_one({'_id':row['_id']},{'$set':{'status':'expired'}})
            raise
        self.db['mgmt_join_requests'].update_one({'_id':row['_id']},{'$set':{'status':decision+'d','resolved':now()}})
        self.log(cid,'join_request',{'user_id':user,'decision':decision})
        return {'ok':True,'user_id':user,'status':decision+'d','inbox':self.inbox(cid)}

    def _report_update(self,cid,body):
        from bson import ObjectId
        raw=str(body.get('id') or '')
        try:identifier=ObjectId(raw)
        except Exception:raise ViewError('A valid report ID is required.') from None
        decision=str(body.get('decision') or '')
        if decision:
            return self._report_action(cid,identifier,raw,decision,body)
        status=str(body.get('status') or 'resolved')
        if status not in {'resolved','dismissed'}:raise ViewError('Choose resolved or dismissed.')
        row=self.db['mgmt_reports'].find_one({'_id':identifier,'chat_id':cid})
        if row is None:raise ViewError('This report was not found.',404)
        self.db['mgmt_reports'].update_one({'_id':identifier},{'$set':{'status':status,'resolved':now(),'resolved_by':self.actor}})
        self.log(cid,'report_update',{'id':raw,'status':status})
        return {'ok':True,'id':raw,'status':status,'inbox':self.inbox(cid)}

    def _report_action(self,cid,identifier,raw,decision,body):
        """Warn or ban the reported member, then close the report.

        This is the same escalation ladder ``/warn`` uses; the limit and the
        action come from the group's stored settings rather than a constant.
        """
        if decision not in {'warn','ban'}:raise ViewError('Choose warn, ban, resolved or dismissed.')
        row=self.db['mgmt_reports'].find_one({'_id':identifier,'chat_id':cid})
        if row is None:raise ViewError('This report was not found.',404)
        if str(row.get('status') or 'open')!='open':
            raise ViewError('This report was already handled.',409)
        try:target=int(row.get('target') or 0)
        except (TypeError,ValueError):target=0
        if target<=0:raise ViewError('This report does not name the member to act on.',409)
        _,actor=self.access(cid)
        self.rights(cid,actor,['can_restrict_members'])
        note=''
        if decision=='ban':
            self.call('banChatMember',{'chat_id':cid,'user_id':target})
            note='member banned'
        else:
            from videl.utils import warnings as warning_rules
            from videl.utils.db import add_warn,get_escalation,get_warn_limit
            window=self.db['mgmt_warnings'].find_one({'chat_id':cid,'user_id':target}) or {}
            escalation=get_escalation(cid)
            limit=get_warn_limit(cid)
            # Same verdict the bot's /warn reaches: decay first, then the rung.
            plan=warning_rules.next_stage(window,limit,escalation.get('decay_days',0))
            count=add_warn(cid,target,'report')
            if plan['reached']:
                self.db['mgmt_warnings'].update_one({'chat_id':cid,'user_id':target},
                    {'$set':{'stages':plan['next_stage']}})
            count=plan['count']
            shown=min(count,limit)
            if plan['reached']:
                action=warning_rules.ladder_action(escalation,plan['stage']) if escalation.get('enabled') else 'none'
                if action in {'ban','kick'} and escalation.get('review_severe'):
                    try:
                        from videl.utils.escalations import queue_review
                        identifier=queue_review(self.db,cid,target,action,shown,str(row.get('reason') or 'Report warning'),
                                                self.actor,'web')
                        note=f'{shown}/{limit} warnings; {action} pending admin review (case {identifier})'
                    except Exception:
                        log.exception('Could not queue report escalation review for chat %s member %s',cid,target)
                        note=f'{shown}/{limit} warnings; review queue unavailable, so {action} was not applied'
                elif action=='ban':
                    self.call('banChatMember',{'chat_id':cid,'user_id':target})
                    note=f'{shown}/{limit} warnings; member banned'
                elif action=='kick':
                    self.call('banChatMember',{'chat_id':cid,'user_id':target})
                    self.call('unbanChatMember',{'chat_id':cid,'user_id':target})
                    note=f'{shown}/{limit} warnings; member removed'
                elif action=='mute':
                    hours=max(1,min(int(escalation.get('mute_hours') or 6),168))
                    self.call('banChatMember',{'chat_id':cid,'user_id':target,
                        'until_date':int(time.time())+hours*3600})
                    note=f'{shown}/{limit} warnings; muted {hours}h'
                else:
                    note=f'{shown}/{limit} warnings; escalation is off'
            else:
                note=f'{shown}/{limit} warnings'
            if plan['decayed']:
                note+=f" ({plan['decayed']} older lapsed)"
        self.db['mgmt_reports'].update_one({'_id':identifier},{'$set':{
            'status':'resolved','resolved':now(),'decision':decision,'resolved_by':self.actor}})
        self.log(cid,'report_update',{'id':raw,'decision':decision,'user_id':target})
        return {'ok':True,'id':raw,'status':'resolved','decision':decision,
                'note':note,'inbox':self.inbox(cid)}

    def _commands(self,cid,body):
        from videl.utils.command_catalog import commands as catalog_commands
        name=str(body.get('command') or '').strip().casefold()
        allowed={item['name'] for item in catalog_commands()}
        if name not in allowed:raise ViewError('Choose a command the bot registers.')
        from videl.utils.db import disable_cmd,enable_cmd,list_disabled
        enable=body.get('action')=='command_enable'
        if enable:enable_cmd(cid,name)
        else:disable_cmd(cid,name)
        disabled=sorted({str(item) for item in list_disabled(cid)})[:80]
        self.log(cid,body.get('action'),{'command':name})
        return {'ok':True,'command':name,'enabled':enable,'disabled_commands':disabled}

    def _automation(self,cid,body):
        from videl.utils.db import get_automation,set_automation
        previous=get_automation(cid)
        quiet=body.get('quiet_hours');escalation=body.get('escalation');protection=body.get('protection')
        if quiet is None and escalation is None and protection is None:
            raise ViewError('Send quiet_hours, escalation or protection settings.')
        if quiet is not None:
            if not isinstance(quiet,dict):raise ViewError('Quiet hours must be an object.')
            if 'enabled' in quiet and type(quiet['enabled']) is not bool:
                raise ViewError('Quiet hours enabled must be true or false.')
            for key in ('start','end'):
                if key in quiet and parse_hhmm(quiet[key]) is None:
                    raise ViewError('Choose a valid 24-hour start and end time.')
            if 'tz_offset' in quiet:
                offset=quiet['tz_offset']
                if isinstance(offset,bool) or not isinstance(offset,int) or not -840<=offset<=840:
                    raise ViewError('The timezone offset must be minutes between -840 and 840.')
            if quiet.get('start') and quiet.get('end') and parse_hhmm(quiet['start'])==parse_hhmm(quiet['end']):
                raise ViewError('Quiet hours cannot start and end at the same minute.')
            quiet=normalize_quiet({**get_automation(cid)['quiet_hours'],**quiet})
        if escalation is not None:
            if not isinstance(escalation,dict):raise ViewError('Escalation must be an object.')
            if 'action' in escalation and escalation['action'] not in ESCALATION_ACTIONS:
                raise ViewError('Choose ban, mute, kick or none as the escalation action.')
            if 'mute_hours' in escalation:
                hours=escalation['mute_hours']
                if isinstance(hours,bool) or not isinstance(hours,int) or not MUTE_RANGE[0]<=hours<=MUTE_RANGE[1]:
                    raise ViewError(f'The mute length must be {MUTE_RANGE[0]}–{MUTE_RANGE[1]} hours.')
            if 'enabled' in escalation and type(escalation['enabled']) is not bool:
                raise ViewError('Escalation enabled must be true or false.')
            if 'review_severe' in escalation and type(escalation['review_severe']) is not bool:
                raise ViewError('Severe-action review must be true or false.')
            if 'decay_days' in escalation:
                decay=escalation['decay_days']
                if isinstance(decay,bool) or not isinstance(decay,int) or not DECAY_RANGE[0]<=decay<=DECAY_RANGE[1]:
                    raise ViewError(f'Warning decay must be {DECAY_RANGE[0]}–{DECAY_RANGE[1]} days (0 keeps warnings forever).')
            if 'ladder' in escalation:
                ladder=escalation['ladder']
                if not isinstance(ladder,list) or any(item not in ESCALATION_LADDER for item in ladder):
                    raise ViewError('The ladder may only contain mute, kick and ban, in that order.')
                order={'mute':0,'kick':1,'ban':2}
                if len(ladder)>3 or any(order[ladder[i]]>=order[ladder[i+1]] for i in range(len(ladder)-1)):
                    raise ViewError('Order the ladder from the gentlest action to the harshest, without duplicates.')
            escalation=normalize_escalation({**get_automation(cid)['escalation'],**escalation})
        if protection is not None:
            if not isinstance(protection,dict):raise ViewError('The protection window must be an object.')
            if 'enabled' in protection and type(protection['enabled']) is not bool:
                raise ViewError('The protection window switch must be true or false.')
            for key in ('start','end'):
                if key in protection and parse_hhmm(protection[key]) is None:
                    raise ViewError('Choose a valid 24-hour start and end time for the window.')
            if 'locks' in protection:
                locks=protection['locks']
                if not isinstance(locks,list):raise ViewError('Locks must be a list.')
                allowed=set(LOCK_KEYS)
                if any(not isinstance(item,str) or item not in allowed for item in locks):
                    raise ViewError('Pick locks the bot actually enforces.')
            protection=normalize_protection({**get_automation(cid)['protection'],**protection})
            if protection['enabled'] and not protection['locks']:
                raise ViewError('Pick at least one lock for the window to apply.')
            if parse_hhmm(protection['start'])==parse_hhmm(protection['end']):
                raise ViewError('A protection window cannot start and end at the same minute.')
        try:
            config=set_automation(cid,quiet_hours=quiet,escalation=escalation,protection=protection,
                                  expected=self._expected(body))
        except settings_store.SettingsConflict as error:
            raise self._stale(error) from None
        self.log(cid,'automation',{'quiet':quiet,'escalation':escalation,'protection':protection},
                 before=previous,after=config)
        return {'ok':True,'automation':config}

    def admin(self,cid,actor,body,source='web'):
        """Typed admin actions. Every write re-reads the document afterwards."""
        action=body.get('action')
        if self.scope!='owner' and action in self.OWNER_ONLY:
            raise ViewError('Only the bot owner can do that.',403)
        service=action in {'automation','command_disable','command_enable','join_request','report_update',
                           'backup_import','backup_restore','backup_snapshot','backup_list','case_note','escalation_review'}
        tracked={'settings','preset','warn_limit','welcome','goodbye','rules','blacklist_mode'}
        before=self.snapshot(cid) if action in tracked else None
        result=self._service(cid,body) if service else self._admin(cid,actor,body)
        # ``protect`` is written by settings(), which records its own event;
        # service actions record their own history.
        if not service and action!='protect':
            self.log(cid,action,body,source,before=before,
                     after=self.snapshot(cid) if before is not None else None)
        if isinstance(result,dict) and result.get('ok'):
            # The panel replaces its token after every accepted write, so the
            # next switch does not conflict with its own previous save.
            result.setdefault('revision',self.revision(cid))
        return result

    def _service(self,cid,body):
        action=body.get('action')
        if action=='automation':return self._automation(cid,body)
        if action in {'command_disable','command_enable'}:return self._commands(cid,body)
        if action=='join_request':return self._join_request(cid,body)
        if action=='report_update':return self._report_update(cid,body)
        if action=='backup_import':return self.import_group(cid,OWNER_ID,body)
        if action=='backup_restore':return self.restore_saved(cid,OWNER_ID,body)
        if action=='backup_snapshot':return self.save_snapshot(cid,body)
        if action=='backup_list':return self.list_snapshots(cid)
        if action=='case_note':return self.case_note(cid,body)
        if action=='escalation_review':return self.review_escalation(cid,body)
        raise ViewError('Unsupported group management action.')

    def _admin(self,cid,actor,body):
        action=body.get('action')
        if cid>0:raise ViewError('Group management is group-only.',403)
        if action in {'protect','preset'}:
            self.rights(cid,actor,['can_delete_messages'])
        if action=='protect':
            return self.settings(cid,actor,body)
        if action=='settings':
            settings=body.get('settings')
            if not isinstance(settings,dict) or not settings or set(settings)-set(BOOL_SETTINGS) or any(type(value) is not bool for value in settings.values()):
                raise ViewError('Only supported boolean protection settings are accepted.')
            revision=self._write_settings(cid,settings,body)
            return {'ok':True,'settings':self.snapshot(cid),'revision':revision}
        if action=='preset':
            name=body.get('preset')
            if name not in PRESETS:raise ViewError('Choose one of the saved presets.')
            values=PRESETS[name]['settings']
            revision=self._write_settings(cid,values,body)
            return {'ok':True,'preset':name,'settings':self.snapshot(cid),'revision':revision}
        if action=='warn_limit':
            low,high=INT_SETTINGS['warn_threshold']
            value=integer(body.get('limit'),positive=True)
            if not low<=value<=high:raise ViewError(f'The warning limit must be {low}–{high}.')
            revision=self._write_settings(cid,{'warn_threshold':value},body)
            return {'ok':True,'settings':self.snapshot(cid),'revision':revision}
        if action in {'welcome','goodbye'}:
            text=body.get('text')
            if not isinstance(text,str) or len(text)>TEXT_SETTINGS[f'{action}_message']:
                raise ViewError(f'{action.title()} text must be 1–{TEXT_SETTINGS[f"{action}_message"]} characters.')
            updates={f'{action}_message':text.strip()}
            if type(body.get('enabled')) is bool:updates[f'{action}_enabled']=body['enabled']
            revision=self._write_settings(cid,updates,body)
            return {'ok':True,'settings':self.snapshot(cid),'revision':revision}
        if action=='rules':
            text=body.get('text')
            if text is not None and (not isinstance(text,str) or len(text)>TEXT_SETTINGS['rules']):
                raise ViewError('Rules must be text up to 2000 characters, or empty to clear them.')
            revision=self._write_settings(cid,{'rules':(text or '').strip() or None},body)
            return {'ok':True,'settings':self.snapshot(cid),'revision':revision}
        if action in {'blacklist_add','blacklist_remove'}:
            trigger=str(body.get('trigger') or '').strip().casefold()
            if not trigger or len(trigger)>64:raise ViewError('A blacklist word between 1 and 64 characters is required.')
            if action=='blacklist_add':
                self.db['blacklist'].update_one({'chat':cid,'trigger':trigger},{'$set':{'chat':cid,'trigger':trigger,'mode':str(body.get('mode') or 'del')}},upsert=True)
            else:
                self.db['blacklist'].delete_one({'chat':cid,'trigger':trigger})
            return {'ok':True,'action':action,'trigger':trigger}
        if action=='blacklist_mode':
            mode=body.get('mode')
            if mode not in ENUM_SETTINGS['blacklist_mode']:raise ViewError('Choose a supported blacklist mode.')
            revision=self._write_settings(cid,{'blacklist_mode':mode},body)
            return {'ok':True,'settings':self.snapshot(cid),'revision':revision}
        if action=='note_create':
            name=str(body.get('name') or '').strip().casefold()
            text=body.get('text')
            if not re.fullmatch(r'[a-z0-9_]{1,32}',name):raise ViewError('Note names may use 1–32 letters, numbers or underscores.')
            if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ViewError('A note needs 1–2000 characters of text.')
            self.db['mgmt_notes'].update_one({'chat_id':cid,'name':name},
                {'$set':{'chat_id':cid,'name':name,'content':text.strip(),'type':'text'}},upsert=True)
            return {'ok':True,'saved':name}
        if action=='note_delete':
            name=str(body.get('name') or '').strip().casefold()
            if not name:raise ViewError('A note name is required.')
            self.db['mgmt_notes'].delete_one({'chat_id':cid,'name':name})
            return {'ok':True,'deleted':name}
        if action=='filter_create':
            keyword=str(body.get('keyword') or '').strip().casefold()
            reply=body.get('reply')
            if not keyword or len(keyword)>64:raise ViewError('Filter keywords must contain 1–64 characters.')
            if not isinstance(reply,str) or not reply.strip() or len(reply)>400:raise ViewError('An automatic reply needs 1–400 characters.')
            self.db['mgmt_filters'].update_one({'chat_id':cid,'keyword':keyword},
                {'$set':{'chat_id':cid,'keyword':keyword,'reply':reply.strip()}},upsert=True)
            return {'ok':True,'saved':keyword}
        if action=='filter_delete':
            keyword=str(body.get('keyword') or '').strip().casefold()
            if not keyword:raise ViewError('A filter keyword is required.')
            self.db['mgmt_filters'].delete_one({'chat_id':cid,'keyword':keyword})
            return {'ok':True,'deleted':keyword}
        if action=='custom_command_create':
            from videl.utils import custom_commands
            try:
                name=custom_commands.save(self.db,cid,body.get('name'),body.get('response'),body.get('cooldown_seconds',0))
            except custom_commands.CustomCommandError as error:
                raise ViewError(str(error)) from None
            return {'ok':True,'saved':name,'custom_commands':custom_commands.list_for(self.db,cid)}
        if action=='custom_command_delete':
            from videl.utils import custom_commands
            try:
                name=custom_commands.delete(self.db,cid,body.get('name'))
            except custom_commands.CustomCommandError as error:
                raise ViewError(str(error)) from None
            return {'ok':True,'deleted':name,'custom_commands':custom_commands.list_for(self.db,cid)}
        if action=='approved_remove':
            user=integer(body.get('user_id'),positive=True)
            self.db['approved'].delete_one({'chat':cid,'user':user})
            return {'ok':True,'user_id':user}
        if action=='warn_reset':
            user=integer(body.get('user_id'),positive=True)
            self.db['mgmt_warnings'].delete_one({'chat_id':cid,'user_id':user})
            return {'ok':True,'user_id':user}
        raise ViewError('Unsupported group management action.')

    def settings(self,cid,actor,body):
        action=body.get('action')
        if action=='recording':
            enabled=body.get('enabled');days=body.get('retention_days',7)
            if type(enabled) is not bool or type(days) is not int or days not in RETENTION:
                raise ViewError('Choose recording on/off and retention of 1, 7 or 30 days.')
            previous=self.db['group_view_settings'].find_one({'_id':cid}) or {}
            enabled_at=previous.get('enabled_at',now()) if previous.get('enabled') else now()
            indexes(self.db)
            if enabled and not previous.get('enabled'):
                self.call('sendMessage',{'chat_id':cid,'text':f'Bot inbox recording enabled by the bot owner. Bot-visible messages will be stored for up to {days} days in an owner-only dashboard. '+('You can stop recording with /inbox off.' if cid>0 else 'Any current group admin can stop recording with /groupview off.')+' Telegram history is not imported.'})
            self.db['group_view_settings'].update_one({'_id':cid},{'$set':{'enabled':enabled,'retention_days':days,
                'enabled_at':enabled_at,'epoch':str(uuid.uuid4())}},upsert=True)
            self.db['group_view_messages'].update_many({'chat_id':cid},[{'$set':{'expires_at':{'$add':['$date',days*86400000]}}}])
            self.log(cid,'recording',{'enabled':enabled,'days':days})
            return {'ok':True,'recording':enabled,'retention_days':days}
        if action=='purge_history':
            self.db['group_view_settings'].update_one({'_id':cid},{'$set':{'enabled':False,'epoch':str(uuid.uuid4())}},upsert=True)
            count=self.db['group_view_messages'].delete_many({'chat_id':cid}).deleted_count
            self.log(cid,'purge_history',{'count':count})
            return {'ok':True,'deleted_count':count,'recording':False}
        if action=='protect':
            if cid>0:raise ViewError('Protection controls are group-only.',403)
            settings=body.get('settings')
            if not isinstance(settings,dict) or not settings or set(settings)-PROTECTION or any(type(v) is not bool for v in settings.values()):
                raise ViewError('Only supported boolean group protection settings are accepted.')
            self.rights(cid,actor,['can_delete_messages'])
            before=self.snapshot(cid)
            revision=self._write_settings(cid,settings,body)
            after=self.snapshot(cid)
            self.log(cid,'protect',{'settings':settings},before=before,after=after)
            return {'ok':True,'settings':after,'revision':revision}
        raise ViewError('Unknown setting action.')

    def act(self,body,source='web'):
        cid,actor=self.access(body.get('chat_id'))
        action=body.get('action')
        if self.scope!='owner' and action in self.OWNER_ONLY:
            raise ViewError('Only the bot owner can do that.',403)
        if action in {'recording','purge_history','protect'}:return self.settings(cid,actor,body)
        if action in {'settings','preset','warn_limit','welcome','goodbye','rules','blacklist_add','blacklist_remove','blacklist_mode','note_create','note_delete','filter_create','filter_delete','custom_command_create','custom_command_delete','approved_remove','warn_reset','automation','command_disable','command_enable','join_request','report_update','backup_snapshot','backup_list','backup_import','backup_restore','case_note','escalation_review'}:
            return self.admin(cid,actor,body,source)
        if cid>0 and action not in {'send','reply','delete','react','poll','forward'}:raise ViewError('This action is group-only.',403)
        if action not in {'send','reply','delete','react','poll','forward','mute','unmute','ban','pin','unpin'}:raise ViewError('Unsupported group action.')
        mid=None if action in {'send','poll'} else integer(body.get('message_id'),positive=True)
        policy=self.db['group_view_settings'].find_one({'_id':cid}) or {}
        days=policy.get('retention_days',7)
        if days not in RETENTION:days=7
        message=self.db['group_view_messages'].find_one({'chat_id':cid,'message_id':mid,'expires_at':{'$gt':now()},'date':{'$gte':now()-timedelta(days=days)}})
        if action not in {'send','poll'} and (not message or message.get('deleted')):raise ViewError('This recorded message is missing, expired or deleted.',404)
        rights={'delete':[] if cid>0 else ['can_delete_messages'],'pin':['can_pin_messages'],'unpin':['can_pin_messages'],
            'mute':['can_restrict_members'],'unmute':['can_restrict_members'],'ban':['can_restrict_members']}.get(action,[])
        me=self.rights(cid,actor,rights)
        target=message.get('sender_id') if message else None
        if action in {'mute','unmute','ban'}:
            if not message.get('sender_is_user') or not target or target in {OWNER_ID,me['id']}:
                raise ViewError('Anonymous/channel senders, the bot and the owner cannot be targeted.',403)
            member=self.call('getChatMember',{'chat_id':cid,'user_id':target})
            if member.get('status') in {'creator','administrator'}:raise ViewError('Group administrators are protected targets.',403)
        payload={'chat_id':cid}
        is_html=False
        if action in {'send','reply'}:
            text=body.get('text')
            if not isinstance(text,str) or not text.strip():
                raise ViewError('Enter a reply of 1–4096 Telegram text units.')
            text,is_html=rich_text(text,4096)
            method='sendMessage';payload.update(text=text)
            if is_html:payload['parse_mode']='HTML'
            if mid:payload['reply_parameters']={'message_id':mid,'allow_sending_without_reply':False}
            if message and message.get('thread_id'):payload['message_thread_id']=message['thread_id']
        elif action=='react':
            emoji=body.get('emoji')
            if emoji not in REACTIONS:
                raise ViewError('Choose one of the supported reaction emojis.')
            method='setMessageReaction';payload.update(message_id=mid,reaction=[{'type':'emoji','emoji':emoji}])
        elif action=='poll':
            question=body.get('question')
            options=body.get('options')
            if not isinstance(question,str) or not question.strip() or len(question)>300:
                raise ViewError('Poll questions must be 1–300 characters.')
            if not isinstance(options,list) or not (2<=len(options)<=10) or any(not isinstance(item,str) or not item.strip() or len(item)>100 for item in options):
                raise ViewError('Add 2–10 poll options, each 1–100 characters.')
            method='sendPoll'
            payload.update(question=question.strip(),options=[item.strip() for item in options],
                is_anonymous=body.get('anonymous') is not False,
                allows_multiple_answers=bool(body.get('multiple')))
            if message and message.get('thread_id'):payload['message_thread_id']=message['thread_id']
        elif action=='forward':
            destination=self.access(body.get('to_chat_id'))[0]
            if destination==cid:raise ViewError('Choose a different chat to forward this message to.')
            method='forwardMessage'
            payload={'chat_id':destination,'from_chat_id':cid,'message_id':mid}
        elif action=='delete':method='deleteMessage';payload['message_id']=mid
        elif action in {'pin','unpin'}:
            method='pinChatMessage' if action=='pin' else 'unpinChatMessage';payload['message_id']=mid
            if action=='pin':payload['disable_notification']=True
        elif action=='ban':method='banChatMember';payload['user_id']=target
        else:
            method='restrictChatMember';payload['user_id']=target
            if action=='mute':
                payload.update(permissions={'can_send_messages':False},until_date=int((now()+timedelta(minutes=10)).timestamp()))
            else:
                chat=self.call('getChat',{'chat_id':cid})
                if not isinstance(chat.get('permissions'),dict):raise ViewError('Group default permissions could not be read.',502)
                payload['permissions']=chat['permissions']
        key=body.get('request_id')
        try:key=str(uuid.UUID(key))
        except (ValueError,TypeError,AttributeError):raise ViewError('A unique request ID is required.') from None
        fingerprint={'chat_id':cid,'action':action,'message_id':mid,'payload':payload}
        # Expiry is not part of semantic identity: a repeated mute must not extend it.
        signature={**fingerprint,'payload':{k:v for k,v in payload.items() if k!='until_date'}}
        record={'_id':key,'request':signature,'status':'pending','expires_at':now()+timedelta(days=7)}
        indexes(self.db)
        try:self.db['group_view_operations'].insert_one(record)
        except DuplicateKeyError:
            previous=self.db['group_view_operations'].find_one({'_id':key}) or {}
            if previous.get('request')!=signature:raise ViewError('Request ID already belongs to another action.',409)
            return {'ok':previous.get('status')=='confirmed','status':previous.get('status','unconfirmed'),
                    'error':None if previous.get('status')=='confirmed' else 'Earlier delivery is pending or unconfirmed. Check Telegram; it was not retried.'}
        fallback_note=None
        try:
            try:result=self.call(method,payload)
            except TelegramError as error:
                # Telegram explicitly rejected the entities, so nothing was
                # delivered; one plain-text retry cannot duplicate a message.
                if not is_html or not error.parse_error:raise
                plain=plain_from_rich(payload['text'])
                retry={**payload,'text':plain};retry.pop('parse_mode',None)
                result=self.call(method,retry)
                payload=retry
                fallback_note='Telegram could not render every formatting tag, so the message was sent as plain text. Check the result before resending.'
        except Exception:
            self.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'unconfirmed'}})
            raise
        # Telegram success is separate from local follow-up persistence.
        warning=fallback_note
        try:
            self.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'confirmed'}})
            if action=='delete':self.db['group_view_messages'].update_one({'chat_id':cid,'message_id':mid},{'$set':{'deleted':True,'text':'','media':None}})
            if action=='react':self.db['group_view_messages'].update_one({'chat_id':cid,'message_id':mid},{'$set':{'bot_reaction':payload['reaction'][0]['emoji']}})
            settings=self.db['group_view_settings'].find_one({'_id':cid}) or {}
            if settings.get('enabled'):
                if action in {'send','reply'} and isinstance(result,dict):
                    store(self.db,{'chat_id':cid,'message_id':result['message_id'],'text':payload['text'],'media':None,
                        'sender_id':me['id'],'sender_is_user':True,'sender_name':me.get('first_name','Videl'),
                        'sender_username':me.get('username',''),'is_bot':True,'reply_to_id':mid,
                        'thread_id':message.get('thread_id') if message else None,'date':now(),'edited':False,'deleted':False})
                if action=='forward' and isinstance(result,dict):
                    target_settings=self.db['group_view_settings'].find_one({'_id':payload['chat_id']}) or {}
                    if target_settings.get('enabled'):
                        store(self.db,{'chat_id':payload['chat_id'],'message_id':result.get('message_id'),'text':str(result.get('text') or message.get('text') or ''),
                            'media':None,'sender_id':me['id'],'sender_is_user':True,'sender_name':me.get('first_name','Videl'),
                            'sender_username':me.get('username',''),'is_bot':True,'reply_to_id':None,'thread_id':None,
                            'date':now(),'edited':False,'deleted':False})
                if action=='poll' and isinstance(result,dict):
                    store(self.db,{'chat_id':cid,'message_id':result['message_id'],'text':payload['question'],
                        'media':{'kind':'poll','name':payload['question'][:160]},
                        'poll':{'question':payload['question'],'options':payload['options'],
                            'anonymous':payload['is_anonymous'],'multiple':payload['allows_multiple_answers']},
                        'sender_id':me['id'],'sender_is_user':True,'sender_name':me.get('first_name','Videl'),
                        'sender_username':me.get('username',''),'is_bot':True,'reply_to_id':None,
                        'thread_id':payload.get('message_thread_id'),'date':now(),'edited':False,'deleted':False})
        except Exception:warning=fallback_note or 'Telegram confirmed the action, but the local receipt/history update could not be saved.'
        return {'ok':True,'status':'confirmed','message_id':result.get('message_id') if isinstance(result,dict) else None,
                'warning':warning,'reaction':payload.get('reaction',[{}])[0].get('emoji') if action=='react' else None}
