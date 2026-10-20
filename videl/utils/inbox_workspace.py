"""Owner-authored inbox preferences, drafts and saved replies in MongoDB.

These are separate from captured-message retention. Every chat detail read/write
rechecks the same live access policy as the inbox. Revisions prevent lost edits.
"""
import uuid
from pymongo.errors import DuplicateKeyError
from videl.utils.group_view import OWNER_ID,ViewError,integer,now


def text(value,limit,label):
    if not isinstance(value,str) or len(value.encode('utf-16-le'))//2>limit:
        raise ViewError(f'{label} must be plain text of at most {limit} Telegram text units.')
    return value


def revision(value):
    if type(value) is not int or not 0<=value<=9007199254740991:raise ViewError('A valid edit revision is required.')
    return value


def default_chat(cid):
    return {'chat_id':cid,'draft':'','notes':'','pinned':False,'tags':[],'last_reviewed_message_id':0,
        'revisions':{'draft':0,'notes':0,'organize':0}}


class InboxWorkspace:
    def __init__(self,service):self.service=service;self.db=service.db

    def key(self,cid):return f'{OWNER_ID}:{cid}'

    def chat(self,cid):
        doc=self.db['inbox_owner_chats'].find_one({'_id':self.key(cid),'owner_id':OWNER_ID}) or {}
        result=default_chat(cid)
        for key in result:
            if key in doc:result[key]=doc[key]
        return result

    def read(self,chat_id=None):
        if chat_id is not None:
            cid,_=self.service.access(chat_id)
            return {'ok':True,'chat':self.chat(cid)}
        rows=list(self.db['inbox_owner_chats'].find({'owner_id':OWNER_ID},
            {'_id':0,'chat_id':1,'pinned':1,'tags':1,'last_reviewed_message_id':1}).limit(500))
        replies=list(self.db['inbox_quick_replies'].find({'owner_id':OWNER_ID},{'_id':0,'owner_id':0}).sort('title',1).limit(50))
        for item in replies:
            if item.get('updated_at'):item['updated_at']=item['updated_at'].isoformat()
        return {'ok':True,'conversations':rows,'quick_replies':replies}

    def change(self,body):
        action=body.get('action')
        if action in {'save_reply','delete_reply'}:return self.reply(body)
        if action not in {'draft','notes','organize','review'}:raise ViewError('Unsupported workspace action.')
        cid,_=self.service.access(body.get('chat_id'))
        if action=='draft':updates={'draft':text(body.get('value'),4096,'Draft')}
        elif action=='notes':updates={'notes':text(body.get('value'),2000,'Notes')}
        elif action=='organize':
            pinned=body.get('pinned');tags=body.get('tags')
            if type(pinned) is not bool or not isinstance(tags,list) or len(tags)>5:raise ViewError('Choose a pin state and up to five tags.')
            tags=[text(tag,20,'Tag').strip() for tag in tags]
            if any(not tag for tag in tags):raise ViewError('Tags cannot be blank.')
            updates={'pinned':pinned,'tags':list(dict.fromkeys(tags))}
        else:
            mid=integer(body.get('message_id'),positive=True)
            # A review marker can only acknowledge an actually stored, unexpired
            # message. It is not a Telegram read receipt or a remote read action.
            if self.db['group_view_messages'].find_one({'chat_id':cid,'message_id':mid,'expires_at':{'$gt':now()}}) is None:
                raise ViewError('This message is no longer available for review.',404)
            updates=None
        expected=revision(body.get('revision')) if action!='review' else None
        key=self.key(cid)
        initial={**default_chat(cid),'owner_id':OWNER_ID}
        try:self.db['inbox_owner_chats'].update_one({'_id':key},{'$setOnInsert':initial},upsert=True)
        except DuplicateKeyError:pass
        if action=='review':
            self.db['inbox_owner_chats'].update_one({'_id':key,'owner_id':OWNER_ID},
                {'$max':{'last_reviewed_message_id':mid},'$set':{'updated_at':now()}})
        else:
            result=self.db['inbox_owner_chats'].update_one({'_id':key,'owner_id':OWNER_ID,f'revisions.{action}':expected},
                {'$set':{**updates,'updated_at':now()},'$inc':{f'revisions.{action}':1}})
            if result.matched_count!=1:raise ViewError('This field changed in another window. Refresh workspace data before saving; your editor text was not sent or overwritten.',409)
        return {'ok':True,'chat':self.chat(cid)}

    def reply(self,body):
        try:rid=str(uuid.UUID(body.get('id')))
        except (ValueError,TypeError,AttributeError):raise ViewError('A saved-reply ID is required.') from None
        expected=revision(body.get('revision'))
        key=f'{OWNER_ID}:{rid}';col=self.db['inbox_quick_replies']
        if body['action']=='delete_reply':
            result=col.delete_one({'_id':key,'owner_id':OWNER_ID,'revision':expected})
            if result.deleted_count!=1:raise ViewError('Saved reply changed or was removed. Refresh before deleting.',409)
            return {'ok':True}
        title=text(body.get('title'),60,'Title').strip();value=text(body.get('text'),4096,'Saved reply')
        if not title or not value.strip():raise ViewError('Add a title and reply text.')
        doc={'id':rid,'owner_id':OWNER_ID,'title':title,'text':value,'revision':expected+1,'updated_at':now()}
        if expected==0:
            if col.count_documents({'owner_id':OWNER_ID})>=50:raise ViewError('Keep at most 50 saved replies; remove one before adding another.')
            try:col.insert_one({'_id':key,**doc})
            except DuplicateKeyError:raise ViewError('This saved reply already exists. Refresh before editing.',409) from None
        else:
            result=col.update_one({'_id':key,'owner_id':OWNER_ID,'revision':expected},{'$set':doc})
            if result.matched_count!=1:raise ViewError('Saved reply changed in another window. Refresh before saving.',409)
        return {'ok':True,'reply':{key:value for key,value in doc.items() if key not in {'owner_id','updated_at'}}}
