# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Vote-to-skip, queue view, skip protection
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import time
from collections import defaultdict

from pyrogram import filters
from pyrogram.types import CallbackQuery, Message

import config
from videl import bot, call_py
from videl.core.queue import get_queue, peek_current, pop_current, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import get_skip_votes_needed, set_skip_votes_needed
from videl.utils.formatters import sc, short
from videl.utils.helpers import delete_file
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
    rich_edit,
)

# chat_id -> set of user_ids who voted to skip current track
_skip_votes: dict[int, set[int]] = defaultdict(set)
# chat_id -> song title fingerprint so votes reset on new song
_vote_track: dict[int, str] = {}


def reset_votes(chat_id: int, track_key: str = "") -> None:
    _skip_votes[chat_id] = set()
    _vote_track[chat_id] = track_key


def _track_key(song: dict | None) -> str:
    if not song:
        return ""
    return str(song.get("video_id") or song.get("url") or song.get("title") or "")


@bot.on_message(
    filters.command(["voteskip", "setvoteskip", "skipvotes"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def set_voteskip_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if len(message.command) < 2 or not message.command[1].isdigit():
        current = get_skip_votes_needed(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("⏭ Vote-skip settings", level=3)
            + rich_kv_table([("Votes needed", str(current))])
            + rich_note(
                "Usage: <code>/voteskip 3</code>\n"
                "Set to <code>0</code> to allow anyone to skip (admins always can)."
            ),
        )
        return

    n = int(message.command[1])
    set_skip_votes_needed(chat_id, n)
    await rich_send(
        bot, chat_id,
        rich_heading("✅ Vote-skip updated", level=3)
        + rich_kv_table([("Votes needed", str(get_skip_votes_needed(chat_id)))]),
    )


@bot.on_message(
    filters.command(["queue", "q"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def queue_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    q = get_queue(chat_id)
    if not q:
        await rich_send(bot, chat_id, rich_heading(f"📋 {sc('queue is empty')}", level=3))
        return

    lines = []
    for i, s in enumerate(q[:15]):
        prefix = "▶️" if i == 0 else f"`{i}.`"
        title = short(s.get("title", "?"), 40)
        req = s.get("requester", "?")
        lines.append(f"{prefix} <b>{rich_esc(title)}</b>\n    ↳ {rich_esc(req)} • {rich_esc(s.get('duration', '?'))}")

    extra = f"\n\n… {sc('and')} {len(q) - 15} {sc('more')}" if len(q) > 15 else ""
    await rich_send(
        bot, chat_id,
        rich_heading(f"📋 {sc('queue')} ({len(q)})", level=3)
        + rich_note("\n".join(lines) + extra),
    )


async def handle_vote_skip(cq: CallbackQuery) -> bool:
    """Called from callbacks. Returns True if handled."""
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    user = cq.from_user
    if not chat_id or not user:
        return True

    needed = get_skip_votes_needed(chat_id)
    # Admins can always force skip via the normal skip button
    if needed <= 0:
        await cq.answer("Vote-skip is disabled. Use ‣‣I or /skip", show_alert=False)
        return True

    current = peek_current(chat_id)
    key = _track_key(current)
    if _vote_track.get(chat_id) != key:
        reset_votes(chat_id, key)

    voters = _skip_votes[chat_id]
    if user.id in voters:
        await cq.answer("You already voted to skip", show_alert=False)
        return True

    voters.add(user.id)
    count = len(voters)

    if count >= needed:
        reset_votes(chat_id, "")
        await cq.answer("Skip threshold reached!", show_alert=False)

        skipped = pop_current(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass

        import asyncio
        await asyncio.sleep(1.5)

        if skipped:
            try:
                delete_file(skipped.get("file_path", ""))
            except Exception:
                pass

        from videl.core.queue import peek_current as peek
        from videl.core.player import play_song

        nxt = peek(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("⏭ Skipped by votes", level=3)
            + rich_kv_table([
                ("Votes", f"{count}/{needed}"),
                ("Song", rich_esc(short((skipped or {}).get("title", "?")))),
            ]),
        )
        if nxt:
            dm = await rich_send(
                bot, chat_id,
                rich_heading("⏭ Next track", level=3)
                + rich_kv_table([("Song", f"<code>{rich_esc(short(nxt.get('title', '?')))}</code>")]),
            )
            try:
                await play_song(chat_id, dm, nxt)
            except Exception:
                pass
        else:
            try:
                await call_py.leave_call(chat_id)
            except Exception:
                pass
    else:
        await cq.answer(f"Skip vote: {count}/{needed}", show_alert=False)
        try:
            await cq.message.reply(
                f"⏭ Skip vote: <b>{count}/{needed}</b> (by {user.mention})",
                quote=False,
            )
        except Exception:
            pass
    return True
