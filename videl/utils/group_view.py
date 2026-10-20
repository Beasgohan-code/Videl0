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

OWNER_ID=6265999542
RETENTION=(1,7,30)
PROTECTION={'lock_links','lock_media','lock_stickers','lock_forwards','lock_polls','lock_mentions','antispam','welcome_enabled'}
log=logging.getLogger(__name__)


class ViewError(ValueError):
    def __init__(self,message,status=400):super().__init__(message);self.status=status


def integer(value,*,positive=False):
    if isinstance(value,bool) or not re.fullmatch(r'-?[0-9]{1,16}',str(value)):raise ViewError('A numeric Telegram ID is required.')
    value=int(value)
    if abs(value)>9007199254740991 or (positive and value<=0):raise ViewError('Invalid Telegram ID.')
    return value


def now():return datetime.now(timezone.utc)


def aware(value):
    if not isinstance(value,datetime):return now()
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def snapshot(message):
    chat=getattr(message,'chat',None)
    kind=str(getattr(getattr(chat,'type',None),'value',getattr(chat,'type','')))
    if kind not in {'group','supergroup','private'}:return None
    text=str(getattr(message,'text',None) or getattr(message,'caption',None) or '')[:4096]
    media=None
    for key in ('photo','video','document','audio','voice','sticker','animation','video_note','poll'):
        item=getattr(message,key,None)
        if item:
            media={'kind':key,'name':str(getattr(item,'file_name','') or '')[:160],
                   'file_id':getattr(item,'file_id',None),'size':getattr(item,'file_size',None),
                   'mime':getattr(item,'mime_type',None)}
            break
    if not text and media is None:return None
    user=getattr(message,'from_user',None)
    sender=user or getattr(message,'sender_chat',None)
    reply=getattr(message,'reply_to_message',None)
    return {'chat_id':chat.id,'chat_type':kind,'chat_title':str(getattr(chat,'title',None) or getattr(chat,'first_name',None) or getattr(sender,'first_name',None) or chat.id)[:100],'message_id':message.id,'text':text,'media':media,
        'sender_id':getattr(sender,'id',None),'sender_is_user':user is not None,
        'sender_name':str(getattr(sender,'first_name',None) or getattr(sender,'title',None) or 'Anonymous')[:100],
        'sender_username':str(getattr(sender,'username','') or '')[:64],
        'is_bot':bool(getattr(user,'is_bot',False)),
        'reply_to_id':getattr(reply,'id',None),'thread_id':getattr(message,'message_thread_id',None),
        'date':aware(getattr(message,'date',None)),'edited':bool(getattr(message,'edit_date',None)),
        'deleted':False}


_ALLOWED_RICH={'b','strong','i','em','u','ins','s','strike','del','code','pre','blockquote','a','tg-spoiler','tg-emoji'}
_RICH_TAG=re.compile(r'</?\s*([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>')


def rich_text(text,limit=4096):
    """Validate Telegram HTML, strip unsafe tags/attributes and premium emoji IDs.

    Returns (text,is_html). Plain text is returned untouched. Only formatting
    that Telegram documents is allowed; unknown tags are shown as literal text.
    """
    if not isinstance(text,str) or not text.strip():
        raise ViewError(f'Enter a message of 1–{limit} Telegram text units.')
    has=bool(re.search(r'<\s*/?\s*(?:b|i|u|s|code|pre|blockquote|a|tg-spoiler|tg-emoji|span)\b',text,re.I))
    if not has:
        if len(text.encode('utf-16-le'))//2>limit:
            raise ViewError(f'Enter a message of 1–{limit} Telegram text units.')
        return text,False
    if re.search(r'<tg-emoji',text,re.I):
        for _tag in re.findall(r'<tg-emoji[^>]*>',text,re.I):
            if not re.fullmatch(r"""<tg-emoji\s+emoji-id\s*=\s*["']?[0-9]{1,20}["']?\s*>""",_tag,re.I):
                raise ViewError('Premium emoji ID must be 1–20 digits. Copy it from @emoji or Telegram.')
    def replace(match):
        raw=match.group(0);name=match.group(1).lower()
        if name not in _ALLOWED_RICH:
            return _html.escape(raw)
        raw=re.sub(r"""\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""",'',raw,flags=re.I)
        if raw.startswith('</'):
            return f'</{name}>'
        if name=='tg-emoji':
            found=re.fullmatch(r"""<tg-emoji\s+emoji-id\s*=\s*["']?([0-9]{1,20})["']?\s*>""",raw,re.I)
            return f'<tg-emoji emoji-id="{found.group(1)}">' if found else _html.escape(raw)
        if name=='a':
            href=re.search(r"""href\s*=\s*(["'])(.*?)\1""",raw,re.I|re.S)
            if href and re.match(r'^(?:https?://|tg://)',href.group(2),re.I):
                return f'<a href="{_html.escape(href.group(2),quote=True)}">'
            return '<a>'
        return f'<{name}>'
    text=_RICH_TAG.sub(replace,text)
    text=re.sub(r'<(?!/?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote|a|tg-spoiler|tg-emoji)(?:\s|>))','&lt;',text)
    plain=_html.unescape(re.sub(r'<[^>]+>','',text))
    if not plain.strip():
        raise ViewError('Formatted messages need visible text outside the tags.')
    if len(plain.encode('utf-16-le'))//2>limit:
        raise ViewError(f'Formatted messages are limited to {limit} Telegram text units. Shorten the visible text.')
    if len(text)>min(20000,limit*8):
        raise ViewError('Formatted message is too large.')
    return text,True


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
        if cid>0 and action not in {'send','reply','delete'}:raise ViewError('This action is group-only.',403)
        if action not in {'send','reply','delete','mute','unmute','ban','pin','unpin'}:raise ViewError('Unsupported group action.')
        mid=None if action=='send' else integer(body.get('message_id'),positive=True)
        policy=self.db['group_view_settings'].find_one({'_id':cid}) or {}
        days=policy.get('retention_days',7)
        if days not in RETENTION:days=7
        message=self.db['group_view_messages'].find_one({'chat_id':cid,'message_id':mid,'expires_at':{'$gt':now()},'date':{'$gte':now()-timedelta(days=days)}})
        if action!='send' and (not message or message.get('deleted')):raise ViewError('This recorded message is missing, expired or deleted.',404)
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
        if action in {'send','reply'}:
            text=body.get('text')
            if not isinstance(text,str) or not text.strip():
                raise ViewError('Enter a reply of 1–4096 Telegram text units.')
            text,is_html=rich_text(text,4096)
            method='sendMessage';payload.update(text=text)
            if is_html:payload['parse_mode']='HTML'
            if mid:payload['reply_parameters']={'message_id':mid,'allow_sending_without_reply':False}
            if message and message.get('thread_id'):payload['message_thread_id']=message['thread_id']
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
        try:result=self.call(method,payload)
        except Exception:
            self.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'unconfirmed'}})
            raise
        # Telegram success is separate from local follow-up persistence.
        warning=None
        try:
            self.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'confirmed'}})
            if action=='delete':self.db['group_view_messages'].update_one({'chat_id':cid,'message_id':mid},{'$set':{'deleted':True,'text':'','media':None}})
            if action in {'send','reply'} and isinstance(result,dict):
                settings=self.db['group_view_settings'].find_one({'_id':cid}) or {}
                if settings.get('enabled'):
                    store(self.db,{'chat_id':cid,'message_id':result['message_id'],'text':payload['text'],'media':None,
                        'sender_id':me['id'],'sender_is_user':True,'sender_name':me.get('first_name','Videl'),
                        'sender_username':me.get('username',''),'is_bot':True,'reply_to_id':mid,
                        'thread_id':message.get('thread_id') if message else None,'date':now(),'edited':False,'deleted':False})
        except Exception:warning='Telegram confirmed the action, but the local receipt/history update could not be saved.'
        return {'ok':True,'status':'confirmed','message_id':result.get('message_id') if isinstance(result,dict) else None,'warning':warning}
