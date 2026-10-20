"""Owner-only Mongo queue. Atomic claims; uncertain sends are never retried."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from videl.utils.db import get_db
from videl.utils.bot_api import call_bot_api

OWNER_ID = 6265999542


def _collection():
    db = get_db()
    if db is None:
        raise RuntimeError("Database unavailable")
    return db['scheduled_posts']


def enqueue(method, payload, scheduled_at, request_id):
    now = datetime.now(timezone.utc)
    if method not in {'sendMessage', 'sendPhoto'}:
        raise ValueError('Unsupported scheduled method')
    try:
        due = datetime.fromisoformat(str(scheduled_at).replace('Z', '+00:00'))
        identifier = str(uuid.UUID(str(request_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Use a valid request ID and an ISO date with a timezone') from None
    if due.tzinfo is None:
        raise ValueError('Scheduling requires an explicit timezone')
    due = due.astimezone(timezone.utc)
    # Serialize a stable identity, allowing a retry to discover an existing job.
    digest = hashlib.sha256(json.dumps([method,payload,due.isoformat()],sort_keys=True).encode()).hexdigest()
    col = _collection()
    existing = col.find_one({'_id':identifier, 'owner_id':OWNER_ID})
    if existing:
        if existing.get('fingerprint') != digest:
            raise ValueError('Request ID already belongs to a different post')
        return {'ok':True,'job_id':identifier,'status':existing['status'],'scheduled_at':due.isoformat()}
    if not now+timedelta(seconds=60) <= due <= now+timedelta(days=90):
        raise ValueError('Choose a time from 1 minute to 90 days ahead')
    document = {'_id':identifier,'owner_id':OWNER_ID,'status':'pending','method':method,
                'payload':payload,'due_at':due,'created_at':now,'fingerprint':digest}
    try:
        col.insert_one(document)
    except DuplicateKeyError:
        existing = col.find_one({'_id':identifier,'owner_id':OWNER_ID})
        if not existing or existing.get('fingerprint') != digest:
            raise ValueError('Conflicting schedule request') from None
        return {'ok':True,'job_id':identifier,'status':existing['status'],'scheduled_at':due.isoformat()}
    return {'ok':True,'job_id':identifier,'status':'pending','scheduled_at':due.isoformat()}


def _stamp(value):
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    return None


def list_jobs():
    docs = _collection().find({'owner_id':OWNER_ID}).sort('created_at',-1).limit(50)
    return [{'id':doc['_id'],'status':doc['status'],'chat_id':doc['payload']['chat_id'],
             'scheduled_at':doc['due_at'].replace(tzinfo=timezone.utc).isoformat(),
             'text':str(doc['payload'].get('text',doc['payload'].get('caption','')))[:200],
             'message_id':doc.get('message_id'),
             # Why a job stopped, when the dispatcher recorded a reason.
             'error':str(doc.get('error') or '')[:160] or None,
             'finished_at':_stamp(doc.get('finished_at'))} for doc in docs]


def retry_job(identifier, when=None):
    """Requeue a job Telegram explicitly rejected.

    Only ``failed`` qualifies: the dispatcher sets that state on a 4xx, which
    means nothing was delivered. ``sent``, ``sending``, ``unconfirmed`` and
    ``missed`` are never resent, because a duplicate post is worse than a
    missing one.
    """
    identifier = str(uuid.UUID(str(identifier)))
    col = _collection()
    now = datetime.now(timezone.utc)
    doc = col.find_one({'_id': identifier, 'owner_id': OWNER_ID})
    if not doc:
        raise ValueError('This scheduled post no longer exists')
    if doc.get('status') != 'failed':
        raise ValueError('Only a post Telegram rejected can be retried; sent and unconfirmed posts are never resent')
    due = now + timedelta(minutes=1)
    if when is not None:
        try:
            due = datetime.fromisoformat(str(when).replace('Z','+00:00'))
        except (TypeError, ValueError):
            raise ValueError('Use an ISO date with a timezone') from None
        if due.tzinfo is None:
            raise ValueError('Scheduling requires an explicit timezone')
        due = due.astimezone(timezone.utc)
        if not now + timedelta(seconds=60) <= due <= now + timedelta(days=90):
            raise ValueError('Choose a time from 1 minute to 90 days ahead')
    updated = col.update_one({'_id': identifier, 'owner_id': OWNER_ID, 'status': 'failed'},
                             {'$set': {'status': 'pending', 'due_at': due, 'finished_at': None,
                                       'error': None, 'claimed_at': None}})
    if not updated.modified_count:
        raise ValueError('This schedule changed while retrying; refresh its status')
    return {'ok': True, 'job_id': identifier, 'status': 'pending', 'scheduled_at': due.isoformat()}


def cancel_job(identifier):
    identifier = str(uuid.UUID(str(identifier)))
    result = _collection().update_one({'_id':identifier,'owner_id':OWNER_ID,'status':'pending'},
        {'$set':{'status':'cancelled','finished_at':datetime.now(timezone.utc)}})
    return result.modified_count == 1


def dispatch_one():
    """At most one send per tick. Catch-up >24h is marked missed, never sent."""
    col, now = _collection(), datetime.now(timezone.utc)
    col.update_many({'owner_id':OWNER_ID,'status':'sending','claimed_at':{'$lt':now-timedelta(minutes=10)}},
                    {'$set':{'status':'unconfirmed','finished_at':now}})
    col.update_many({'owner_id':OWNER_ID,'status':'pending','due_at':{'$lt':now-timedelta(days=1)}},
                    {'$set':{'status':'missed','finished_at':now}})
    doc = col.find_one_and_update({'owner_id':OWNER_ID,'status':'pending','due_at':{'$lte':now}},
        {'$set':{'status':'sending','claimed_at':now}},sort=[('due_at',1)],return_document=ReturnDocument.AFTER)
    if not doc:
        return
    try:
        status, result = call_bot_api(doc['method'],doc['payload'])
        accepted = bool(status == 200 and result.get('ok') and result.get('result',{}).get('message_id'))
        state = 'sent' if accepted else 'failed' if status and 400 <= status < 500 else 'unconfirmed'
        update = {'status':state,'finished_at':datetime.now(timezone.utc)}
        if accepted:
            update['message_id'] = result['result']['message_id']
        else:
            # Store why, so the monitor can explain instead of showing a bare state.
            description = str(result.get('description') or '').strip()[:160]
            update['error'] = description or f'Telegram returned HTTP {status or "no response"}' 
        col.update_one({'_id':doc['_id'],'status':'sending'}, {'$set':update})
    except Exception:
        # Includes DB failure after Telegram accepted. A stale sending record will
        # become unconfirmed; never put it back in pending or resend automatically.
        col.update_one({'_id':doc['_id'],'status':'sending'},
                       {'$set':{'status':'unconfirmed','finished_at':datetime.now(timezone.utc)}})
