# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import logging
import random

from videl.core.queue import add_to_queue, queue_size
from videl.utils.youtube import search_yt
from videl.utils.formatters import iso_to_human, iso_to_sec

logger = logging.getLogger(__name__)

# ── Per-chat state ────────────────────────────────────────────────────────────
_autoplay_active:   dict[int, bool] = {}
_autoplay_query:    dict[int, str]  = {}
_autoplay_fetched:  dict[int, set]  = {}
_autoplay_fetching: dict[int, bool] = {}

BATCH_SIZE       = 10  
REFETCH_THRESHOLD = 2  


def is_autoplay(chat_id: int) -> bool:
    return _autoplay_active.get(chat_id, False)


def get_autoplay_query(chat_id: int) -> str:
    return _autoplay_query.get(chat_id, "")


def stop_autoplay(chat_id: int) -> None:
    _autoplay_active.pop(chat_id, None)
    _autoplay_query.pop(chat_id, None)
    _autoplay_fetched.pop(chat_id, None)
    _autoplay_fetching.pop(chat_id, None)


async def _fetch_more(chat_id: int, requester: str, requester_id: int) -> int:
    if _autoplay_fetching.get(chat_id):
        return 0
    _autoplay_fetching[chat_id] = True

    query   = _autoplay_query.get(chat_id, "")
    fetched = _autoplay_fetched.setdefault(chat_id, set())
    added   = 0
    variations = [
        query,
        f"{query} new songs",
        f"{query} best songs",
        f"{query} hits",
        f"{query} latest",
    ]

    try:
        for variation in variations:
            if not is_autoplay(chat_id):
                break
            if added >= BATCH_SIZE:
                break

            try:
                result = await search_yt(variation)

                if isinstance(result, dict) and "playlist" in result:
                    items = result["playlist"]
                    random.shuffle(items)
                    for item in items:
                        if not is_autoplay(chat_id):
                            break
                        vid_url = item.get("link", "")
                        vid_id  = vid_url.split("v=")[-1].split("&")[0] if "v=" in vid_url else vid_url
                        if vid_id in fetched:
                            continue
                        fetched.add(vid_id)
                        add_to_queue(chat_id, {
                            "url":              vid_url,
                            "title":            item.get("title", "Unknown"),
                            "duration":         iso_to_human(item.get("duration", "PT0S")),
                            "duration_seconds": iso_to_sec(item.get("duration", "PT0S")),
                            "requester":        f"🔁 AutoPlay",
                            "requester_id":     requester_id,
                            "thumbnail":        item.get("thumbnail", ""),
                        })
                        added += 1
                        if added >= BATCH_SIZE:
                            break

                else:
                    # Single track
                    url, title, dur_iso, thumb = result
                    vid_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url
                    if vid_id not in fetched:
                        fetched.add(vid_id)
                        add_to_queue(chat_id, {
                            "url":              url,
                            "title":            title,
                            "duration":         iso_to_human(dur_iso),
                            "duration_seconds": iso_to_sec(dur_iso),
                            "requester":        f"🔁 AutoPlay",
                            "requester_id":     requester_id,
                            "thumbnail":        thumb,
                        })
                        added += 1

            except Exception as e:
                logger.warning(f"[AutoPlay] fetch variation '{variation}': {e}")
                continue

    finally:
        _autoplay_fetching[chat_id] = False

    logger.info(f"[AutoPlay] {chat_id}: +{added} songs added")
    return added


async def start_autoplay(
    chat_id:      int,
    query:        str,
    requester:    str,
    requester_id: int,
) -> int:
    stop_autoplay(chat_id)

    _autoplay_active[chat_id]  = True
    _autoplay_query[chat_id]   = query
    _autoplay_fetched[chat_id] = set()

    count = await _fetch_more(chat_id, requester, requester_id)
    return count


async def maybe_refetch(
    chat_id:      int,
    requester:    str,
    requester_id: int,
) -> None:
    if not is_autoplay(chat_id):
        return
    if _autoplay_fetching.get(chat_id):
        return
    if queue_size(chat_id) <= REFETCH_THRESHOLD:
        asyncio.create_task(
            _fetch_more(chat_id, requester, requester_id)
        )
