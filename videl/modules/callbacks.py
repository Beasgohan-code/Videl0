"""Scoped music callback dispatcher. Never consume unrelated module callbacks."""
from pyrogram import filters
from pyrogram.types import CallbackQuery
from videl import bot
from videl.utils.db import is_user_blocked_db
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc
from videl.utils.command_ui import rich_send, rich_edit

@bot.on_callback_query(filters.regex(r"^(?:pause|resume|skip|stop|clear|replay|cycle_loop|noop|show_queue|save_pl_hint|vote_skip|close_help|show_help|go_back|help_[a-z]+)$"))
async def on_callback(client, cbq: CallbackQuery) -> None:

    if not cbq.message or not cbq.from_user:
        return await cbq.answer("Open the controls in a chat.")
    chat_id = cbq.message.chat.id
    user    = cbq.from_user
    data    = cbq.data

    # Migrated buttons use exactly the same policies/actions as slash commands.
    from videl.app.music_callbacks import handle
    if await handle(client,cbq):
        return

    # ── Block check ──────────────────────────────────────────────────────────[...]
    if user and is_user_blocked_db(user.id):
        await cbq.answer()
        return

    # ── NOOP ────────────────────────────────────────────────────────────[...]
    if data == "noop":
        await cbq.answer()

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


    elif data in ("show_help", "go_back") or data.startswith("help_"):
        from videl.utils.help_catalog import guide
        await cbq.answer()
        section = {"help_play":"music", "help_speed":"music", "help_admin":"manage"}.get(data,"home")
        text, markup = guide(section)
        await rich_edit(cbq.message, text, reply_markup=markup)
