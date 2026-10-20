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
        elif method=='sendPoll':result={'message_id':60}
        elif method=='setMessageReaction':result=True
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

    def test_read_advertises_rich_text_support(self):
        result=self.service.read(CID)
        self.assertIs(result['rich_text'],True)
        self.assertIn('rich_text',result)

    def test_captured_entities_become_safe_html(self):
        text="Hwy hu h hhhh \U0001F451"
        index=text.index("\U0001F451")
        entities=[NS(type=NS(name="BOLD"),offset=0,length=3),
            NS(type=NS(name="ITALIC"),offset=0,length=8),
            NS(type=NS(name="CUSTOM_EMOJI"),offset=index,length=2,custom_emoji_id=5042225965518816316),
            NS(type=NS(name="TEXT_LINK"),offset=4,length=5,url="https://example.com"),
            NS(type=NS(name="TEXT_LINK"),offset=0,length=3,url="javascript:alert(1)"),
            NS(type=NS(name="CODE"),offset=1,length=2)]
        html,used=view.entities_html(text,entities)
        self.assertTrue(used)
        # Telegram forbids code sharing characters with bold, so the normalizer
        # closes the bold run around the code span instead of emitting bad nesting.
        self.assertEqual(html,'<i><b>H</b></i><code>wy</code><i> hu h</i> hhhh <tg-emoji emoji-id="5042225965518816316">\U0001F451</tg-emoji>')
        self.assertNotIn('javascript',html)
        # An emoji plus its variation selector spans one visible character.
        html,used=view.entities_html("\U0001F44D\U0001F3FD",[NS(type=NS(name="CUSTOM_EMOJI"),offset=0,length=4,custom_emoji_id=5368324170671202286)])
        self.assertTrue(used);self.assertIn('<tg-emoji emoji-id="5368324170671202286">',html)
        self.assertEqual(view.entities_html("plain text",[])[1],False)

    def test_snapshot_marks_formatting_for_rendering(self):
        msg=NS(chat=NS(id=CID,type=ChatType.SUPERGROUP),id=77,date=view.now(),text="Bold",
            entities=[NS(type=NS(name="BOLD"),offset=0,length=4)],caption=None,
            from_user=NS(id=123,first_name="A",username="a",is_bot=False),reply_to_message=None,message_thread_id=None,
            photo=None,video=None,document=None,audio=None,voice=None,sticker=None,animation=None,video_note=None,poll=None,edit_date=None)
        item=view.snapshot(msg)
        self.assertEqual(item["text"],"<b>Bold</b>");self.assertTrue(item["rich"])
        self.assertFalse(view.snapshot(NS(**{**msg.__dict__,"text":"plain","entities":[]}))["rich"])

    def test_bot_replies_are_stored_as_rich_and_polls_marked(self):
        self.db["group_view_settings"].insert_one({"_id":CID,"enabled":True,"epoch":"e","enabled_at":view.now()-timedelta(minutes=5),"retention_days":7})
        self.action("send",text="<b>Hello</b> <tg-emoji emoji-id=\"5368324170671202286\">\U0001F44D</tg-emoji>")
        doc=self.db["group_view_messages"].find_one({"message_id":50})
        self.assertTrue(doc["rich"]);self.assertIn("<b>Hello</b>",doc["text"])

    def test_nested_formatting_is_normalized_for_telegram(self):
        # code/pre may not share characters with bold/italic/underline/spoiler.
        self.assertEqual(view.rich_text('Hwy <u>hu<code>h<tg-spoiler>hhhh</tg-spoiler></code></u>',4096),
                         ('Hwy <u>hu</u><code>hhhhh</code>',True))
        self.assertEqual(view.rich_text('<b>bold <i>both</b> italic</i>',4096),
                         ('<b>bold <i>both</i></b> italic',True))
        self.assertEqual(view.rich_text('<u>hu<code>h</code> more</u>',4096),
                         ('<u>hu</u><code>h</code><u> more</u>',True))
        self.assertEqual(view.rich_text('<b><b>double</b></b>',4096),('<b>double</b>',True))
        self.assertEqual(view.rich_text('<script>alert(1)</script>',100),('alert(1)',False))
        self.assertEqual(view.rich_text('<p>one</p><p>two</p>',100),('one\ntwo',False))

    def test_rich_send_retries_plain_only_after_explicit_entity_rejection(self):
        original=self.telegram
        calls=[];rejected=False
        def reject_once(method,payload):
            nonlocal rejected
            calls.append(payload)
            if method=='sendMessage' and not rejected:
                rejected=True
                return 400,{'ok':False,'description':"Bad Request: can't parse entities: nested tag"}
            return original(method,payload)
        self.api.side_effect=reject_once
        result=self.action('reply',text='<u>hu<code>h</code></u>')
        self.assertTrue(result['ok'])
        self.assertIn('plain text',result['warning'])
        sent=[c for c in calls if c.get('text','').startswith(('hu','<u>'))]
        self.assertEqual(sent[0]['parse_mode'],'HTML')
        self.assertNotIn('parse_mode',sent[-1]);self.assertEqual(sent[-1]['text'],'hu h'.replace(' ',''))

    def test_forward_requires_a_second_known_chat(self):
        self.db['served_chats'].insert_one({'_id':-100123457})
        self.db['group_view_settings'].insert_one({'_id':CID,'enabled':True,'epoch':'e','enabled_at':view.now()-timedelta(minutes=5),'retention_days':7})
        result=self.service.act({'chat_id':CID,'message_id':25,'action':'forward','to_chat_id':-100123457,'request_id':str(uuid.uuid4())})
        self.assertTrue(result['ok'])
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='forwardMessage')
        self.assertEqual(sent,{'chat_id':-100123457,'from_chat_id':CID,'message_id':25})
        with self.assertRaises(view.ViewError):self.service.act({'chat_id':CID,'message_id':25,'action':'forward','to_chat_id':CID,'request_id':str(uuid.uuid4())})
        with self.assertRaises(view.ViewError):self.service.act({'chat_id':CID,'message_id':25,'action':'forward','to_chat_id':-100999999,'request_id':str(uuid.uuid4())})

    def test_chat_photo_is_resolved_through_telegram(self):
        original=self.telegram
        def telegram(method,payload):
            if method=='getChat':return 200,{'ok':True,'result':{'photo':{'small_file_id':'photo-file-id'}}}
            if method=='getFile':return 200,{'ok':True,'result':{'file_path':'photos/file_1.jpg'}}
            return original(method,payload)
        self.api.side_effect=telegram
        # photo() imports the cached downloader lazily from premium_emoji.
        with patch('videl.utils.premium_emoji.fetch_file',return_value=('image/jpeg',b'jpeg')) as fetch:
            mime,payload=self.service.photo(CID)
        self.assertEqual((mime,payload),('image/jpeg',b'jpeg'))
        fetch.assert_called_once_with(self.api,'photo-file-id')

    def test_reaction_action_is_scoped_to_a_recorded_message(self):
        result=self.action('react',emoji='🔥')
        self.assertTrue(result['ok']);self.assertEqual(result['reaction'],'🔥')
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='setMessageReaction')
        self.assertEqual(sent['message_id'],25);self.deep_equal_reaction(sent['reaction'])
        doc=self.db['group_view_messages'].find_one({'message_id':25})
        self.assertEqual(doc['bot_reaction'],'🔥')
        with self.assertRaises(view.ViewError):self.action('react',emoji='🦄')
        with self.assertRaises(view.ViewError):self.service.act({'chat_id':CID,'message_id':999,'action':'react','emoji':'🔥','request_id':str(uuid.uuid4())})

    def deep_equal_reaction(self,reaction):
        self.assertEqual(reaction,[{'type':'emoji','emoji':'🔥'}])

    def test_poll_action_validates_and_stores_the_sent_poll(self):
        self.db['group_view_settings'].insert_one({'_id':CID,'enabled':True,'epoch':'e','enabled_at':view.now()-timedelta(minutes=5),'retention_days':7})
        result=self.service.act({'chat_id':CID,'action':'poll','question':'Ship it?','options':['Yes','No','Later'],
            'anonymous':True,'multiple':False,'request_id':str(uuid.uuid4())})
        self.assertTrue(result['ok']);self.assertEqual(result['message_id'],60)
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendPoll')
        self.assertEqual(sent['options'],['Yes','No','Later']);self.assertTrue(sent['is_anonymous']);self.assertFalse(sent['allows_multiple_answers'])
        doc=self.db['group_view_messages'].find_one({'message_id':60})
        self.assertEqual(doc['poll']['options'],['Yes','No','Later']);self.assertEqual(doc['media']['kind'],'poll')
        for options in [['one'],['x']*11,['ok','']]:
            with self.assertRaises(view.ViewError):
                self.service.act({'chat_id':CID,'action':'poll','question':'Q','options':options,'request_id':str(uuid.uuid4())})
        with self.assertRaises(view.ViewError):
            self.service.act({'chat_id':CID,'action':'poll','question':'','options':['a','b'],'request_id':str(uuid.uuid4())})

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

    def test_reply_has_real_reply_and_forum_context_with_rich_html(self):
        result=self.action('reply',text='<b>Plain text</b>')
        self.assertEqual(result['status'],'confirmed')
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendMessage')
        self.assertEqual(sent['reply_parameters'],{'message_id':25,'allow_sending_without_reply':False})
        self.assertEqual(sent['message_thread_id'],7);self.assertEqual(sent['parse_mode'],'HTML')
        self.assertNotIn('as_user',sent)

    def test_plain_reply_keeps_no_parse_mode(self):
        self.action('reply',text='Plain < 2 and > 1')
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendMessage')
        self.assertNotIn('parse_mode',sent);self.assertEqual(sent['text'],'Plain < 2 and > 1')

    def test_premium_emoji_and_formatting_are_sanitized(self):
        rich=self.action('reply',text='<tg-emoji emoji-id="5368324170671202286">🔥</tg-emoji> <b onclick="steal()">Launch</b> <a href="javascript:alert(1)">bad</a>')
        self.assertEqual(rich['status'],'confirmed')
        sent=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendMessage')
        self.assertEqual(sent['parse_mode'],'HTML')
        self.assertIn('<tg-emoji emoji-id="5368324170671202286">🔥</tg-emoji>',sent['text'])
        self.assertIn('<b>Launch</b>',sent['text'])
        self.assertNotIn('onclick',sent['text']);self.assertNotIn('javascript:',sent['text'])
        # Unknown/editor-only tags are dropped but their text is preserved.
        self.assertEqual(view.rich_text('<span data-spoiler="true">note</span> <i>safe</i>',100)[0],
                         'note <i>safe</i>')
        self.assertEqual(view.rich_text('<script>alert(1)</script>',100),('alert(1)',False))

    def test_invalid_premium_emoji_id_is_rejected(self):
        for bad in ['<tg-emoji emoji-id="abc">🔥</tg-emoji>','<tg-emoji>🔥</tg-emoji>']:
            with self.assertRaises(view.ViewError):view.rich_text(bad,100)
        self.assertEqual(view.rich_text('plain &amp; simple',100),('plain &amp; simple',False))
        with self.assertRaises(view.ViewError):view.rich_text('<b> </b>',100)
        with self.assertRaises(view.ViewError):view.rich_text('<b>'+'😀'*60+'</b>',100)

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
