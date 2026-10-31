import asyncio
import importlib
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from videl.utils import db
from videl.core import watcher
from videl.utils.permission_diagnostics import permission_rows
from pyrogram.enums import ChatMemberStatus

class RetentionTests(unittest.TestCase):
    def test_preview_is_default_and_saved_content_is_never_touched(self):
        collections={name:Mock() for name in ['chat_activity','user_activity','plugin_reminders','scheduled_posts']}
        for col in collections.values(): col.count_documents.return_value=3
        with patch.object(db,'_db',object()),patch.object(db,'_col',side_effect=collections.__getitem__):
            result=db.cleanup_old_data()
        self.assertTrue(result['ok'])
        self.assertFalse(result['applied'])
        self.assertEqual(result['counts']['chat_activity'],3)
        for col in collections.values(): col.delete_many.assert_not_called()

    def test_apply_uses_atomic_predicates_not_stale_ids(self):
        calls={}
        def get_col(name):
            col=Mock();col.delete_many.return_value.deleted_count=2;calls[name]=col;return col
        with patch.object(db,'_db',object()),patch.object(db,'_col',side_effect=get_col):
            result=db.cleanup_old_data(apply=True)
        self.assertTrue(result['ok'])
        self.assertEqual(set(calls),{'chat_activity','user_activity','plugin_reminders','scheduled_posts'})
        self.assertIn('$lt',calls['chat_activity'].delete_many.call_args.args[0]['last_active'])
        self.assertEqual(calls['plugin_reminders'].delete_many.call_args.args[0]['status'],'sent')
        # Only finished, delivered/cancelled queue rows are disposable. A
        # failure is the record someone will come back to read.
        queue=calls['scheduled_posts'].delete_many.call_args.args[0]
        self.assertEqual(queue['status'],{'$in':['sent','cancelled']})
        self.assertEqual(queue['finished_at']['$type'],'date')

    def test_missing_db_and_invalid_retention_fail_closed(self):
        with patch.object(db,'_db',None):self.assertFalse(db.cleanup_old_data(apply=True)['ok'])
        for value in (0,1,366,True,'30'):
            with self.assertRaises(ValueError):db.cleanup_old_data(value)

    def test_permission_diagnostics_dont_infer_rights_for_non_admin(self):
        member=SimpleNamespace(status=ChatMemberStatus.MEMBER,privileges=SimpleNamespace(can_delete_messages=True))
        self.assertTrue(all(state=='Missing' for _,state in permission_rows(member)))
        member.status=ChatMemberStatus.OWNER
        self.assertTrue(all(state=='Granted' for _,state in permission_rows(member)))

class WatchdogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await watcher.stop_watchdog()
        watcher._state['checks'].clear()
        watcher._state['last_tick']=None
        watcher._vc_idle_since.clear()
        watcher._bot_disconnected_checks=0
        watcher._bot_last_restart=0.0
        watcher._bot_restart_lock=None

    async def test_start_is_singleton_and_shutdown_cancels(self):
        async def forever():await asyncio.Event().wait()
        with patch.object(watcher,'watchdog',side_effect=forever):
            first=watcher.start_watchdog()
            self.assertIs(first,watcher.start_watchdog())
            await asyncio.sleep(0)
            await watcher.stop_watchdog()
            self.assertTrue(first.cancelled())
            self.assertFalse(watcher.watchdog_status()['running'])

    async def test_telegram_client_restarts_only_after_sustained_disconnect(self):
        client=SimpleNamespace(is_connected=False)
        async def restart():
            client.is_connected=True
        client.restart=AsyncMock(side_effect=restart)
        with patch.object(watcher,'bot',client):
            with self.assertRaisesRegex(RuntimeError,'second failed health check'):
                await watcher._check_bot()
            client.restart.assert_not_awaited()
            await watcher._check_bot()
            client.restart.assert_awaited_once()
            self.assertTrue(client.is_connected)
            self.assertEqual(watcher._bot_disconnected_checks,0)

    async def test_job_failure_is_isolated_and_recovery_recorded(self):
        bad=AsyncMock(side_effect=RuntimeError('unavailable'))
        self.assertFalse(await watcher._run_check('database',bad))
        self.assertTrue(await watcher._run_check('downloads',AsyncMock()))
        self.assertEqual(watcher._state['checks']['database'],'failed')
        self.assertTrue(await watcher._run_check('database',AsyncMock()))
        self.assertEqual(watcher._state['checks']['database'],'ok')

    async def test_cancellation_propagates(self):
        with self.assertRaises(asyncio.CancelledError):
            await watcher._run_check('cancel',AsyncMock(side_effect=asyncio.CancelledError()))

    async def test_downloads_defer_while_queue_active(self):
        with patch.object(watcher,'chat_queues',{1:[{'url':'cached audio'}]}),patch.object(watcher,'_sweep_downloads') as sweep:
            self.assertEqual(await watcher._cleanup_downloads(),0)
            sweep.assert_not_called()

    async def test_idle_call_resets_when_queue_becomes_active(self):
        fake=SimpleNamespace(calls={123:object()},leave_call=AsyncMock())
        watcher._vc_idle_since[123]=time.monotonic()-10000
        with patch.object(watcher,'call_py',fake),patch.object(watcher,'queue_size',return_value=1):
            await watcher._auto_leave_idle_vcs()
            fake.leave_call.assert_not_called()
            self.assertNotIn(123,watcher._vc_idle_since)
        watcher._vc_idle_since[123]=time.monotonic()-10000
        with patch.object(watcher,'call_py',fake),patch.object(watcher,'queue_size',return_value=0):
            await watcher._auto_leave_idle_vcs()
            fake.leave_call.assert_awaited_once_with(123)

    def test_download_sweep_preserves_new_protected_and_symlink_files(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            old=root/'old.mp3';old.write_bytes(b'old')
            live=root/'live.mp3';live.write_bytes(b'live')
            fresh=root/'new.mp3';fresh.write_bytes(b'new')
            link=root/'link';link.symlink_to(old)
            stale=time.time()-100000
            for file in [old,live]:os.utime(file,(stale,stale))
            with patch.object(watcher,'DOWNLOAD_DIR',root):self.assertEqual(watcher._sweep_downloads({live.resolve()}),1)
            self.assertTrue(live.exists());self.assertTrue(fresh.exists());self.assertTrue(link.is_symlink())
