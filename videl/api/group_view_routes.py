"""Internal-only group viewer. Public access is through the owner-authenticated proxy."""
from flask import jsonify,request
from videl.utils.group_view import GroupView,ViewError


def error_payload(error):
    """A refused edit carries the revision the panel should reload from."""
    payload={'ok':False,'error':str(error)}
    if getattr(error,'conflict',False):
        payload['conflict']=True
        payload['revision']=getattr(error,'revision',None)
    return payload


def register_group_view_routes(app,authorized,api):
    @app.route('/internal/group-view',methods=['GET','POST'])
    def group_view():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from videl.utils.db import get_db
        try:
            service=GroupView(get_db(),api)
            if request.method=='GET':
                if request.args.get('info'):
                    result=service.info(request.args.get('chat_id'))
                else:
                    result=service.read(request.args.get('chat_id'),before=request.args.get('before'),query=request.args.get('q',''),sender=request.args.get('sender'))
            else:
                if request.content_length and request.content_length>20000:raise ViewError('Request body is too large.',413)
                body=request.get_json(silent=True)
                if not isinstance(body,dict):raise ViewError('A JSON object is required.')
                if 'as_user' in body:raise ViewError('Group viewer only operates through the bot.')
                result=service.act(body)
            return jsonify(result),200,{'Cache-Control':'no-store'}
        except ViewError as error:return jsonify(error_payload(error)),error.status,{'Cache-Control':'no-store'}
        except Exception:
            return jsonify({'ok':False,'error':'Group viewer unavailable. If an action was submitted, check Telegram before retrying.'}),503,{'Cache-Control':'no-store'}

    @app.route('/internal/premium-emoji',methods=['GET'])
    def premium_emoji():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from videl.utils.premium_emoji import EmojiError,fetch_emoji
        from flask import Response
        try:
            mime,payload=fetch_emoji(api,request.args.get('id',''))
        except EmojiError as error:
            return jsonify({'ok':False,'error':str(error)}),error.status,{'Cache-Control':'no-store'}
        return Response(payload,mimetype=mime,headers={'Cache-Control':'private, max-age=86400','X-Content-Type-Options':'nosniff'})

    @app.route('/internal/chat-photo',methods=['GET'])
    def chat_photo():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from flask import Response
        from videl.utils.db import get_db
        try:
            service=GroupView(get_db(),api)
            mime,payload=service.photo(request.args.get('chat_id'))
            return Response(payload,mimetype=mime,headers={'Cache-Control':'private, max-age=21600','X-Content-Type-Options':'nosniff'})
        except ViewError as error:
            return jsonify({'ok':False,'error':str(error)}),error.status,{'Cache-Control':'no-store'}
        except Exception:
            return jsonify({'ok':False,'error':'Chat photo unavailable.'}),503,{'Cache-Control':'no-store'}

    @app.route('/internal/bot-conversations',methods=['GET'])
    def bot_conversations():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from videl.utils.db import get_db
        try:
            db=get_db()
            if db is None:raise ViewError('MongoDB is not connected.',503)
            peers=list(db['bot_inbox_peers'].find({}, {'_id':1,'title':1,'type':1}).sort('seen_at',-1).limit(100))
            known={row['_id'] for row in peers}
            for row in db['served_chats'].find({}, {'_id':1}).limit(100):
                if row['_id']<0 and row['_id'] not in known:peers.append({'_id':row['_id'],'title':f"Group {row['_id']}",'type':'group'})
            return jsonify({'ok':True,'chats':[{'id':row['_id'],'title':row.get('title') or str(row['_id']),'type':row.get('type','group'),'members':None,'available':True} for row in peers[:150]],'truncated':len(peers)>150}),200,{'Cache-Control':'no-store'}
        except ViewError as error:return jsonify({'ok':False,'error':str(error)}),error.status
        except Exception:return jsonify({'ok':False,'error':'Bot conversations unavailable.'}),503

    @app.route('/internal/inbox-media',methods=['GET','POST'])
    def inbox_media():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from videl.utils.db import get_db
        from videl.utils.inbox_media import send_attachment,media_info,UPLOAD_LIMIT,DOWNLOAD_LIMIT
        try:
            service=GroupView(get_db(),api)
            if request.method=='POST':
                if request.content_length and request.content_length>UPLOAD_LIMIT+65536:raise ViewError('Uploads are limited to 4 MB.',413)
                if 'as_user' in request.form:raise ViewError('Only bot sending is supported.')
                file=request.files.get('file')
                if file is None:raise ViewError('Choose an attachment.')
                result=send_attachment(service,request.form.to_dict(),file.stream.read(UPLOAD_LIMIT+1))
                return jsonify(result),200,{'Cache-Control':'no-store'}
            from flask import send_file
            import io
            from urllib.parse import quote
            import requests
            import config
            path,mime,kind=media_info(service,request.args.get('chat_id'),request.args.get('message_id'))
            if not config.BOT_TOKEN:raise ViewError('Bot media is not configured.',503)
            # Only a Telegram-returned path is fetched, never a browser-provided URL.
            with requests.get(f'https://api.telegram.org/file/bot{config.BOT_TOKEN}/{quote(path,safe="/")}',stream=True,timeout=(5,15)) as upstream:
                if upstream.status_code!=200:raise ViewError('Telegram attachment is unavailable.',502)
                parts=[];length=0
                for part in upstream.iter_content(65536):
                    length+=len(part)
                    if length>DOWNLOAD_LIMIT:raise ViewError('Attachment exceeds the viewer limit.',413)
                    parts.append(part)
            response=send_file(io.BytesIO(b''.join(parts)),mimetype=mime,download_name='attachment',as_attachment=kind not in {'photo','video','voice','audio','animation'})
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
            return response
        except ViewError as error:return jsonify(error_payload(error)),error.status,{'Cache-Control':'no-store'}
        except Exception:return jsonify({'ok':False,'error':'Media response unconfirmed. Check Telegram before resending an attachment.'}),503,{'Cache-Control':'no-store'}

    @app.route('/internal/inbox-workspace',methods=['GET','POST'])
    def inbox_workspace():
        if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),403
        from videl.utils.db import get_db
        from videl.utils.inbox_workspace import InboxWorkspace
        try:
            workspace=InboxWorkspace(GroupView(get_db(),api))
            if request.method=='GET':result=workspace.read(request.args.get('chat_id'))
            else:
                if request.content_length and request.content_length>20000:raise ViewError('Request is too large.',413)
                body=request.get_json(silent=True)
                if not isinstance(body,dict):raise ViewError('A JSON object is required.')
                result=workspace.change(body)
            return jsonify(result),200,{'Cache-Control':'no-store'}
        except ViewError as error:return jsonify(error_payload(error)),error.status,{'Cache-Control':'no-store'}
        except Exception:return jsonify({'ok':False,'error':'Workspace storage is unavailable. Your editor was not sent to Telegram.'}),503,{'Cache-Control':'no-store'}
