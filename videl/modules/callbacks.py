# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import random

from pyrogram import enums
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import config
from videl import bot, call_py
from videl.core.call import leave_vc
from videl.core.player import play_song
from videl.core.queue import clear_queue, get_queue, peek_current, pop_current, queue_size
from videl.utils.db import is_user_blocked_db
from videl.utils.formatters import short
from videl.utils.helpers import delete_file
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_details,
    rich_esc,
    rich_heading,
    rich_img,
    rich_kv_table,
    rich_note,
    rich_send,
    rich_table,
    rich_edit,
    sanitize_display_name,
)

def _support_updates_pills() -> str:
    return (
        "<p>"
        f'<tg-button type="url" style="primary" url="{config.SUPPORT_GROUP}">'
        " support</tg-button> "
        f'<tg-button type="url" style="success" url="{config.UPDATES_CHANNEL}">'
        " updates</tg-button>"
        "</p>"
    )


def _category_html(title: str, desc: str, rows, photo: str = None) -> str:
    """title/desc/rows + photo -> photo + heading + description + Command/Description table + pills."""
    html = ""
    if photo:
        html += rich_img(photo)
    return (
        html
        + rich_heading(title, level=3)
        + f"<p>{desc}</p>"
        + rich_table(["command", "description"], rows)
        + _support_updates_pills()
    )


# ── Help menu layout ──────────────────────────────────────────────────────────[...]
#
#   Row 1 : [ᴧᴅᴍɪɴ]  [ᴧ-ᴘʟᴀʏ]  [ɢ-ᴄᴧsᴛ]
#   Row 2 : [ʙʟ-ᴄʜᴧᴛ] [ʙʟ-ᴜsᴇʀs] [ᴘɪɴɢ]
#   Row 3 : [ᴘʟᴀʏ]   [sᴘᴇᴇᴅ]   [ɪɴғᴏ]
#   Row 4 :          [⌯ ʜᴏᴍᴇ ⌯]
#
# ──────────────────────────────────────────────────────────────────[...]

def _webapp_root() -> str:
    return (getattr(config, "WEBAPP_URL", "https://videl0-control-panel.vercel.app") or "https://videl0-control-panel.vercel.app").rstrip("/")


_HELP_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🛡️ Group & Admin", callback_data="help_admin"),
        InlineKeyboardButton("🎵 Music Play", callback_data="help_play"),
        InlineKeyboardButton("🎚️ Audio Effects", callback_data="help_speed"),
    ],
    [
        InlineKeyboardButton("🔁 Autoplay", callback_data="help_autoplay"),
        InlineKeyboardButton("📢 Broadcast", callback_data="help_gcast"),
        InlineKeyboardButton("🏓 Ping & Stats", callback_data="help_ping"),
    ],
    [
        InlineKeyboardButton("🚫 Chat Block", callback_data="help_blchat"),
        InlineKeyboardButton("🚷 User Block", callback_data="help_blusers"),
        InlineKeyboardButton("ℹ️ Bot Info", callback_data="help_info"),
    ],
    [
        InlineKeyboardButton("👑 Videl Web App", url=_webapp_root()),
        InlineKeyboardButton("🏠 Home", callback_data="go_back"),
    ],
])

_BACK_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⬅️ Back to Modules", callback_data="show_help"),
        InlineKeyboardButton("👑 Web App", url=_webapp_root()),
    ],
    [InlineKeyboardButton("✖ Close", callback_data="close_help")],
])

# ── Help texts ────────────────────────────────────────────────────────────[...]
# Same commands/wording as the old ASCII-box version, restructured into a real
# heading + description + Command/Description table.
# Note: photo parameter will be passed at render time from callback handler

_HELP_TEXTS = {

    "help_admin": {
        "title": "⚙️ admin &amp; moderation",
        "desc": "playback controls + group management (requires bot admin rights).",
        "rows": [
            ("/pause /resume /skip /stop", "playback controls"),
            ("/seek &lt;sec&gt; /seekback", "seek forward / back"),
            ("/ban /unban /kick", "ban, unban or kick a user"),
            ("/mute [1h] /unmute", "mute (optional duration) / unmute"),
            ("/warn /warns /resetwarns", "warn system (auto-ban at limit)"),
            ("/setwarnlimit &lt;n&gt;", "set warn limit (default 3)"),
            ("/promote /demote", "promote or demote admin"),
            ("/purge", "delete messages from reply to here"),
            ("/pin /unpin", "pin or unpin a message"),
            ("/setwelcome /welcome on|off", "welcome message"),
            ("/setgoodbye", "goodbye message"),
            ("/admins", "list group admins"),
            ("/locks", "content locks panel"),
            ("/antiflood", "anti-flood settings"),
            ("/voteskip &lt;n&gt;", "votes needed to skip"),
            ("/queue", "show current queue"),
            ("/saveplaylist /playlist", "save / load playlists"),
        ],
    },

    "help_autoplay": {
        "title": " autoplay commands",
        "desc": "keep the queue going automatically based on a query.",
        "rows": [
            ("/autoplay &lt;query&gt;", "continuously play songs based on your query"),
            ("/end, /stop", "stop autoplay &amp; clear queue"),
            ("<code>/autoplay sidhu moose wala</code>", "example"),
            ("<code>/autoplay arijit singh</code>", "example"),
        ],
    },

    "help_gcast": {
        "title": " g-cast commands",
        "desc": "broadcast to every served chat (owner only).",
        "rows": [
            ("/broadcast, /gcast", "reply to a msg or type text"),
            ("-pin", "pin silently in groups"),
            ("-pinloud", "pin with notification"),
            ("-nogroup", "skip groups"),
            ("-user", "also send to users"),
        ],
    },

    "help_blchat": {
        "title": " bl-chat commands",
        "desc": "block or unblock whole groups (owner only).",
        "rows": [
            ("/gblock", "block current group — no commands will work"),
            ("/gblock &lt;-100xxxxxxx&gt;", "block by chat id"),
            ("/gunblock", "unblock group"),
            ("/gunblock &lt;-100xxxxxxx&gt;", "unblock by chat id"),
            ("/blocklist", "show all blocked groups &amp; users"),
        ],
    },

    "help_blusers": {
        "title": " bl-users commands",
        "desc": "block or unblock individual users (owner only).",
        "rows": [
            ("/ublock", "reply to a user's msg to block — they can't use any command"),
            ("/ublock &lt;user id&gt;", "block by user id"),
            ("/uunblock", "reply to a user's msg to unblock"),
            ("/uunblock &lt;user id&gt;", "unblock by user id"),
            ("/blocklist", "show all blocked users &amp; chats"),
        ],
    },

    "help_ping": {
        "title": "🏓 ping commands",
        "desc": "latency and system diagnostics.",
        "rows": [
            ("/ping", "bot latency, ram, cpu, disk &amp; uptime stats"),
            ("/speedtest, /spt", "network speed test (owner only)"),
            ("/stats", "full system + mongodb stats (owner only)"),
        ],
    },

    "help_play": {
        "title": " play commands",
        "desc": "audio, video, files &amp; channel play.",
        "rows": [
            ("/play &lt;name or URL&gt;", "play audio in group vc"),
            ("/vplay &lt;name or URL&gt;", "play video in group vc"),
            ("/cplay &lt;name or URL&gt;", "play audio in linked channel"),
            ("/cvplay &lt;name or URL&gt;", "play video in linked channel"),
            ("/channelplay @ch", "link a channel for /cplay"),
            ("reply + /play or /vplay", "audio, video, mkv, mp4, webm…"),
            ("search picker", "choose from top 5 yt results"),
            ("/lyrics", "lyrics for current or search"),
            ("now playing btn", "queue · lyrics · save pl"),
            ("max duration", f"{config.MAX_DURATION_SECONDS // 60} minutes"),
            ("queue limit", f"{config.QUEUE_LIMIT} songs"),
        ],
    },

    "help_speed": {
        "title": "🎚️ speed &amp; effects",
        "desc": "adjust playback speed and audio effects.",
        "rows": [
            ("/speed &lt;0.25–4.0&gt;", "change playback speed — e.g. /speed 1.5"),
            ("/speedreset", "reset speed to normal (1.0x)"),
            ("/bass &lt;1–20&gt;", "boost bass by n db — e.g. /bass 10"),
            ("/bassoff", "turn off bass boost"),
            ("/effecton", "apply effects to all songs"),
            ("/effectoff", "disable auto effects"),
            ("/effects", "show current effect status"),
        ],
    },

    "help_info": {
        "title": "ℹ️ info commands",
        "desc": "bot, chat, and user information.",
        "rows": [
            ("/id", "get ids of user / chat / msg — also works with reply"),
            ("/id @username", "get any user's id"),
            ("/repo", "source code link"),
            ("/stats", "full stats — system + mongodb info (owner only)"),
        ],
    },
}


# ══════════════════════════════════════════════════════════════════[...]
#  MAIN CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════[...]

@bot.on_callback_query()
async def on_callback(client, cbq: CallbackQuery) -> None:

    chat_id = cbq.message.chat.id
    user    = cbq.from_user
    data    = cbq.data

    # ── Block check ──────────────────────────────────────────────────────────[...]
    if user and is_user_blocked_db(user.id):
        await cbq.answer()
        return

    # ── Admin check for playback controls ─────────────────────────────────────
    if data in ("pause", "resume", "skip", "stop", "clear", "replay", "cycle_loop"):
        if not await is_user_authorized(cbq):
            await cbq.answer("❍ admins only", show_alert=True)
            return

    # ── REPLAY ────────────────────────────────────────────────────────────
    if data == "replay":
        cur = peek_current(chat_id)
        if not cur:
            await cbq.answer("queue empty", show_alert=True)
            return
        await cbq.answer("replaying…")
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass
        await asyncio.sleep(1)
        try:
            await play_song(chat_id, cbq.message, cur)
        except Exception:
            await cbq.answer("replay failed", show_alert=True)
        return

    # ── PAUSE ────────────────────────────────────────────────────────────
    if data == "pause":
        try:
            await call_py.pause(chat_id)
            from videl.core.player import set_paused, refresh_np_ui
            set_paused(chat_id, True)
            await cbq.answer("paused")
            await refresh_np_ui(chat_id)
        except Exception:
            await cbq.answer("failed to pause", show_alert=True)

    # ── RESUME ────────────────────────────────────────────────────────────
    elif data == "resume":
        try:
            await call_py.resume(chat_id)
            from videl.core.player import set_paused, refresh_np_ui
            set_paused(chat_id, False)
            await cbq.answer("resumed")
            await refresh_np_ui(chat_id)
        except Exception:
            await cbq.answer("failed to resume", show_alert=True)

    # ── LOOP CYCLE ────────────────────────────────────────────────────────
    elif data == "cycle_loop":
        try:
            from videl.core.player import cycle_loop, refresh_np_ui
            mode = cycle_loop(chat_id)
            labels = {"off": "loop off", "one": "loop one", "all": "loop queue"}
            await cbq.answer(labels.get(mode, mode))
            await refresh_np_ui(chat_id)
        except Exception:
            await cbq.answer("failed", show_alert=True)

    # ── SKIP ────────────────────────────────────────────────────────────[...]
    elif data == "skip":
        if not queue_size(chat_id):
            await cbq.answer("queue is empty", show_alert=True)
            return

        skipped = pop_current(chat_id)

        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass

        await asyncio.sleep(2)

        try:
            delete_file(skipped.get("file_path", ""))
        except Exception:
            pass

        await rich_send(
            bot, chat_id,
            rich_heading("⏭ track skipped", level=3)
            + rich_kv_table([
                ("by", user.mention),
                ("song", f"<code>{rich_esc(short(skipped['title']))}</code>"),
            ]),
        )

        nxt = peek_current(chat_id)
        if nxt:
            await cbq.answer("playing next")
            dm = await rich_send(
                bot, chat_id,
                rich_heading("⏭ next track", level=3)
                + rich_kv_table([
                    ("song", f"<code>{rich_esc(short(nxt['title']))}</code>"),
                ]),
            )
            await play_song(chat_id, dm, nxt)
        else:
            await cbq.answer("queue empty", show_alert=True)

    # ── STOP ────────────────────────────────────────────────────────────[...]
    elif data == "stop":
        await leave_vc(chat_id)
        await cbq.answer("stopped")
        await rich_send(
            bot, chat_id,
            rich_heading(" playback stopped", level=3)
            + rich_note(f"❍ by » {user.mention}"),
        )

    # ── CLEAR ────────────────────────────────────────────────────────────[...]
    elif data == "clear":
        clear_queue(chat_id)
        await cbq.answer("queue cleared")
        await rich_edit(
            cbq.message,
            rich_heading("🧹 queue cleared", level=3)
            + rich_note(f"❍ by » {user.mention}"),
        )

    # ── NOOP ────────────────────────────────────────────────────────────[...]
    elif data == "noop":
        await cbq.answer()

    # ── SHOW QUEUE (from Now Playing) ─────────────────────────────────────
    elif data == "show_queue":
        q = get_queue(chat_id)
        if not q:
            await cbq.answer("Queue empty", show_alert=True)
        else:
            lines = []
            for i, s in enumerate(q[:10]):
                lines.append(f"{i}. {short(s.get('title', '?'))}")
            await cbq.answer()
            await rich_send(
                bot, chat_id,
                rich_heading(f"📋 Queue ({len(q)})", level=3)
                + rich_note("\n".join(lines)),
            )

    # ── SAVE PLAYLIST HINT ────────────────────────────────────────────────
    elif data == "save_pl_hint":
        await cbq.answer()
        await rich_send(
            bot, chat_id,
            rich_heading("⭐ Save playlist", level=3)
            + rich_note(
                "Save current queue:\n"
                "<code>/saveplaylist MyHits</code>\n"
                "Group playlist: <code>/saveplaylist g:Party</code>\n"
                "Load later with <code>/playlist Name</code>"
            ),
        )

    # ── VOTE SKIP ─────────────────────────────────────────────────────────
    elif data == "vote_skip":
        try:
            from videl.modules.smartqueue import handle_vote_skip
            await handle_vote_skip(cbq)
        except Exception as e:
            await cbq.answer("Vote failed", show_alert=False)

    # ── CLOSE HELP ──────────────────────────────────────────────────────────[...]
    elif data == "close_help":
        await cbq.answer()
        try:
            await cbq.message.delete()
        except Exception:
            pass

    # ── HELP ────────────────────────────────────────────────────────────[...]
    elif data == "show_help":
        await cbq.answer()
        uid  = cbq.from_user.id
        name = sanitize_display_name(cbq.from_user.first_name)
        photo = random.choice(config.START_PHOTOS)
        content = (
            rich_heading("👑 Videl Studio · Command Modules", level=2)
            + rich_img(photo)
            + rich_note(
                f"<p>👋 Welcome <a href=\"tg://user?id={uid}\">{rich_esc(name)}</a>! "
                "Select a module below or open the single-URL Videl Web App Studio.</p>"
            )
            + rich_details(
                "⚡ Quick Reference",
                rich_table(
                    ["Module", "Primary Commands"],
                    [
                        ("🎵 Voice Music", "/play · /vplay · /queue · /skip · /lyrics"),
                        ("🛡️ Group Manager", "/setup · /locks · /ban · /mute · /warn"),
                        ("👑 Web App Studio", _webapp_root()),
                    ],
                ),
                open=True,
            )
            + _support_updates_pills()
        )
        if getattr(cbq.message, "photo", None):
            try:
                await cbq.message.delete()
            except Exception:
                pass
            await rich_send(bot, chat_id, content, reply_markup=_HELP_KB)
        else:
            await rich_edit(cbq.message, content, reply_markup=_HELP_KB)

    elif data == "go_back":
        await _go_back(cbq)

    elif data.startswith("help_"):
        await cbq.answer()
        photo = random.choice(config.START_PHOTOS)
        help_data = _HELP_TEXTS.get(data)
        if help_data:
            text = _category_html(help_data["title"], help_data["desc"], help_data["rows"], photo)
            await rich_edit(cbq.message, text, reply_markup=_BACK_KB)


# ── Go back to start message ───────────────────────────────────────────────────

async def _go_back(cbq: CallbackQuery) -> None:
    await cbq.answer()
    uid  = cbq.from_user.id
    name = sanitize_display_name(cbq.from_user.first_name)
    from videl.modules.start import _studio_private_caption, _start_kb
    is_priv = cbq.message.chat.type == enums.ChatType.PRIVATE
    text = _studio_private_caption(uid, name)
    kb = _start_kb(is_private=is_priv, use_webapp_btn=False)
    chat_id = cbq.message.chat.id
    try:
        await cbq.message.delete()
    except Exception:
        pass
    await rich_send(bot, chat_id, text, reply_markup=kb)
