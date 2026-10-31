# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

chat_queues: dict[int, list] = {}

# A requester may keep at most this many tracks in the upcoming queue at once.
# The currently playing head is not counted, so a person can always start a
# track in an idle chat and still add a small playlist behind it.
MAX_UPCOMING_PER_REQUESTER = 3


def get_queue(chat_id: int) -> list:
    return chat_queues.get(chat_id, [])


def add_to_queue(chat_id: int, song: dict) -> int:
    queue = chat_queues.setdefault(chat_id, [])
    queue.append(song)
    return len(queue)


def insert_next(chat_id: int, song: dict, *, offset: int = 0) -> int:
    """Insert after the current item, preserving order for a batch of tracks.

    Returns the one-based queue position (current item is position one).
    When the queue is empty, the track becomes the current item.
    """
    queue = chat_queues.setdefault(chat_id, [])
    index = min(1 + max(0, int(offset)), len(queue)) if queue else 0
    queue.insert(index, song)
    return index + 1


def requester_pending(chat_id: int, requester_id: int) -> int:
    """Count a person's tracks after the current item."""
    if not requester_id:
        return 0
    count = 0
    for song in get_queue(chat_id)[1:]:
        try:
            same_requester = int(song.get("requester_id") or 0) == int(requester_id)
        except (TypeError, ValueError):
            same_requester = False
        count += int(same_requester)
    return count


def requester_capacity(chat_id: int, requester_id: int) -> int:
    """How many more upcoming tracks this requester may add right now."""
    if not requester_id:
        return MAX_UPCOMING_PER_REQUESTER
    return max(0, MAX_UPCOMING_PER_REQUESTER - requester_pending(chat_id, requester_id))


def add_request(chat_id: int, song: dict, *, play_next: bool = False, offset: int = 0) -> int | None:
    """Queue a user request subject to the per-requester fair-share limit.

    Returns its one-based position, or ``None`` without changing the queue if
    the requester already has their full share of upcoming tracks.
    """
    requester_id = int(song.get("requester_id") or 0)
    if requester_id and requester_capacity(chat_id, requester_id) <= 0:
        return None
    try:
        from videl.plugins import base
        settings_chat_id = int(song.get("settings_chat_id", chat_id))
        blocked_items = base.get_setting(settings_chat_id, "music_track_blocklist", [])
        from videl.utils.track_blocklist import matches
        if matches(blocked_items, song):
            return -3
        if not bool(base.get_setting(settings_chat_id, "music_requests_enabled", True)):
            return -2
        approval_enabled = bool(base.get_setting(settings_chat_id, "music_approval_required", False))
    except Exception:
        approval_enabled = False
    if approval_enabled:
        from videl.core.request_approval import submit
        pending_song = dict(song)
        pending_song["_queue_chat_id"] = int(chat_id)
        return -1 if submit(settings_chat_id, pending_song) is not None else None
    if play_next:
        return insert_next(chat_id, song, offset=offset)
    try:
        from videl.plugins import base
        shuffle_enabled = bool(base.get_setting(int(song.get("settings_chat_id", chat_id)), "music_shuffle_enabled", False))
    except Exception:
        shuffle_enabled = False
    if shuffle_enabled:
        import random
        items = chat_queues.setdefault(chat_id, [])
        index = random.randint(1, len(items)) if len(items) > 1 else len(items)
        items.insert(index, song)
        return index + 1
    return add_to_queue(chat_id, song)


def pop_current(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)

    if not queue:
        return None

    return queue.pop(0)


def remove_from_queue(chat_id: int, index: int) -> dict | None:
    queue = chat_queues.get(chat_id)

    if not queue:
        return None

    if index < 0 or index >= len(queue):
        return None

    return queue.pop(index)


def peek_current(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)

    if not queue:
        return None

    return queue[0]


def peek_next(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)

    if not queue or len(queue) < 2:
        return None

    return queue[1]


def clear_queue(chat_id: int) -> list:
    return chat_queues.pop(chat_id, [])


def queue_size(chat_id: int) -> int:
    return len(chat_queues.get(chat_id, []))


def is_empty(chat_id: int) -> bool:
    return queue_size(chat_id) == 0


def clear_pending(chat_id: int) -> list:
    """Remove upcoming tracks without losing the currently playing queue head."""
    queue = chat_queues.get(chat_id)
    if not queue:
        return []
    removed = queue[1:]
    del queue[1:]
    return removed
