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
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from videl.utils.db import get_db
from videl.utils.bot_api import call_bot_api

OWNER_ID = 6265999542
# Telegram rate limits are transient: retry a few times, then stop and say so.
MAX_RATE_LIMITED_RETRIES = 3
MIN_RETRY_SECONDS = 5
MAX_RETRY_SECONDS = 3600
# A repeat without a timezone keeps its UTC hour (the historical behaviour).
# A repeat with an IANA timezone keeps its *local* wall clock instead, so a
# 09:00 daily note stays at 09:00 after a daylight-saving change.
REPEAT_INTERVALS = {'daily': timedelta(days=1), 'weekly': timedelta(days=7)}
WALL_TIME = re.compile(r'^([01][0-9]|2[0-3]):([0-5][0-9])$')
log = logging.getLogger(__name__)


def _zone(name):
    """Resolve an IANA zone. A bad name is an error, never a silent UTC."""
    text = str(name or '').strip()
    if not text or len(text) > 64 or any(character.isspace() for character in text):
        raise ValueError('Use an IANA timezone name, for example Asia/Kolkata')
    try:
        return text, ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('That timezone is not recognised') from None


def _as_utc(value):
    if not isinstance(value, datetime):
        raise ValueError('A stored time is invalid')
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def localize_wall_time(wall, zone):
    """Map a naive wall-clock time onto a real instant in ``zone``.

    Two days a year a wall clock is not a function of UTC:

    * an **ambiguous** time (autumn fall-back) resolves to its FIRST occurrence,
      so a series sends once and never twice;
    * a **nonexistent** time (spring-forward gap) moves forward to the first
      minute that exists — a 02:30 note runs at 03:00 that day, and the next
      day is 02:30 again, because the series anchor is kept as intended.

    Returns ``(utc_datetime, adjusted)``; ``adjusted`` is True only for the gap.
    """
    wall = wall.replace(microsecond=0)

    def resolve(candidate):
        return candidate.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)

    instant = resolve(wall)
    if instant.astimezone(zone).replace(tzinfo=None) == wall:
        return instant, False
    probe = wall
    for _ in range(181):
        probe += timedelta(minutes=1)
        candidate = resolve(probe)
        if candidate.astimezone(zone).replace(tzinfo=None) == probe:
            return candidate, True
    return instant, False


def _wall_of(value, zone):
    return _as_utc(value).astimezone(zone).replace(tzinfo=None)


def _anchor_from(due, zone, wall_time=None):
    """The intended local wall clock for a series, independent of gap shifts."""
    local = _wall_of(due, zone)
    if wall_time not in (None, ''):
        match = WALL_TIME.fullmatch(str(wall_time))
        if not match:
            raise ValueError('wall_time must be a 24-hour HH:MM value')
        local = local.replace(hour=int(match.group(1)), minute=int(match.group(2)),
                              second=0, microsecond=0)
        resolved, _ = localize_wall_time(local, zone)
        if abs(resolved - _as_utc(due)) > timedelta(hours=3):
            raise ValueError('The local time does not match the scheduled instant')
    return local.replace(microsecond=0)


def _collection():
    db = get_db()
    if db is None:
        raise RuntimeError("Database unavailable")
    return db['scheduled_posts']


def _repeat_interval(repeat):
    if repeat in (None, '', 'none'):
        return None
    try:
        return REPEAT_INTERVALS[repeat]
    except (KeyError, TypeError):
        # TypeError covers JSON that sent a list or object where a word belongs:
        # that is a bad request, not a server error.
        raise ValueError('Repeat must be once, daily or weekly') from None


def enqueue(method, payload, scheduled_at, request_id, repeat=None,
            timezone_name=None, wall_time=None):
    """Queue one post (or the first occurrence of a repeating one).

    ``timezone_name`` is an IANA zone; without it a repeat keeps the historical
    fixed-UTC-interval behaviour. ``wall_time`` is the HH:MM the owner actually
    chose, sent separately so that a first occurrence shifted out of a
    daylight-saving gap does not drag the whole series with it.
    """
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
    zone_name = zone = anchor = None
    if timezone_name not in (None, ''):
        zone_name, zone = _zone(timezone_name)
        anchor = _anchor_from(due, zone, wall_time)
    elif wall_time not in (None, ''):
        raise ValueError('A wall time needs a timezone')
    # Serialize a stable identity, allowing a retry to discover an existing job.
    # The zone and anchor are part of it: the same request ID may not silently
    # turn into a different series.
    identity = [method, payload, due.isoformat(), repeat]
    if zone_name or anchor is not None:
        # Only zoned requests add fields, so an in-flight request created before
        # this feature can still be retried and recognised by its old digest.
        identity += [zone_name, anchor.isoformat(timespec='seconds') if anchor else None]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    col = _collection()
    existing = col.find_one({'_id':identifier, 'owner_id':OWNER_ID})
    if existing:
        if existing.get('fingerprint') != digest:
            raise ValueError('Request ID already belongs to a different post')
        return {'ok':True,'job_id':identifier,'status':existing['status'],
                'scheduled_at':due.isoformat(), 'timezone':zone_name,
                'paused':bool(existing.get('paused'))}
    if not now+timedelta(seconds=60) <= due <= now+timedelta(days=90):
        raise ValueError('Choose a time from 1 minute to 90 days ahead')
    document = {'_id':identifier,'owner_id':OWNER_ID,'status':'pending','method':method,
                'payload':payload,'due_at':due,'created_at':now,'fingerprint':digest}
    if repeat:
        document['repeat'] = repeat
        if anchor is not None:
            # Kept as the *intended* wall clock, not the shifted first run.
            document['repeat_anchor'] = anchor.isoformat(timespec='seconds')
    if zone_name:
        document['timezone'] = zone_name
    try:
        col.insert_one(document)
    except DuplicateKeyError:
        existing = col.find_one({'_id':identifier,'owner_id':OWNER_ID})
        if not existing or existing.get('fingerprint') != digest:
            raise ValueError('Conflicting schedule request') from None
        return {'ok':True,'job_id':identifier,'status':existing['status'],
                'scheduled_at':due.isoformat(), 'timezone':zone_name,
                'paused':bool(existing.get('paused'))}
    return {'ok':True,'job_id':identifier,'status':'pending','scheduled_at':due.isoformat(),
            'repeat':repeat,'timezone':zone_name}


def _stamp(value):
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    return None


def _job_view(doc):
    scheduled = _as_utc(doc['due_at'])
    zone_name = doc.get('timezone')
    scheduled_local = None
    if zone_name:
        try:
            _, zone = _zone(zone_name)
            scheduled_local = scheduled.astimezone(zone).isoformat()
        except ValueError:
            zone_name = None
    return {'id': doc['_id'], 'status': doc['status'],
            'chat_id': doc['payload']['chat_id'],
            'scheduled_at': scheduled.isoformat(),
            # The same instant expressed in the series' own zone, for display.
            'scheduled_local': scheduled_local,
            'timezone': zone_name,
            'paused': bool(doc.get('paused')),
            # True when the current occurrence had to move out of a DST gap.
            'dst_adjusted': bool(doc.get('dst_adjusted')),
            'text': str(doc['payload'].get('text', doc['payload'].get('caption', '')))[:200],
            'message_id': doc.get('message_id'),
            # How many times a rate limit pushed this job back into the queue.
            'attempts': int(doc.get('attempts') or 0),
            'repeat': doc.get('repeat'),
            # How many times a series has actually delivered.
            'sent_count': int(doc.get('sent_count') or 0),
            'skipped': int(doc.get('skipped') or 0),
            'error': str(doc.get('error') or '')[:160] or None,
            # Informational: a skip or a catch-up, not a delivery failure.
            'note': str(doc.get('note') or '')[:160] or None,
            'finished_at': _stamp(doc.get('finished_at'))}


def list_jobs():
    docs = _collection().find({'owner_id':OWNER_ID}).sort('created_at',-1).limit(50)
    return [_job_view(doc) for doc in docs]


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
                                       'error': None, 'note': None, 'claimed_at': None}})
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
        zone_name = doc.get('timezone')
        if zone_name:
            # The copy is its own series: anchor it to the time that was just
            # chosen, not to the original's wall clock.
            _, zone = _zone(zone_name)
            copy['timezone'] = zone_name
            copy['repeat_anchor'] = _anchor_from(due, zone).isoformat(timespec='seconds')
    elif doc.get('timezone'):
        # A one-shot keeps the zone for display only.
        copy['timezone'] = doc.get('timezone')
    col.insert_one(copy)
    return {'ok': True, 'job_id': fresh, 'status': 'pending', 'scheduled_at': due.isoformat(),
            'duplicated_from': identifier}


def cancel_job(identifier):
    identifier = str(uuid.UUID(str(identifier)))
    result = _collection().update_one({'_id':identifier,'owner_id':OWNER_ID,'status':'pending'},
        {'$set':{'status':'cancelled','finished_at':datetime.now(timezone.utc)}})
    return result.modified_count == 1


def _next_occurrence(doc):
    """The next instant for a repeating job, plus the anchor to remember.

    Three cases, deliberately kept apart:

    * no repeat — there is no next occurrence;
    * a repeat without a zone — the historical fixed UTC interval;
    * a repeat with a zone — the *intended local wall clock* stays fixed, so
      09:00 remains 09:00 after a DST change. Only an occurrence that falls in
      a spring-forward gap is shifted, and only for that day.
    """
    due = _as_utc(doc.get('due_at'))
    interval = REPEAT_INTERVALS.get(doc.get('repeat'))
    if interval is None:
        return due, None, False
    zone_name = doc.get('timezone')
    if not zone_name:
        return due + interval, None, False
    _, zone = _zone(zone_name)
    try:
        anchor = datetime.fromisoformat(str(doc.get('repeat_anchor'))).replace(tzinfo=None)
    except (TypeError, ValueError):
        # Older rows (or a copy) have no anchor; their current wall clock is it.
        anchor = _wall_of(due, zone)
    anchor = anchor.replace(microsecond=0) + interval
    run_at, adjusted = localize_wall_time(anchor, zone)
    return run_at, anchor, adjusted


def _future_occurrence(doc, now):
    """Walk a series forward until it is strictly in the future.

    Used when resuming a paused series: the owner wants the schedule back, not
    a burst of every copy that was missed while it was paused. The jump is
    computed in one step (daily and weekly intervals are exact multiples of a
    calendar day), so pausing for years cannot exhaust a hop budget.
    """
    probe = dict(doc)
    due = _as_utc(probe.get('due_at'))
    interval = REPEAT_INTERVALS.get(probe.get('repeat'))
    if interval is None or due > now:
        return probe, 0, None, False
    steps = int((now - due) // interval) + 1
    zone_name = probe.get('timezone')
    zone = None
    if zone_name:
        try:
            _, zone = _zone(zone_name)
        except ValueError:
            zone = None
    if zone is not None:
        try:
            anchor = datetime.fromisoformat(str(probe.get('repeat_anchor'))).replace(tzinfo=None)
        except (TypeError, ValueError):
            anchor = _wall_of(due, zone)
        anchor += interval * steps
        run_at, adjusted = localize_wall_time(anchor, zone)
        # A DST shift can make the computed instant a few minutes early; step
        # once more rather than returning a past time.
        while run_at <= now:
            anchor += interval
            run_at, adjusted = localize_wall_time(anchor, zone)
            steps += 1
        probe['due_at'] = run_at
        probe['repeat_anchor'] = anchor.isoformat(timespec='seconds')
        return probe, steps, anchor, adjusted
    probe['due_at'] = due + interval * steps
    return probe, steps, None, False


def set_paused(identifier, paused):
    """Pause or resume a repeating series without losing its identity."""
    identifier = str(uuid.UUID(str(identifier)))
    col = _collection()
    now = datetime.now(timezone.utc)
    doc = col.find_one({'_id': identifier, 'owner_id': OWNER_ID})
    if not doc:
        raise ValueError('This scheduled post no longer exists')
    if doc.get('repeat') not in REPEAT_INTERVALS:
        raise ValueError('Only a repeating post can be paused')
    if doc.get('status') != 'pending':
        raise ValueError('This series is not waiting in the queue; refresh its status')
    changes = {'paused': bool(paused), 'paused_at': now if paused else None, 'note': None}
    if not paused:
        # Never replay the pause as a burst of late copies.
        ahead, hops, anchor, adjusted = _future_occurrence(doc, now)
        changes['due_at'] = _as_utc(ahead['due_at'])
        if hops:
            changes['dst_adjusted'] = bool(adjusted)
        if anchor is not None:
            changes['repeat_anchor'] = anchor.isoformat(timespec='seconds')
        if hops:
            changes['skipped'] = int(doc.get('skipped') or 0) + hops
            changes['note'] = f'{hops} occurrence(s) skipped while paused'
    # The state this decision was based on is part of the write. Two tabs
    # pressing pause and resume at once cannot both win silently.
    guard = {'_id': identifier, 'owner_id': OWNER_ID, 'status': 'pending',
             'paused': {'$ne': True} if paused else True}
    updated = col.update_one(guard, {'$set': changes})
    if not updated.modified_count:
        raise ValueError('This series changed while saving; refresh its status')
    return {'ok': True, 'job_id': identifier, 'paused': bool(paused),
            'scheduled_at': _as_utc(changes.get('due_at', doc['due_at'])).isoformat(),
            'skipped': int(changes.get('skipped', doc.get('skipped') or 0))}


def skip_next(identifier):
    """Move a pending occurrence one step forward without sending it."""
    identifier = str(uuid.UUID(str(identifier)))
    col = _collection()
    doc = col.find_one({'_id': identifier, 'owner_id': OWNER_ID})
    if not doc:
        raise ValueError('This scheduled post no longer exists')
    if doc.get('repeat') not in REPEAT_INTERVALS:
        raise ValueError('Only a repeating post has a next occurrence')
    if doc.get('status') != 'pending':
        raise ValueError('This occurrence is no longer waiting; refresh the queue')
    if doc.get('paused'):
        raise ValueError('Resume the series before skipping an occurrence')
    run_at, anchor, adjusted = _next_occurrence(doc)
    changes = {'due_at': run_at,
               'skipped': int(doc.get('skipped') or 0) + 1,
               'dst_adjusted': bool(adjusted),
               'note': 'Next occurrence skipped by the owner'}
    if anchor is not None:
        changes['repeat_anchor'] = anchor.isoformat(timespec='seconds')
    # The due_at guard makes this a no-op if the dispatcher claimed the job
    # between the read and this write.
    updated = col.update_one({'_id': identifier, 'owner_id': OWNER_ID,
                              'status': 'pending', 'paused': {'$ne': True},
                              'due_at': doc.get('due_at')},
                             {'$set': changes})
    if not updated.modified_count:
        raise ValueError('This occurrence is being sent; refresh the queue')
    return {'ok': True, 'job_id': identifier, 'scheduled_at': run_at.isoformat(),
            'skipped': changes['skipped'], 'dst_adjusted': bool(adjusted)}


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
    a reason to send three copies at once: jump to the next upcoming
    occurrence. A paused series is not late — it is paused — so it is left where
    the owner left it. The jump is computed directly, so a long outage cannot
    exhaust a per-tick budget and leave the series to be declared missed.
    """
    stale = col.find({'owner_id':OWNER_ID, 'status':'pending',
                      'paused':{'$ne':True},
                      'due_at':{'$lt':now-timedelta(days=1)},
                      'repeat':{'$in':list(REPEAT_INTERVALS)}})
    for doc in stale:
        interval = REPEAT_INTERVALS[doc['repeat']]
        due = _as_utc(doc['due_at'])
        steps = max(1, int((now - due) // interval) + 1)
        changes = {}
        zone_name = doc.get('timezone')
        zone = None
        if zone_name:
            try:
                _, zone = _zone(zone_name)
            except ValueError:
                zone = None
        if zone is not None:
            try:
                anchor = datetime.fromisoformat(str(doc.get('repeat_anchor'))).replace(tzinfo=None)
            except (TypeError, ValueError):
                # A row without an anchor still has a wall clock: its due time.
                anchor = _wall_of(due, zone)
            anchor += interval * steps
            due, adjusted = localize_wall_time(anchor, zone)
            while due <= now:
                anchor += interval
                due, adjusted = localize_wall_time(anchor, zone)
                steps += 1
            changes['repeat_anchor'] = anchor.isoformat(timespec='seconds')
            changes['dst_adjusted'] = bool(adjusted)
        else:
            due += interval * steps
            while due <= now:
                due += interval
                steps += 1
        changes.update({'due_at': due,
                        'skipped': int(doc.get('skipped') or 0) + steps,
                        'note': f'{steps} occurrence(s) skipped while the bot was offline'})
        col.update_one({'_id':doc['_id'], 'status':'pending', 'paused':{'$ne':True}},
                       {'$set': changes})

def dispatch_one():
    """At most one send per tick. Catch-up >24h is marked missed, never sent."""
    col, now = _collection(), datetime.now(timezone.utc)
    col.update_many({'owner_id':OWNER_ID,'status':'sending','claimed_at':{'$lt':now-timedelta(minutes=10)}},
                    {'$set':{'status':'unconfirmed','finished_at':now}})
    _skip_missed_series(col, now)
    col.update_many({'owner_id':OWNER_ID,'status':'pending','paused':{'$ne':True},
                     'due_at':{'$lt':now-timedelta(days=1)}},
                    {'$set':{'status':'missed','finished_at':now}})
    doc = col.find_one_and_update({'owner_id':OWNER_ID,'status':'pending',
        'paused':{'$ne':True},'due_at':{'$lte':now}},
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
                # With a timezone this keeps the local wall clock across DST.
                run_at, anchor, adjusted = _next_occurrence(doc)
                update.update({'status':'pending','due_at':run_at,
                               'finished_at':None,'claimed_at':None,'error':None,'note':None,
                               'attempts':0,'sent_count':int(doc.get('sent_count') or 0)+1,
                               'dst_adjusted':bool(adjusted),
                               'last_sent_at':datetime.now(timezone.utc)})
                if anchor is not None:
                    update['repeat_anchor'] = anchor.isoformat(timespec='seconds')
                state = 'pending'
        else:
            # Store why, so the monitor can explain instead of showing a bare state.
            description = str(result.get('description') or '').strip()[:160]
            reason = description or f'Telegram returned HTTP {status or "no response"}'
            if wait is not None:
                reason = f'Rate limit persisted after {attempts} automatic retries: {reason}'[:200]
            update['error'] = reason
            update['note'] = None
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
