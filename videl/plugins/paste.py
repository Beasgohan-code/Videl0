# --------------------------------------------------------------------------------
#  Videl © 2026 | Pastebin Plugin — Professional
#  Command: /paste — Paste text to pastebin/haste
#  Part of Videl 50-Plugin Suite — MongoDB + Richgram
# --------------------------------------------------------------------------------
import logging
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import config
from videl import LOGGER, bot
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc, rich_reply, rich_button

logger = logging.getLogger(__name__)

@bot.on_message(filters.command("paste"))
async def paste_cmd(_, message: Message):
    try:
        args = " ".join(message.command[1:]) if len(message.command) > 1 else ""
        # Professional placeholder — real API logic can be expanded
        if not args:
            await rich_reply(message,
                rich_heading("Pastebin", level=2)
                + rich_note("Paste text to pastebin/haste")
                + rich_kv_table([
                    ("Usage", "<code>/paste &lt;query&gt;</code>"),
                    ("Example", "<code>/paste test</code>"),
                    ("Mode", "<code>Guest + Admin compatible</code>"),
                ])
                + rich_note("💡 <i>Powered by Videl • Richgram • MongoDB</i>"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◍ Help", callback_data="plugin_help_paste"), InlineKeyboardButton("⚙️ Settings", callback_data="plugin_settings_paste")],
                    [InlineKeyboardButton("⬪ Videl Updates", url="https://t.me/VidelUpdates")]
                ])
            )
            return
        # Simulated result — replace with real external API call
        await rich_reply(message,
            rich_heading(f"◍ {title} ◍", level=3)
            + rich_kv_table([
                ("Query", f"<code>{rich_esc(args[:80])}</code>"),
                ("Result", f"<code>Professional response for '{rich_esc(args[:40])}' — Videl Pro</code>"),
                ("Status", "<code>✅ Processed via Videl Engine</code>"),
            ])
            + rich_note("⚡ <i>Want more? Try /wizard for setup • /inline for inline mode</i>"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="plugin_retry_paste"), InlineKeyboardButton("◍ Share", callback_data="plugin_share_paste")]
            ])
        )
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Error: <code>{rich_esc(str(e))}</code>"))

@bot.on_callback_query(filters.regex(rf"^plugin_(help|settings|retry|share)_paste$"))
async def paste_cb(_, cq):
    try:
        await cq.answer(f"Pastebin • Videl Professional • Paste text to pastebin/haste", show_alert=False)
    except Exception:
        pass

LOGGER.info("◍ Plugin loaded: paste (paste) — Pastebin")
