import unittest
import uuid
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,patch
from videl.utils import scheduled_posts as scheduling

class ScheduledPostTests(unittest.TestCase):
    def test_enqueue_stores_snapshot_without_sending_and_dedupes(self):
        col=Mock();col.find_one.return_value=None
        payload={'chat_id':'-1001','text':'<b>Hello</b>','parse_mode':'HTML'}
        due=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
        key=str(uuid.uuid4())
        with patch.object(scheduling,'_collection',return_value=col),patch.object(scheduling,'call_bot_api') as send:
            result=scheduling.enqueue('sendMessage',payload,due,key)
            doc=col.insert_one.call_args.args[0]
            self.assertEqual(doc['status'],'pending')
            self.assertEqual(doc['payload'],payload)
            self.assertEqual(result['job_id'],key)
            col.find_one.return_value=doc
            scheduling.enqueue('sendMessage',payload,due,key)
            col.insert_one.assert_called_once()
            send.assert_not_called()
            with self.assertRaises(ValueError):scheduling.enqueue('sendMessage',{'text':'different'},due,key)

    def test_invalid_times_and_ids_cannot_schedule(self):
        col=Mock();col.find_one.return_value=None
        for due,key in [('2026-01-01T12:00:00',str(uuid.uuid4())),((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),str(uuid.uuid4())),('bad','bad')]:
            with self.subTest(due=due),patch.object(scheduling,'_collection',return_value=col):
                with self.assertRaises(ValueError):scheduling.enqueue('sendMessage',{},due,key)
        col.insert_one.assert_not_called()

    def test_claimed_job_sends_once_and_sets_sent_status(self):
        col=Mock();doc={'_id':'job','method':'sendMessage','payload':{'chat_id':'-1001','text':'Hi'}}
        col.find_one_and_update.return_value=doc
        with patch.object(scheduling,'_collection',return_value=col),patch.object(scheduling,'call_bot_api',return_value=(200,{'ok':True,'result':{'message_id':42}})) as send:
            scheduling.dispatch_one()
        self.assertEqual(col.find_one_and_update.call_args.args[0]['status'],'pending')
        send.assert_called_once_with('sendMessage',doc['payload'])
        self.assertEqual(col.update_one.call_args.args[1]['$set']['status'],'sent')
        self.assertEqual(col.update_one.call_args.args[1]['$set']['message_id'],42)

    def test_unknown_delivery_never_requeues(self):
        col=Mock();col.find_one_and_update.return_value={'_id':'job','method':'sendMessage','payload':{}}
        with patch.object(scheduling,'_collection',return_value=col),patch.object(scheduling,'call_bot_api',return_value=(None,{'ok':False})) as send:
            scheduling.dispatch_one()
        send.assert_called_once()
        self.assertEqual(col.update_one.call_args.args[1]['$set']['status'],'unconfirmed')
        for call in col.update_many.call_args_list:
            self.assertNotEqual(call.args[1]['$set']['status'],'pending')

    def test_cancel_only_pending_jobs(self):
        col=Mock();col.update_one.return_value.modified_count=0
        with patch.object(scheduling,'_collection',return_value=col):
            self.assertFalse(scheduling.cancel_job(str(uuid.uuid4())))
        self.assertEqual(col.update_one.call_args.args[0]['status'],'pending')
        self.assertEqual(col.update_one.call_args.args[0]['owner_id'],6265999542)
