"""Owner workspace contract, concurrency and permission regressions (offline Mongo)."""
import unittest
import uuid
from datetime import timedelta
from unittest.mock import Mock
import mongomock
from flask import Flask
from videl.utils.group_view import GroupView,ViewError,OWNER_ID,now
from videl.utils.inbox_workspace import InboxWorkspace
from videl.api.group_view_routes import register_group_view_routes

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().videl
        self.db.bot_inbox_peers.insert_one({'_id':123,'type':'private'})
        self.db.served_chats.insert_one({'_id':-100123})
        self.api=Mock(return_value=(200,{'ok':True,'result':{'status':'administrator'}}))
        self.workspace=InboxWorkspace(GroupView(self.db,self.api))

    def change(self,action,**body):
        return self.workspace.change({'action':action,'chat_id':123,**body})

    def test_drafts_use_mongo_and_never_send_to_telegram(self):
        self.assertEqual(self.workspace.read(123)['chat']['draft'],'')
        result=self.change('draft',value='<b>Plain owner text</b>',revision=0)
        self.assertEqual(result['chat']['draft'],'<b>Plain owner text</b>')
        other=InboxWorkspace(GroupView(self.db,self.api))
        self.assertEqual(other.read(123)['chat']['draft'],'<b>Plain owner text</b>')
        self.api.assert_not_called()

    def test_conflicting_draft_cannot_overwrite_newer_edit(self):
        self.change('draft',value='first device',revision=0)
        with self.assertRaises(ViewError) as error:self.change('draft',value='stale device',revision=0)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(self.workspace.read(123)['chat']['draft'],'first device')

    def test_draft_notes_and_organization_have_independent_revisions(self):
        self.change('draft',value='draft',revision=0)
        self.change('notes',value='owner notes',revision=0)
        result=self.change('organize',pinned=True,tags=['support','support','urgent'],revision=0)
        self.assertEqual(result['chat']['tags'],['support','urgent'])
        self.assertEqual(result['chat']['revisions'],{'draft':1,'notes':1,'organize':1})

    def test_global_summary_never_contains_private_draft_or_notes(self):
        self.change('draft',value='private draft',revision=0)
        self.change('notes',value='private notes',revision=0)
        result=self.workspace.read()
        self.assertNotIn('draft',result['conversations'][0]);self.assertNotIn('notes',result['conversations'][0])

    def test_lengths_tags_and_revision_values_are_bounded(self):
        cases=[('draft',{'value':'😀'*2049,'revision':0}),('notes',{'value':'x'*2001,'revision':0}),
               ('organize',{'pinned':'yes','tags':[],'revision':0}),('organize',{'pinned':True,'tags':[''] ,'revision':0}),
               ('organize',{'pinned':True,'tags':['a']*6,'revision':0}),('organize',{'pinned':True,'tags':['x'*21],'revision':0}),
               ('draft',{'value':'hello','revision':True})]
        for action,body in cases:
            with self.subTest(action=action,body=str(body)[:60]),self.assertRaises(ViewError):self.change(action,**body)

    def test_group_chat_details_recheck_actual_owner_membership(self):
        self.workspace.read(-100123)
        self.api.assert_called_once_with('getChatMember',{'chat_id':-100123,'user_id':OWNER_ID})
        self.api.return_value=(200,{'ok':True,'result':{'status':'member'}})
        for operation in [lambda:self.workspace.read(-100123),lambda:self.workspace.change({'action':'notes','chat_id':-100123,'value':'no','revision':0})]:
            with self.assertRaises(ViewError):operation()

    def test_owner_id_from_body_cannot_change_document_ownership(self):
        self.change('draft',value='ours',revision=0,owner_id=999)
        doc=self.db.inbox_owner_chats.find_one({})
        self.assertEqual(doc['owner_id'],OWNER_ID);self.assertEqual(doc['_id'],f'{OWNER_ID}:123')

    def test_review_markers_only_move_forward_and_never_call_telegram(self):
        for mid in [7,9]:self.db.group_view_messages.insert_one({'chat_id':123,'message_id':mid,'expires_at':now()+timedelta(days=1)})
        self.change('review',message_id=9);result=self.change('review',message_id=7)
        self.assertEqual(result['chat']['last_reviewed_message_id'],9)
        self.api.assert_not_called()
        with self.assertRaises(ViewError):self.change('review',message_id=99999)

    def test_quick_replies_can_create_edit_and_delete_without_sending(self):
        rid=str(uuid.uuid4())
        result=self.change('save_reply',id=rid,title='Welcome',text='Hello there',revision=0)
        self.assertEqual(result['reply']['revision'],1)
        self.assertEqual(self.workspace.read()['quick_replies'][0]['text'],'Hello there')
        self.change('save_reply',id=rid,title='Welcome back',text='Good to see you',revision=1)
        self.change('delete_reply',id=rid,revision=2)
        self.assertEqual(self.workspace.read()['quick_replies'],[]);self.api.assert_not_called()

    def test_quick_reply_conflicts_do_not_overwrite_or_remove_newer_data(self):
        rid=str(uuid.uuid4());self.change('save_reply',id=rid,title='Title',text='Original',revision=0)
        for action in ['save_reply','delete_reply']:
            with self.assertRaises(ViewError):self.change(action,id=rid,title='Stale',text='Stale',revision=0)
        self.assertEqual(self.workspace.read()['quick_replies'][0]['text'],'Original')

    def test_unknown_chat_or_action_cannot_create_workspace_state(self):
        with self.assertRaises(ViewError):self.workspace.change({'action':'draft','chat_id':999,'value':'bad','revision':0})
        with self.assertRaises(ViewError):self.change('arbitrary_database_action')
        self.assertEqual(self.db.inbox_owner_chats.count_documents({}),0)

    def test_internal_workspace_endpoint_denies_before_any_data_access(self):
        app=Flask('workspace-test');register_group_view_routes(app,lambda:False,self.api)
        for method in ['get','post']:
            response=getattr(app.test_client(),method)('/internal/inbox-workspace')
            self.assertEqual(response.status_code,403)
        self.api.assert_not_called()
