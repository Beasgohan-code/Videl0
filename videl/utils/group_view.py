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
import uuid
from pymongo.errors import DuplicateKeyError

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


def coerce_bool(value):
    return value if type(value) is bool else bool(value)
REACTIONS=('👍','❤️','🔥','🎉','😁','🤔','👏','🙏','💯','⚡')
_PARSE_ERROR=re.compile(r'parse|entit|tag|nest',re.I)


def parse_error(status,description):
    return status==400 and bool(_PARSE_ERROR.search(str(description or '')))
log=logging.getLogger(__name__)


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
    def __init__(self,db,api):
        if db is None:raise ViewError('MongoDB is not connected.',503)
        self.db=db;self.api=api

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
        actor=self.call('getChatMember',{'chat_id':cid,'user_id':OWNER_ID})
        if actor.get('status') not in {'creator','administrator'}:
            raise ViewError('The owner account must currently be a group administrator to view or manage it.',403)
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
            'capture_dropped':_dropped,'rich_text':True,'settings':{key:bool(protections.get(key,False)) for key in PROTECTION},
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
                'can_manage':bool((bot_member or {}).get('can_manage_chat')) if member_status=='administrator' else False}
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
        except Exception:
            notes,filters=[],[]
        try:blacklist=list(self.db['blacklist'].find({'chat':cid},{'_id':0,'trigger':1,'mode':1}).limit(120))
        except Exception:blacklist=[]
        try:approved=[int(item) for item in self.db['approved'].distinct('user',{'chat':cid})][:120]
        except Exception:approved=[]
        try:disabled=[str(item.get('cmd','')) for item in self.db['disabled_cmds'].find({'chat':cid},{'_id':0,'cmd':1}).limit(80)]
        except Exception:disabled=[]
        from videl.utils.db import list_warns,get_warn_limit
        try:warns=list_warns(cid,100)
        except Exception:warns=[]
        return {'ok':True,'chat':info,'settings':self.snapshot(cid),'presets':PRESETS,
                'community':{
                    'warns':warns,'warn_limit':get_warn_limit(cid),
                    'notes':[{'name':str(item.get('name','')),'type':str(item.get('type','text'))} for item in notes],
                    'filters':[{'keyword':str(item.get('keyword','')),'reply':str(item.get('reply',''))[:160]} for item in filters],
                    'blacklist':[{'trigger':str(item.get('trigger','')),'mode':str(item.get('mode','del'))} for item in blacklist],
                    'approved':approved,'disabled_commands':disabled,
                },
                'problems':problems}

    def admin(self,cid,actor,body):
        """Typed admin actions. Every write re-reads the document afterwards."""
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
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':settings},upsert=True)
            return {'ok':True,'settings':self.snapshot(cid)}
        if action=='preset':
            name=body.get('preset')
            if name not in PRESETS:raise ViewError('Choose one of the saved presets.')
            values=PRESETS[name]['settings']
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':values},upsert=True)
            return {'ok':True,'preset':name,'settings':self.snapshot(cid)}
        if action=='warn_limit':
            low,high=INT_SETTINGS['warn_threshold']
            value=integer(body.get('limit'),positive=True)
            if not low<=value<=high:raise ViewError(f'The warning limit must be {low}–{high}.')
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':{'warn_threshold':value}},upsert=True)
            return {'ok':True,'settings':self.snapshot(cid)}
        if action in {'welcome','goodbye'}:
            text=body.get('text')
            if not isinstance(text,str) or len(text)>TEXT_SETTINGS[f'{action}_message']:
                raise ViewError(f'{action.title()} text must be 1–{TEXT_SETTINGS[f"{action}_message"]} characters.')
            updates={f'{action}_message':text.strip()}
            if type(body.get('enabled')) is bool:updates[f'{action}_enabled']=body['enabled']
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':updates},upsert=True)
            return {'ok':True,'settings':self.snapshot(cid)}
        if action=='rules':
            text=body.get('text')
            if text is not None and (not isinstance(text,str) or len(text)>TEXT_SETTINGS['rules']):
                raise ViewError('Rules must be text up to 2000 characters, or empty to clear them.')
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':{'rules':(text or '').strip() or None}},upsert=True)
            return {'ok':True,'settings':self.snapshot(cid)}
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
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':{'blacklist_mode':mode}},upsert=True)
            return {'ok':True,'settings':self.snapshot(cid)}
        if action=='note_delete':
            name=str(body.get('name') or '').strip().casefold()
            if not name:raise ViewError('A note name is required.')
            self.db['mgmt_notes'].delete_one({'chat_id':cid,'name':name})
            return {'ok':True,'deleted':name}
        if action=='filter_delete':
            keyword=str(body.get('keyword') or '').strip().casefold()
            if not keyword:raise ViewError('A filter keyword is required.')
            self.db['mgmt_filters'].delete_one({'chat_id':cid,'keyword':keyword})
            return {'ok':True,'deleted':keyword}
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
            return {'ok':True,'recording':enabled,'retention_days':days}
        if action=='purge_history':
            self.db['group_view_settings'].update_one({'_id':cid},{'$set':{'enabled':False,'epoch':str(uuid.uuid4())}},upsert=True)
            count=self.db['group_view_messages'].delete_many({'chat_id':cid}).deleted_count
            return {'ok':True,'deleted_count':count,'recording':False}
        if action=='protect':
            if cid>0:raise ViewError('Protection controls are group-only.',403)
            settings=body.get('settings')
            if not isinstance(settings,dict) or not settings or set(settings)-PROTECTION or any(type(v) is not bool for v in settings.values()):
                raise ViewError('Only supported boolean group protection settings are accepted.')
            self.rights(cid,actor,['can_delete_messages'])
            self.db['mgmt_chat_settings'].update_one({'chat_id':cid},{'$set':settings},upsert=True)
            return {'ok':True,'settings':settings}
        raise ViewError('Unknown setting action.')

    def act(self,body):
        cid,actor=self.access(body.get('chat_id'))
        action=body.get('action')
        if action in {'recording','purge_history','protect'}:return self.settings(cid,actor,body)
        if action in {'settings','preset','warn_limit','welcome','goodbye','rules','blacklist_add','blacklist_remove','blacklist_mode','note_delete','filter_delete','approved_remove','warn_reset'}:
            return self.admin(cid,actor,body)
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
