"""Owner-only Mongo queue. Atomic claims; uncertain sends are never retried.

Two kinds of failure are deliberately treated differently:

* a **rate limit** (HTTP 429) proves nothing was delivered, so the job returns
  to the queue automatically and waits the interval Telegram asked for;
* any other rejection is final and waits for the owner, because a duplicate
  post is worse than a missing one.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from videl.utils.db import get_db
from videl.utils.bot_api import call_bot_api

OWNER_ID = 6265999542
# Telegram rate limits are transient: retry a few times, then stop and say so.
MAX_RATE_LIMITED_RETRIES = 3
MIN_RETRY_SECONDS = 5
MAX_RETRY_SECONDS = 3600
# A repeat keeps its wall-clock UTC time, so a daily note stays at the same hour.
REPEAT_INTERVALS = {'daily': timedelta(days=1), 'weekly': timedelta(days=7)}
log = logging.getLogger(__name__)


def _collection():
    db = get_db()
    if db is None:
        raise RuntimeError("Database unavailable")
    return db['scheduled_posts']


def _repeat_interval(repeat):
    if repeat in (None, '', 'none'):
        return None
    if repeat not in REPEAT_INTERVALS:
        raise ValueError('Repeat must be once, daily or weekly')
    return REPEAT_INTERVALS[repeat]


def enqueue(method, payload, scheduled_at, request_id, repeat=None):
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
    repeat = None if repeat in (None, '', 'none') else repeat
    _repeat_interval(repeat)
    # Serialize a stable identity, allowing a retry to discover an existing job.
    digest = hashlib.sha256(json.dumps([method,payload,due.isoformat(),repeat],sort_keys=True).encode()).hexdigest()
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
    if repeat:
        document['repeat'] = repeat
    try:
        col.insert_one(document)
    except DuplicateKeyError:
        existing = col.find_one({'_id':identifier,'owner_id':OWNER_ID})
        if not existing or existing.get('fingerprint') != digest:
            raise ValueError('Conflicting schedule request') from None
        return {'ok':True,'job_id':identifier,'status':existing['status'],'scheduled_at':due.isoformat()}
    return {'ok':True,'job_id':identifier,'status':'pending','scheduled_at':due.isoformat(),
            'repeat':repeat}


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
             # How many times a rate limit pushed this job back into the queue.
             'attempts':int(doc.get('attempts') or 0),
             # Why a job stopped, when the dispatcher recorded a reason.
             'repeat':doc.get('repeat'),
             # How many times a series has actually delivered.
             'sent_count':int(doc.get('sent_count') or 0),
             'skipped':int(doc.get('skipped') or 0),
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


def duplicate_job(identifier, when=None):
    """Queue a fresh copy of a post that has already finished.

    A copy is a *new* job, so it may follow any outcome — including ``sent`` —
    without ever resending the original. A job still waiting or in flight is
    refused: copy after it settles, or the group would get two posts at once.
    """
    identifier = str(uuid.UUID(str(identifier)))
    col = _collection()
    now = datetime.now(timezone.utc)
    doc = col.find_one({'_id': identifier, 'owner_id': OWNER_ID})
    if not doc:
        raise ValueError('This scheduled post no longer exists')
    if doc.get('status') in {'pending', 'sending'}:
        raise ValueError('This post is still in the queue; cancel it or wait for it to finish')
    due = now + timedelta(hours=1)
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
    method = doc.get('method')
    if method not in {'sendMessage', 'sendPhoto'}:
        raise ValueError('This post cannot be copied')
    payload = json.loads(json.dumps(doc.get('payload') or {}))
    fresh = str(uuid.uuid4())
    digest = hashlib.sha256(json.dumps([method,payload,due.isoformat()],sort_keys=True).encode()).hexdigest()
    copy = {'_id': fresh, 'owner_id': OWNER_ID, 'status': 'pending', 'method': method,
            'payload': payload, 'due_at': due, 'created_at': now, 'fingerprint': digest,
            'duplicated_from': identifier, 'attempts': 0}
    if doc.get('repeat') in REPEAT_INTERVALS:
        copy['repeat'] = doc['repeat']
    col.insert_one(copy)
    return {'ok': True, 'job_id': fresh, 'status': 'pending', 'scheduled_at': due.isoformat(),
            'duplicated_from': identifier}


def cancel_job(identifier):
    identifier = str(uuid.UUID(str(identifier)))
    result = _collection().update_one({'_id':identifier,'owner_id':OWNER_ID,'status':'pending'},
        {'$set':{'status':'cancelled','finished_at':datetime.now(timezone.utc)}})
    return result.modified_count == 1


def _retry_after(result, status):
    """Seconds Telegram asked us to wait, or None when this is not a rate limit."""
    if status != 429:
        return None
    parameters = result.get('parameters') if isinstance(result, dict) else None
    try:
        seconds = int((parameters or {}).get('retry_after') or 0)
    except (TypeError, ValueError):
        seconds = 0
    return max(MIN_RETRY_SECONDS, min(seconds or 30, MAX_RETRY_SECONDS))


def _alert(job, state, reason):
    """Tell the owner once, in the log channel, that a post did not arrive."""
    try:
        import config
        channel = int(getattr(config, 'LOG_CHANNEL_ID', 0) or 0)
    except Exception:
        channel = 0
    if not channel:
        return False
    text = (f"<b>Scheduled post {state}</b>\n"
            f"Chat: <code>{job.get('payload', {}).get('chat_id')}</code>\n"
            f"Job: <code>{job.get('_id')}</code>\n"
            f"Reason: {reason}")
    try:
        status, _ = call_bot_api('sendMessage', {'chat_id': channel, 'text': text,
                                                 'parse_mode': 'HTML',
                                                 'disable_web_page_preview': True})
        return status == 200
    except Exception:
        log.debug('scheduled-post alert failed', exc_info=True)
        return False


def _skip_missed_series(col, now):
    """A repeat that fell more than a day behind skips ahead instead of dying.

    One missed daily note is not a reason to end the series, but it is also not
    a reason to send three copies at once: jump to the next upcoming occurrence.
    """
    stale = col.find({'owner_id':OWNER_ID, 'status':'pending',
                      'due_at':{'$lt':now-timedelta(days=1)},
                      'repeat':{'$in':list(REPEAT_INTERVALS)}})
    for doc in stale:
        interval = REPEAT_INTERVALS[doc['repeat']]
        due = doc['due_at']
        # Some stores hand back naive datetimes; the queue always speaks UTC.
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        hops = 0
        while due <= now and hops < 400:
            due += interval
            hops += 1
        col.update_one({'_id':doc['_id'], 'status':'pending'},
                       {'$set':{'due_at':due,
                                'skipped':int(doc.get('skipped') or 0)+hops,
                                'error':f'{hops} occurrence(s) skipped while the bot was offline'}})


def dispatch_one():
    """At most one send per tick. Catch-up >24h is marked missed, never sent."""
    col, now = _collection(), datetime.now(timezone.utc)
    col.update_many({'owner_id':OWNER_ID,'status':'sending','claimed_at':{'$lt':now-timedelta(minutes=10)}},
                    {'$set':{'status':'unconfirmed','finished_at':now}})
    _skip_missed_series(col, now)
    col.update_many({'owner_id':OWNER_ID,'status':'pending','due_at':{'$lt':now-timedelta(days=1)}},
                    {'$set':{'status':'missed','finished_at':now}})
    doc = col.find_one_and_update({'owner_id':OWNER_ID,'status':'pending','due_at':{'$lte':now}},
        {'$set':{'status':'sending','claimed_at':now}},sort=[('due_at',1)],return_document=ReturnDocument.AFTER)
    if not doc:
        return
    try:
        status, result = call_bot_api(doc['method'],doc['payload'])
        wait = _retry_after(result, status)
        attempts = int(doc.get('attempts') or 0)
        if wait is not None and attempts < MAX_RATE_LIMITED_RETRIES:
            # Nothing was delivered: put it back with the delay Telegram asked
            # for, and say so rather than showing a rejection that never was.
            col.update_one({'_id':doc['_id'],'status':'sending'}, {'$set':{
                'status':'pending','due_at':datetime.now(timezone.utc)+timedelta(seconds=wait+2),
                'claimed_at':None,'finished_at':None,'attempts':attempts+1,
                'error':f'Telegram rate limit; retrying in {wait}s (attempt {attempts+1} of {MAX_RATE_LIMITED_RETRIES})'}})
            return
        accepted = bool(status == 200 and result.get('ok') and result.get('result',{}).get('message_id'))
        if wait is not None:
            state = 'failed'
        else:
            state = 'sent' if accepted else 'failed' if status and 400 <= status < 500 else 'unconfirmed'
        update = {'status':state,'finished_at':datetime.now(timezone.utc)}
        reason = ''
        if accepted:
            update['message_id'] = result['result']['message_id']
            interval = REPEAT_INTERVALS.get(doc.get('repeat'))
            if interval:
                # A series is never "finished": the same record carries its next
                # occurrence, so the monitor shows one line per recurring post.
                update.update({'status':'pending','due_at':doc['due_at']+interval,
                               'finished_at':None,'claimed_at':None,'error':None,
                               'attempts':0,'sent_count':int(doc.get('sent_count') or 0)+1,
                               'last_sent_at':datetime.now(timezone.utc)})
                state = 'pending'
        else:
            # Store why, so the monitor can explain instead of showing a bare state.
            description = str(result.get('description') or '').strip()[:160]
            reason = description or f'Telegram returned HTTP {status or "no response"}'
            if wait is not None:
                reason = f'Rate limit persisted after {attempts} automatic retries: {reason}'[:200]
            update['error'] = reason
            update['attempts'] = attempts
        col.update_one({'_id':doc['_id'],'status':'sending'}, {'$set':update})
        if state in {'failed', 'unconfirmed'}:
            _alert(doc, state, reason or 'delivery could not be confirmed')
    except Exception:
        # Includes DB failure after Telegram accepted. A stale sending record will
        # become unconfirmed; never put it back in pending or resend automatically.
        col.update_one({'_id':doc['_id'],'status':'sending'},
                       {'$set':{'status':'unconfirmed','finished_at':datetime.now(timezone.utc)}})
        _alert(doc, 'unconfirmed', 'the dispatcher could not finish; check Telegram before resending')
