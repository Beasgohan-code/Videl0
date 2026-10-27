# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

chat_queues: dict[int, list] = {}


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
