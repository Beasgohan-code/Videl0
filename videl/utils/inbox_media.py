"""Small owner-authenticated bot attachments. No arbitrary URLs/file IDs accepted."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import uuid
from datetime import timedelta
from pymongo.errors import DuplicateKeyError
from PIL import Image,UnidentifiedImageError
from videl.utils.group_view import ViewError,integer,now,parse_error,plain_from_rich,rich_text,store,RETENTION

UPLOAD_LIMIT=4*1024*1024
DOWNLOAD_LIMIT=8*1024*1024


def prepare(kind,data):
    if not data or len(data)>UPLOAD_LIMIT:raise ViewError('Attachments must be between 1 byte and 4 MB.',413)
    if kind=='photo':
        try:
            image=Image.open(io.BytesIO(data))
            if image.width*image.height>20_000_000 or max(image.size)>10000:raise ViewError('Photo dimensions are too large.')
            image.load();image=image.convert('RGB')
            output=io.BytesIO();image.save(output,format='JPEG',quality=90)
            encoded=output.getvalue()
            if len(encoded)>UPLOAD_LIMIT:raise ViewError('The converted photo is larger than 4 MB. Use a smaller image.',413)
            return encoded,'photo.jpg','image/jpeg'
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ViewError('Choose a valid JPG, PNG or WebP image.') from None
    mp4=len(data)>12 and data[4:8]==b'ftyp'
    webm=data.startswith(b'\x1a\x45\xdf\xa3')
    if kind=='video':
        if not mp4:raise ViewError('Use an MP4 video for inline playback (up to 4 MB).')
        return data,'video.mp4','video/mp4'
    if kind!='voice':raise ViewError('Choose photo, video or voice.')
    if not (mp4 or webm or data.startswith((b'OggS',b'ID3')) or data[:2] in (b'\xff\xfb',b'\xff\xf3',b'\xff\xf2')):
        raise ViewError('Voice recordings must be Ogg, WebM, MP3 or M4A audio.')
    try:
        with tempfile.TemporaryDirectory(prefix='videl-voice-') as folder:
            source=Path(folder)/'input';target=Path(folder)/'voice.ogg';source.write_bytes(data)
            probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(source)],capture_output=True,timeout=8,check=True)
            info=json.loads(probe.stdout)
            duration=float(info.get('format',{}).get('duration') or 0)
            if duration>120 or any(s.get('codec_type')=='video' for s in info.get('streams',[])):
                raise ViewError('Voice messages must be audio-only and at most 2 minutes.')
            subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(source),'-vn','-t','120','-c:a','libopus','-b:a','32k','-ac','1','-ar','48000',str(target)],capture_output=True,timeout=20,check=True)
            return target.read_bytes(),'voice.ogg','audio/ogg'
    except (OSError,ValueError,subprocess.SubprocessError):raise ViewError('Voice conversion is unavailable or this recording could not be decoded.') from None


def remembered(service,cid,result,me,kind,text,reply_id=None):
    media=result.get(kind)
    if kind=='photo' and isinstance(media,list):media=media[-1] if media else None
    store(service.db,{'chat_id':cid,'message_id':result['message_id'],'text':text,'date':now(),
        'sender_id':me['id'],'sender_is_user':True,'sender_name':me.get('first_name','Videl'),
        'sender_username':me.get('username',''),'is_bot':True,'reply_to_id':reply_id,
        'thread_id':result.get('message_thread_id'),'edited':False,'deleted':False,
        'media':{'kind':kind,'name':'','file_id':media.get('file_id'),'size':media.get('file_size'),'mime':media.get('mime_type')} if isinstance(media,dict) else None})


def send_attachment(service,body,data):
    cid,actor=service.access(body.get('chat_id'))
    me=service.rights(cid,actor,[])
    kind=body.get('kind');caption=body.get('text','')
    if not isinstance(caption,str):
        raise ViewError('Attachment captions are limited to 1024 Telegram text units.')
    is_html=False
    if caption.strip():
        caption,is_html=rich_text(caption,1024)
    reply_id=integer(body['message_id'],positive=True) if body.get('message_id') else None
    payload={'chat_id':cid}
    if caption:
        payload['caption']=caption
        if is_html: payload['parse_mode']='HTML'
    if reply_id:
        doc=service.db['group_view_messages'].find_one({'chat_id':cid,'message_id':reply_id,'expires_at':{'$gt':now()},'deleted':False})
        if doc is None:raise ViewError('The replied message is expired, deleted or unavailable.',404)
        payload['reply_parameters']={'message_id':reply_id,'allow_sending_without_reply':False}
        if doc.get('thread_id'):payload['message_thread_id']=doc['thread_id']
    try:key=str(uuid.UUID(body.get('request_id')))
    except (ValueError,TypeError,AttributeError):raise ViewError('A unique request ID is required.') from None
    signature={'chat_id':cid,'kind':kind,'reply_id':reply_id,'caption':caption,'sha256':hashlib.sha256(data).hexdigest()}
    prior=service.db['group_view_operations'].find_one({'_id':key})
    if prior:
        if prior.get('request')!=signature:raise ViewError('Request ID belongs to another attachment.',409)
        return {'ok':prior.get('status')=='confirmed','status':prior.get('status'),'error':'Earlier attachment was not resent. Check Telegram.' if prior.get('status')!='confirmed' else None}
    encoded,name,mime=prepare(kind,data)
    from videl.utils.group_view import indexes
    indexes(service.db)
    try:service.db['group_view_operations'].insert_one({'_id':key,'request':signature,'status':'pending','expires_at':now()+timedelta(days=7)})
    except DuplicateKeyError:return {'ok':False,'status':'pending','error':'This attachment request is already being processed; it was not resent.'}
    method={'photo':'sendPhoto','video':'sendVideo','voice':'sendVoice'}[kind]
    if kind=='video':payload['supports_streaming']=True
    fallback_note=None
    try:
        status,reply=service.api(method,payload,files={kind:(name,encoded,mime)})
        description=reply.get('description','') if isinstance(reply,dict) else ''
        if payload.get('parse_mode') and parse_error(status,description):
            retry={**payload,'caption':plain_from_rich(payload.get('caption',''))}
            retry.pop('parse_mode',None)
            status,reply=service.api(method,retry,files={kind:(name,encoded,mime)})
            payload=retry
            fallback_note='Telegram could not render the caption formatting, so it was sent as plain text.'
        if not status or not reply.get('ok') or not isinstance(reply.get('result'),dict):raise ViewError('Attachment delivery was not confirmed. Check Telegram before retrying.',502)
    except Exception:
        service.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'unconfirmed'}})
        raise
    warning=fallback_note
    try:
        service.db['group_view_operations'].update_one({'_id':key},{'$set':{'status':'confirmed'}})
        remembered(service,cid,reply['result'],me,kind,payload.get('caption',''),reply_id)
    except Exception:warning=fallback_note or 'Telegram confirmed the attachment; its local history receipt could not be saved.'
    return {'ok':True,'status':'confirmed','message_id':reply['result']['message_id'],'warning':warning}


def media_info(service,chat_id,message_id):
    cid,_=service.access(chat_id)
    policy=service.db['group_view_settings'].find_one({'_id':cid}) or {};days=policy.get('retention_days',7)
    if days not in RETENTION:days=7
    doc=service.db['group_view_messages'].find_one({'chat_id':cid,'message_id':integer(message_id,positive=True),'expires_at':{'$gt':now()},'date':{'$gte':now()-timedelta(days=days)},'deleted':False})
    media=(doc or {}).get('media') or {}
    if not media.get('file_id'):raise ViewError('This attachment is unavailable.',404)
    if (media.get('size') or 0)>DOWNLOAD_LIMIT:raise ViewError('This attachment exceeds the 8 MB viewer limit. Open it in Telegram.',413)
    result=service.call('getFile',{'file_id':media['file_id']})
    path=result.get('file_path','')
    if not path or '..' in path or path.startswith('/') or not all(c.isalnum() or c in '/_-. ' for c in path):raise ViewError('Telegram file path is unavailable.',502)
    if (result.get('file_size') or 0)>DOWNLOAD_LIMIT:raise ViewError('This attachment exceeds the viewer limit.',413)
    kind=media.get('kind')
    mime={'photo':'image/jpeg','voice':'audio/ogg','video':'video/mp4','audio':'audio/mpeg','animation':'video/mp4'}.get(kind,'application/octet-stream')
    if media.get('mime') in {'image/png','image/webp','video/webm','audio/mp4','audio/ogg','audio/mpeg','video/mp4'}:mime=media['mime']
    return path,mime,kind
