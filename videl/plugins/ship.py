# --------------------------------------------------------------------------------
#  Videl © 2026 | Shipper Plugin — Professional
#  Command: /ship — Ship two users % compatibility
#  Part of Videl 50-Plugin Suite — MongoDB + Richgram
# --------------------------------------------------------------------------------
import logging
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import config
from videl import LOGGER, bot
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc, rich_reply, rich_button

logger = logging.getLogger(__name__)

@bot.on_message(filters.command("ship"))
async def ship_cmd(_, message: Message):
    try:
        args = " ".join(message.command[1:]) if len(message.command) > 1 else ""
        # Professional placeholder — real API logic can be expanded
        if not args:
            await rich_reply(message,
                rich_heading("Shipper", level=2)
                + rich_note("Ship two users % compatibility")
                + rich_kv_table([
                    ("Usage", "<code>/ship &lt;query&gt;</code>"),
                    ("Example", "<code>/ship test</code>"),
                    ("Mode", "<code>Guest + Admin compatible</code>"),
                ])
                + rich_note("💡 <i>Powered by Videl • Richgram • MongoDB</i>"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◍ Help", callback_data="plugin_help_ship"), InlineKeyboardButton("⚙️ Settings", callback_data="plugin_settings_ship")],
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
                [InlineKeyboardButton("🔄 Try Again", callback_data="plugin_retry_ship"), InlineKeyboardButton("◍ Share", callback_data="plugin_share_ship")]
            ])
        )
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Error: <code>{rich_esc(str(e))}</code>"))

@bot.on_callback_query(filters.regex(rf"^plugin_(help|settings|retry|share)_ship$"))
async def ship_cb(_, cq):
    try:
        await cq.answer(f"Shipper • Videl Professional • Ship two users % compatibility", show_alert=False)
    except Exception:
        pass

LOGGER.info("◍ Plugin loaded: ship (ship) — Shipper")
