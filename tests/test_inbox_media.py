"""Bot inbox DMs and attachment boundaries, with real image/voice conversion tests."""
import io
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest
import uuid
from datetime import timedelta
from unittest.mock import Mock,patch
import mongomock
from PIL import Image
from videl.utils.group_view import GroupView,ViewError,store,now
from videl.utils.inbox_media import prepare,send_attachment,media_info,UPLOAD_LIMIT

class BotInboxTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().videl
        self.db['bot_inbox_peers'].insert_one({'_id':123,'type':'private','title':'Bot contact'})
        self.api=Mock(side_effect=self.telegram)
        self.service=GroupView(self.db,self.api)

    def telegram(self,method,payload,files=None):
        if method=='getMe':result={'id':777,'first_name':'Videl'}
        elif method in {'sendPhoto','sendVideo','sendVoice'}:
            key={'sendPhoto':'photo','sendVideo':'video','sendVoice':'voice'}[method]
            media={'file_id':'server-only-file','file_size':1024}
            result={'message_id':70,key:[media] if key=='photo' else media}
        elif method=='sendMessage':result={'message_id':71}
        elif method=='getFile':result={'file_path':'photos/file_1.jpg','file_size':1024}
        else:result=True
        return 200,{'ok':True,'result':result}

    def test_dm_read_and_text_send_do_not_use_group_membership_or_user_session(self):
        self.assertTrue(self.service.read(123)['is_private'])
        result=self.service.act({'chat_id':123,'action':'send','text':'Hello from my bot','request_id':str(uuid.uuid4())})
        self.assertTrue(result['ok'])
        self.assertFalse(any(call.args[0]=='getChatMember' for call in self.api.call_args_list))
        payload=next(call.args[1] for call in self.api.call_args_list if call.args[0]=='sendMessage')
        self.assertNotIn('reply_parameters',payload);self.assertNotIn('as_user',payload)

    def test_unknown_contact_and_group_moderation_in_dm_are_rejected(self):
        with self.assertRaises(ViewError):self.service.read(999)
        with self.assertRaises(ViewError):self.service.act({'chat_id':123,'action':'ban'})

    def test_dm_contact_metadata_is_saved_but_content_requires_recording(self):
        store(self.db,{'chat_id':456,'chat_type':'private','chat_title':'New person','message_id':1,'text':'private body','date':now()})
        self.assertEqual(self.db['bot_inbox_peers'].find_one({'_id':456})['title'],'New person')
        self.assertEqual(self.db['group_view_messages'].count_documents({'chat_id':456}),0)

    def test_attachment_file_ids_never_leak_through_message_json(self):
        self.db['group_view_messages'].insert_one({'chat_id':123,'message_id':1,'text':'','date':now(),'deleted':False,'expires_at':now()+timedelta(days=7),'media':{'kind':'photo','file_id':'secret-file-id'}})
        result=self.service.read(123)
        self.assertNotIn('file_id',result['items'][0]['media'])
        path,mime,kind=media_info(self.service,123,1)
        self.assertEqual((path,mime,kind),('photos/file_1.jpg','image/jpeg','photo'))

    def test_expired_media_cannot_be_downloaded(self):
        self.db['group_view_messages'].insert_one({'chat_id':123,'message_id':1,'date':now()-timedelta(days=8),'expires_at':now()+timedelta(days=7),'deleted':False,'media':{'kind':'photo','file_id':'old'}})
        with self.assertRaises(ViewError):media_info(self.service,123,1)
        self.assertFalse(any(call.args[0]=='getFile' for call in self.api.call_args_list))

    def test_photo_is_reencoded_not_trusted_by_file_extension(self):
        data=io.BytesIO();Image.new('RGB',(20,20),'red').save(data,format='PNG')
        encoded,name,mime=prepare('photo',data.getvalue())
        self.assertTrue(encoded.startswith(b'\xff\xd8'));self.assertEqual((name,mime),('photo.jpg','image/jpeg'))
        for bad in [b'<script>alert(1)</script>',b'not a photo']:
            with self.assertRaises(ViewError):prepare('photo',bad)
        with self.assertRaises(ViewError):prepare('photo',b'x'*(UPLOAD_LIMIT+1))

    def test_attachment_send_deduplicates_confirmed_uploads(self):
        data=io.BytesIO();Image.new('RGB',(8,8)).save(data,format='PNG')
        body={'chat_id':'123','kind':'photo','text':'caption','request_id':str(uuid.uuid4())}
        result=send_attachment(self.service,body,data.getvalue())
        self.assertTrue(result['ok']);self.assertTrue(send_attachment(self.service,body,data.getvalue())['ok'])
        sent=[call for call in self.api.call_args_list if call.args[0]=='sendPhoto']
        self.assertEqual(len(sent),1);self.assertIn('photo',sent[0].kwargs['files'])
        with self.assertRaises(ViewError):send_attachment(self.service,{**body,'text':'different'},data.getvalue())

    def test_unconfirmed_attachment_is_never_automatically_resent(self):
        data=b'\x00\x00\x00\x18ftypisom12345';body={'chat_id':123,'kind':'video','request_id':str(uuid.uuid4())}
        original=self.telegram
        self.api.side_effect=lambda method,payload,**kw:(None,{'ok':False}) if method=='sendVideo' else original(method,payload,**kw)
        with self.assertRaises(ViewError):send_attachment(self.service,body,data)
        self.assertFalse(send_attachment(self.service,body,data)['ok'])
        self.assertEqual(sum(call.args[0]=='sendVideo' for call in self.api.call_args_list),1)

    def test_video_format_and_caption_limits(self):
        with self.assertRaises(ViewError):prepare('video',b'not MP4')
        with self.assertRaises(ViewError):send_attachment(self.service,{'chat_id':123,'kind':'photo','text':'😀'*513},b'photo')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg required for real voice conversion')
    def test_webm_microphone_recording_becomes_telegram_ogg_opus(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'voice.webm'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.25','-c:a','libopus',str(path)],check=True)
            encoded,name,mime=prepare('voice',path.read_bytes())
        self.assertTrue(encoded.startswith(b'OggS'));self.assertEqual((name,mime),('voice.ogg','audio/ogg'))
