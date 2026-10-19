# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Lyrics — /lyrics + Now Playing button (LRCLIB)
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import re
from urllib.parse import quote

import aiohttp
from pyrogram import filters
from pyrogram.types import CallbackQuery, Message

from videl import bot, LOGGER
from videl.core.queue import peek_current
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import sc, short
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
    rich_edit,
)

LRCLIB_API = "https://lrclib.net/api/search"


def _clean_title(title: str) -> str:
    """Strip common noise for better lyric search."""
    t = title or ""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"(?i)\b(official|video|audio|lyrics|hd|hq|4k|mv|visualiser|visualizer)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—|")
    return t


async def fetch_lyrics(query: str) -> dict | None:
    """
    Search LRCLIB. Returns {title, artist, plainLyrics, synced} or None.
    """
    q = _clean_title(query)
    if not q:
        return None
    url = f"{LRCLIB_API}?q={quote(q)}"
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"User-Agent": "VidelMusicBot/1.0"}) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as e:
        LOGGER.warning(f"[lyrics] fetch failed: {e}")
        return None

    if not data or not isinstance(data, list):
        return None

    for item in data:
        plain = (item.get("plainLyrics") or "").strip()
        if plain and len(plain) > 20:
            return {
                "title": item.get("trackName") or query,
                "artist": item.get("artistName") or "?",
                "lyrics": plain,
                "synced": bool(item.get("syncedLyrics")),
            }
    return None


def _format_lyrics(data: dict, max_chars: int = 3500) -> str:
    body = data["lyrics"]
    if len(body) > max_chars:
        body = body[: max_chars - 20] + "\n\n… " + sc("(truncated)")
    return (
        rich_heading(f"📝 {sc('lyrics')}", level=3)
        + rich_kv_table([
            (sc("title"), rich_esc(short(data["title"], 40))),
            (sc("artist"), rich_esc(short(data["artist"], 30))),
        ])
        + rich_note(f"<pre>{rich_esc(body)}</pre>")
    )


@bot.on_message(
    filters.command(["lyrics", "lyric", "ly"])
    & group_allowed
    & user_allowed
)
async def lyrics_cmd(_, message: Message) -> None:
    chat_id = message.chat.id if message.chat else 0
    query = ""

    if message.command and len(message.command) > 1:
        query = " ".join(message.command[1:]).strip()
    elif message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    else:
        current = peek_current(chat_id)
        if current:
            query = current.get("title", "")

    if not query:
        await rich_send(
            bot, chat_id,
            rich_heading(f"ℹ️ {sc('usage')}", level=3)
            + rich_kv_table([
                (sc("now"), f"<code>/{sc('lyrics')}</code> — {sc('current song')}"),
                (sc("search"), f"<code>/{sc('lyrics')} song name</code>"),
            ]),
        )
        return

    status = await rich_send(
        bot, chat_id,
        rich_heading(f"⏳ {sc('searching lyrics')}…", level=3)
        + rich_note(rich_esc(short(query, 50))),
    )

    data = await fetch_lyrics(query)
    if not data:
        await rich_edit(
            status,
            rich_heading(f"❌ {sc('no lyrics found')}", level=3)
            + rich_note(rich_esc(short(query, 50))),
        )
        return

    await rich_edit(status, _format_lyrics(data))


@bot.on_callback_query(filters.regex(r"^lyrics_now$"))
async def lyrics_callback(_, cq: CallbackQuery) -> None:
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    current = peek_current(chat_id)
    if not current:
        await cq.answer(sc("nothing playing"), show_alert=True)
        return

    await cq.answer(sc("fetching lyrics") + "…")
    data = await fetch_lyrics(current.get("title", ""))
    if not data:
        await rich_send(
            bot, chat_id,
            rich_heading(f"❌ {sc('no lyrics found')}", level=3)
            + rich_note(rich_esc(short(current.get("title", "?"), 50))),
        )
        return

    await rich_send(bot, chat_id, _format_lyrics(data))
