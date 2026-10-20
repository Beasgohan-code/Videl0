"""Mongo-contract and API tests; no live Telegram, user session or database."""
import asyncio
from datetime import timedelta
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch,AsyncMock
import mongomock
from flask import Flask
from pyrogram.enums import ChatType
from videl.utils import group_view as view
from videl.api.group_view_routes import register_group_view_routes

CID=-100123456


class GroupViewerTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().videl
        self.db['served_chats'].insert_one({'_id':CID})
        self.actor={'status':'administrator','can_restrict_members':True,'can_delete_messages':True,'can_pin_messages':True}
        self.bot_member=dict(self.actor)
        self.target={'status':'member'}
        self.api=Mock(side_effect=self.telegram)
        self.service=view.GroupView(self.db,self.api)
        self.message={'chat_id':CID,'message_id':25,'text':'Hello <script>alert(1)</script>',
            'sender_id':123,'sender_name':'Member','sender_is_user':True,'sender_username':'member',
            'date':view.now(),'expires_at':view.now()+timedelta(days=7),'reply_to_id':None,'media':None,
            'thread_id':7,'is_bot':False,'deleted':False,'edited':False}
        self.db['group_view_messages'].insert_one(dict(self.message))

    def telegram(self,method,payload):
        if method=='getMe':result={'id':777,'first_name':'Videl','username':'ExampleBot'}
        elif method=='getChatMember':result=self.actor if payload['user_id']==view.OWNER_ID else self.bot_member if payload['user_id']==777 else self.target
        elif method=='getChat':result={'permissions':{'can_send_messages':True,'can_send_photos':False}}
        elif method=='sendMessage':result={'message_id':50,'date':int(view.now().timestamp())}
        else:result=True
        return 200,{'ok':True,'result':result}

    def action(self,name,**extra):
        return self.service.act({'chat_id':CID,'message_id':25,'action':name,'request_id':str(uuid.uuid4()),**extra})

    def test_reads_only_served_groups_and_current_owner_admin(self):
        for cid in [42,-999]:
            with self.assertRaises(view.ViewError):self.service.read(cid)
        self.actor={'status':'member'}
        with self.assertRaises(view.ViewError) as error:self.service.read(CID)
        self.assertEqual(error.exception.status,403)
        self.api.assert_called_once_with('getChatMember',{'chat_id':CID,'user_id':view.OWNER_ID})

    def test_role_lookup_failure_never_grants_access(self):
        self.api.side_effect=lambda *a:(None,{'ok':False,'description':'token-secret'})
        with self.assertRaises(view.ViewError) as error:self.service.read(CID)
        self.assertNotIn('token-secret',str(error.exception))

    def test_snapshot_ignores_private_chats_and_does_not_copy_file_ids(self):
        msg=NS(chat=NS(id=CID,type=ChatType.SUPERGROUP),id=44,date=view.now(),text=None,caption='<b>caption</b>',
            photo=NS(file_id='do-not-expose'),from_user=NS(id=123,first_name='<Owner>',username='someone',is_bot=False),
            reply_to_message=NS(id=25),message_thread_id=7)
        snapshot=view.snapshot(msg)
        self.assertEqual(snapshot['text'],'<b>caption</b>')
        self.assertEqual(snapshot['media']['file_id'],'do-not-expose');self.assertEqual(snapshot['reply_to_id'],25)
        msg.chat.type=ChatType.PRIVATE
        self.assertEqual(view.snapshot(msg)['chat_type'],'private')

    def test_recording_off_by_default_and_preconsent_updates_ignored(self):
        item={k:v for k,v in self.message.items() if k not in {'_id','expires_at'}};item['message_id']=100
        view.store(self.db,item);self.assertIsNone(self.db['group_view_messages'].find_one({'message_id':100}))
        self.db['group_view_settings'].insert_one({'_id':CID,'enabled':True,'epoch':'epoch','enabled_at':view.now()+timedelta(seconds=1),'retention_days':7})
        view.store(self.db,item);self.assertIsNone(self.db['group_view_messages'].find_one({'message_id':100}))
        item['date']=view.now()+timedelta(seconds=2);view.store(self.db,item)
        doc=self.db['group_view_messages'].find_one({'message_id':100})
        self.assertIsNotNone(doc);self.assertEqual(doc['epoch'],'epoch')

    def test_edited_messages_upsert_instead_of_duplicate(self):
        self.db['group_view_settings'].insert_one({'_id':CID,'enabled':True,'epoch':'one','enabled_at':view.now()-timedelta(minutes=1),'retention_days':1})
        item={k:v for k,v in self.message.items() if k not in {'_id','expires_at'}}
        view.store(self.db,item);item.update(text='Edited',edited=True);view.store(self.db,item)
        self.assertEqual(self.db['group_view_messages'].count_documents({'message_id':25}),1)
        doc=self.db['group_view_messages'].find_one({'message_id':25})
        self.assertTrue(doc['edited']);self.assertEqual(doc['expires_at']-doc['date'],timedelta(days=1))

    def test_local_deleted_marker_cannot_be_revived_by_late_edit(self):
        self.action('delete')
        self.db['group_view_settings'].insert_one({'_id':CID,'enabled':True,'epoch':'one','enabled_at':view.now()-timedelta(minutes=1)})
        view.store(self.db,{k:v for k,v in self.message.items() if k not in {'_id','expires_at'}})
        doc=self.db['group_view_messages'].find_one({'message_id':25})
        self.assertTrue(doc['deleted']);self.assertEqual(doc['text'],'')

    def test_enable_posts_group_notice_and_validates_policy(self):
        # Mongomock lacks MongoDB's supported date + milliseconds aggregation.
        with patch.object(self.db['group_view_messages'],'update_many') as ttl:
            result=self.action('recording',enabled=True,retention_days=7)
        self.assertEqual(ttl.call_args.args[1],[{'$set':{'expires_at':{'$add':['$date',7*86400000]}}}])
        self.assertTrue(result['recording'])
        calls=[call for call in self.api.call_args_list if call.args[0]=='sendMessage']
        self.assertIn('/groupview off',calls[0].args[1]['text'])
        self.assertTrue(self.db['group_view_settings'].find_one({'_id':CID})['enabled'])
        self.assertTrue(any(index.get('expireAfterSeconds')==0 for index in self.db['group_view_messages'].index_information().values()))
        for days in [True,0,365,1.5,'7']:
            with self.assertRaises(view.ViewError):self.action('recording',enabled=True,retention_days=days)

    def test_notice_failure_does_not_enable_recording(self):
        original=self.telegram
        self.api.side_effect=lambda method,payload:(None,{'ok':False}) if method=='sendMessage' else original(method,payload)
        with self.assertRaises(view.ViewError):self.action('recording',enabled=True)
        self.assertIsNone(self.db['group_view_settings'].find_one({'_id':CID}))

    def test_read_time_expiry_and_literal_search(self):
        self.db['group_view_messages'].insert_one({**self.message,'_id':'old','message_id':1,'expires_at':view.now()-timedelta(seconds=1)})
        result=self.service.read(CID,query='.*')
        self.assertEqual(result['items'],[])
        result=self.service.read(CID)
        self.assertEqual([item['message_id'] for item in result['items']],[25])
        self.assertNotIn('_id',result['items'][0]);self.assertNotIn('epoch',result['items'][0])

    def test_pagination_is_bounded_and_conversation_order_is_ascending(self):
        for i in range(100,160):self.db['group_view_messages'].insert_one({**self.message,'_id':str(i),'message_id':i})
        result=self.service.read(CID)
        ids=[item['message_id'] for item in result['items']]
        self.assertEqual(len(ids),50);self.assertEqual(ids,sorted(ids));self.assertTrue(result['has_more'])
        older=self.service.read(CID,before=result['next_before'])
        self.assertLess(max(item['message_id'] for item in older['items']),min(ids))

    def test_admin_and_bot_specific_rights_both_required(self):
        self.actor['can_delete_messages']=False
        with self.assertRaises(view.ViewError):self.action('delete')
        self.actor['can_delete_messages']=True;self.bot_member['can_restrict_members']=False
        with self.assertRaises(view.ViewError):self.action('ban')
        self.assertFalse(any(call.args[0] in {'deleteMessage','banChatMember'} for call in self.api.call_args_list))

    def test_target_admins_and_anonymous_senders_are_protected(self):
        self.target={'status':'administrator'}
        with self.assertRaises(view.ViewError):self.action('ban')
        self.db['group_view_messages'].update_one({'message_id':25},{'$set':{'sender_is_user':False}})
        with self.assertRaises(view.ViewError):self.action('mute')
        self.assertFalse(any(call.args[0] in {'restrictChatMember','banChatMember'} for call in self.api.call_args_list))

    def test_reply_has_real_reply_and_forum_context_without_parse_mode(self):
        result=self.action('reply',text='<b>Plain text</b>')
        self.assertEqual(result['status'],'confirmed')
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendMessage')
        self.assertEqual(sent['reply_parameters'],{'message_id':25,'allow_sending_without_reply':False})
        self.assertEqual(sent['message_thread_id'],7);self.assertNotIn('parse_mode',sent)
        self.assertNotIn('as_user',sent)

    def test_utf16_text_limit(self):
        with self.assertRaises(view.ViewError):self.action('reply',text='😀'*2049)
        self.assertFalse(any(call.args[0]=='sendMessage' for call in self.api.call_args_list))

    def test_unconfirmed_reply_is_never_resent_on_same_request_id(self):
        request={'chat_id':CID,'message_id':25,'action':'reply','text':'hello','request_id':str(uuid.uuid4())}
        original=self.telegram
        self.api.side_effect=lambda method,payload:(None,{'ok':False}) if method=='sendMessage' else original(method,payload)
        with self.assertRaises(view.ViewError):self.service.act(request)
        result=self.service.act(request)
        self.assertFalse(result['ok']);self.assertEqual(result['status'],'unconfirmed')
        self.assertEqual(sum(call.args[0]=='sendMessage' for call in self.api.call_args_list),1)
        with self.assertRaises(view.ViewError):self.service.act({**request,'text':'different'})

    def test_mute_is_ten_minutes_and_unmute_uses_group_defaults(self):
        self.action('mute')
        payload=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='restrictChatMember')
        self.assertAlmostEqual(payload['until_date']-view.now().timestamp(),600,delta=2)
        self.api.reset_mock();self.action('unmute')
        payload=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='restrictChatMember')
        self.assertEqual(payload['permissions'],{'can_send_messages':True,'can_send_photos':False})

    def test_history_clear_does_not_delete_telegram_messages_or_other_data(self):
        self.db['served_users'].insert_one({'_id':123})
        self.db['playlists'].insert_one({'_id':'safe'})
        result=self.action('purge_history')
        self.assertFalse(result['recording']);self.assertEqual(result['deleted_count'],1)
        self.assertEqual(self.db['playlists'].count_documents({}),1);self.assertEqual(self.db['served_users'].count_documents({}),1)
        self.assertFalse(any(call.args[0]=='deleteMessage' for call in self.api.call_args_list))

    def test_protection_settings_use_existing_mongo_contract(self):
        self.action('protect',settings={'lock_links':True,'lock_polls':True})
        self.assertTrue(self.db['mgmt_chat_settings'].find_one({'chat_id':CID})['lock_links'])
        with self.assertRaises(view.ViewError):self.action('protect',settings={'owner_id':True})


class GroupViewRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__);self.api=Mock()
        register_group_view_routes(self.app,lambda:False,self.api)

    def test_internal_route_needs_secret_before_db_or_telegram(self):
        with patch('videl.utils.db.get_db') as db:
            response=self.app.test_client().get('/internal/group-view?chat_id=-100123')
        self.assertEqual(response.status_code,403);db.assert_not_called();self.api.assert_not_called()

    def test_route_rejects_personal_account_mode(self):
        app=Flask('authorized');register_group_view_routes(app,lambda:True,self.api)
        with patch('videl.utils.db.get_db',return_value=mongomock.MongoClient().videl):
            response=app.test_client().post('/internal/group-view',json={'as_user':True})
        self.assertEqual(response.status_code,400);self.api.assert_not_called()


class LocalAdminOptOutTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_admin_opt_out_does_not_require_bot_owner_identity(self):
        from videl.app.group_view import recording
        from videl.app.router import Context,Parsed
        db=mongomock.MongoClient().videl
        db['group_view_settings'].insert_one({'_id':CID,'enabled':True})
        ctx=Context(NS(),NS(chat=NS(id=CID),from_user=NS(id=123)),Parsed('groupview','off'))
        with patch('videl.app.group_view.get_db',return_value=db):screen=await recording(ctx)
        self.assertFalse(db['group_view_settings'].find_one({'_id':CID})['enabled'])
        self.assertIn('Off',screen.html)
