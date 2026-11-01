"""Scoped music callback dispatcher. Never consume unrelated module callbacks."""
from pyrogram import filters
from pyrogram.types import CallbackQuery
from videl import bot
from videl.utils.db import is_user_blocked_db
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc
from videl.utils.command_ui import rich_send, rich_edit

@bot.on_callback_query(filters.regex(r"^(?:pause|resume|skip|stop|clear|replay|cycle_loop|volume_up|volume_down|noop|show_queue|show_history|save_pl_hint|vote_skip|close_help|show_help|go_back|song_search|warns_view|warns:[0-9]{1,20}|help_[a-z]+)$"))
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


    elif data == "song_search":
        await cbq.answer("Send /song <name> or /vsong <name> in this chat.", show_alert=True)

    elif data == "warns_view" or data.startswith("warns:"):
        from videl.utils.db import get_warn_limit, get_warns
        from videl.plugins.base import is_admin
        if chat_id < 0 and not await is_admin(bot, chat_id, user.id):
            return await cbq.answer("Group admins only.", show_alert=True)
        target = int(data.split(":")[1]) if data.startswith("warns:") else user.id
        info = get_warns(chat_id, target)
        limit = get_warn_limit(chat_id)
        reasons = info.get("reasons") or []
        detail = "\n".join(f"• {rich_esc(str(reason))[:80]}" for reason in reasons[-5:]) or "No reasons stored."
        await cbq.answer()
        await rich_send(
            bot, chat_id,
            rich_heading("Warnings", level=3)
            + rich_note(f"User <code>{target}</code> · <b>{info.get('count', 0)}/{limit}</b> warns")
            + rich_note(detail),
            navigation=False,
        )

    elif data in ("show_help", "go_back") or data.startswith("help_"):
        from videl.plugins.help import render_section
        await cbq.answer()
        section = {"help_play":"music", "help_speed":"music", "help_admin":"manage"}.get(data,"home")
        text, markup = render_section(section, owner=False)
        await rich_edit(cbq.message, text, reply_markup=markup)
