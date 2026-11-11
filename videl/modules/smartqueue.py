# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Vote-to-skip, queue view, skip protection
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import threading
from collections import defaultdict

from pyrogram import filters
from pyrogram.types import CallbackQuery, Message

import config
from videl import bot
from videl.core.queue import peek_current
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import get_skip_votes_needed, set_skip_votes_needed
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note
from videl.utils.command_ui import rich_send

# Per-process vote state; transitions remain authoritative for queue/voice mutation.
_skip_votes: dict[int, set[int]] = defaultdict(set)
_vote_track: dict[int, str] = {}
_skip_in_progress: set[int] = set()
_vote_state_lock = threading.RLock()


def reset_votes(chat_id: int, track_key: str = "") -> None:
    with _vote_state_lock:
        _skip_votes[chat_id] = set()
        _vote_track[chat_id] = track_key


def _track_key(song: dict | None) -> str:
    if not song:
        return ""
    return str(song.get("video_id") or song.get("url") or song.get("title") or "")


def vote_status(chat_id: int) -> tuple[int, int]:
    """Return current-track vote count and configured threshold for the player card."""
    needed = max(0, min(20, get_skip_votes_needed(chat_id)))
    key = _track_key(peek_current(chat_id))
    with _vote_state_lock:
        if _vote_track.get(chat_id) != key:
            _skip_votes[chat_id] = set()
            _vote_track[chat_id] = key
        return len(_skip_votes.get(chat_id, set())), needed


@bot.on_message(
    filters.command('voteskip', prefixes=config.COMMAND_PREFIX_LIST)
    & filters.group
    & group_allowed
    & user_allowed
)
async def set_voteskip_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if len(message.command) < 2 or not message.command[1].isdecimal():
        current = get_skip_votes_needed(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("⏭ Vote-skip settings", level=3)
            + rich_kv_table([("Votes needed", str(current))])
            + rich_note(
                "Usage: <code>/voteskip 3</code>\n"
                "Set to <code>0</code> to disable voting (admins can still use /skip)."
            ),
        )
        return

    # Bound parsing before converting untrusted command text to an integer.
    raw = message.command[1].lstrip("0") or "0"
    n = 20 if len(raw) > 2 else min(int(raw), 20)
    set_skip_votes_needed(chat_id, n)
    # Votes were cast under the old rule; restart the round after any threshold update.
    with _vote_state_lock:
        _skip_votes[chat_id] = set()
        _vote_track[chat_id] = _vote_track.get(chat_id, "")
    await rich_send(
        bot, chat_id,
        rich_heading("⏭ Vote-skip updated", level=3)
        + rich_kv_table([("Votes needed", str(get_skip_votes_needed(chat_id)))]),
    )


async def handle_vote_skip(cq: CallbackQuery) -> bool:
    """Collect one actor-bound vote and skip only through acknowledged transitions."""
    message = cq.message
    user = cq.from_user
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", 0) if chat else 0
    if not chat_id or chat_id >= 0 or not user:
        await cq.answer("Vote-skip is available from a group player card.", show_alert=False)
        return True

    # Do not allow copied/forwarded/stale buttons to cast votes for another room.
    try:
        from videl.core import player
        current_card = player._np_msg.get(chat_id)
        current_song = player._np_song.get(chat_id)
        if (
            current_card is None
            or getattr(current_card, "id", None) != getattr(message, "id", None)
            or not current_song
        ):
            await cq.answer("This player card is no longer active.", show_alert=False)
            return True
    except Exception:
        await cq.answer("Player controls are unavailable.", show_alert=False)
        return True

    needed = max(0, min(20, get_skip_votes_needed(chat_id)))
    if needed <= 0:
        await cq.answer("Vote-skip is disabled. Use the regular /skip control.", show_alert=False)
        return True

    current = peek_current(chat_id)
    key = _track_key(current)
    if not key or key != _track_key(current_song):
        await cq.answer("The current track changed; refresh the player card.", show_alert=False)
        return True

    reject = None
    with _vote_state_lock:
        if chat_id in _skip_in_progress:
            reject = "The skip transition is already being checked."
        else:
            if _vote_track.get(chat_id) != key:
                _skip_votes[chat_id] = set()
                _vote_track[chat_id] = key
            voters = _skip_votes[chat_id]
            if user.id in voters:
                reject = "You already voted to skip this track."
            else:
                voters.add(user.id)
                count = len(voters)
                threshold_reached = count >= needed
                if threshold_reached:
                    _skip_in_progress.add(chat_id)

    if reject:
        await cq.answer(reject, show_alert=False)
        return True

    if not threshold_reached:
        await cq.answer(f"Skip vote: {count}/{needed}", show_alert=False)
        try:
            await message.reply(
                f"⏭ Skip vote: <b>{count}/{needed}</b> (by {user.mention})",
                quote=False,
            )
        except Exception:
            pass
        return True

    await cq.answer("Vote threshold reached; checking the voice transition.", show_alert=False)
    try:
        from videl.core.transitions import transition
        outcome = await transition(chat_id, "skip", message=message, expected=current)
    except Exception as error:
        outcome = type("FailedOutcome", (), {
            "title": "Skip not confirmed",
            "body": f"Queue preserved; check the voice chat before retrying ({type(error).__name__}).",
            "confirmed": False,
        })()
    finally:
        # The outcome may be uncertain; clear this round so the group can retry
        # with fresh votes, but never mutate the queue from this callback.
        with _vote_state_lock:
            _skip_in_progress.discard(chat_id)
            _skip_votes[chat_id] = set()
            _vote_track[chat_id] = _track_key(peek_current(chat_id))

    await rich_send(
        bot,
        chat_id,
        rich_heading(str(outcome.title)[:100], level=3)
        + rich_note(rich_esc(str(outcome.body)[:500])),
    )
    return True
