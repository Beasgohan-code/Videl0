"""Professional product and operations commands; reports only measured values."""
from __future__ import annotations

import time
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton

import config
from videl import bot, bot_start_time
from videl.utils.db import (
    get_db, get_served_chats_count, get_served_users_count,
    get_total_plays, is_connected,
)
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_reply, rich_edit

PLUGIN_COMMANDS = {
    "clean": "cleanpro", "filters_pro": "filtpro", "helper_pro": "helperpro",
    "invite": "invitepro", "language": "langpro", "notes_pro": "notespro",
    "reminder": "remind", "rules_pro": "rulespro", "scheduler": "schedule",
    "sticker_tools": "sticker", "telegraph2": "tgraph", "telegraph_pro": "telegraph",
    "translate": "tr", "ytsearch": "yts",
}


def _dashboard_url() -> str:
    return (getattr(config, "WEBAPP_URL", "https://videl0-control-panel.vercel.app") or "https://videl0-control-panel.vercel.app").rstrip("/")


def _active_plugins() -> list[str]:
    try:
        from videl.modules.plugins_loader import LOADED
        return sorted(LOADED)
    except Exception:
        return []


def _page_markup(page: int, pages: int) -> InlineKeyboardMarkup:
    row=[]
    if page>0: row.append(InlineKeyboardButton("‹ Previous",callback_data=f"pro_plugins_{page-1}"))
    if page+1<pages: row.append(InlineKeyboardButton("Next ›",callback_data=f"pro_plugins_{page+1}"))
    return InlineKeyboardMarkup([row] if row else [[InlineKeyboardButton("Close",callback_data="pro_close")]])


@bot.on_message(filters.command(["professional", "pro", "features"]))
async def pro_cmd(_, message: Message):
    plugins=_active_plugins()
    uptime=max(0,int(time.time()-bot_start_time))
    h,rem=divmod(uptime,3600); m,s=divmod(rem,60)
    await rich_reply(
        message,
        rich_heading("Videl · Professional",level=1)
        + rich_kv_table([
            ("Active add-ons",f"<code>{len(plugins)}</code> curated command plugins"),
            ("MongoDB",f"<code>{'connected' if is_connected() else 'disconnected'}</code>"),
            ("Groups",f"<code>{get_served_chats_count()}</code>"),
            ("Users",f"<code>{get_served_users_count()}</code>"),
            ("Music plays",f"<code>{get_total_plays()}</code>"),
            ("Uptime",f"<code>{h}h {m}m {s}s</code>"),
        ])
        + rich_note("Production features only: music playback, moderation, group operations, utilities and owner tools. Demo/entertainment and AI commands are disabled."),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Browse active tools",callback_data="pro_plugins_0")],
            [InlineKeyboardButton("Music help",callback_data="pro_music_help"),InlineKeyboardButton("Group help",callback_data="pro_group_help")],
            [InlineKeyboardButton("Open control panel",url=_dashboard_url())],
        ]),
    )


@bot.on_callback_query(filters.regex(r"^pro_plugins(?:_(\d+))?$"))
async def pro_plugins_cb(_, query: CallbackQuery):
    plugins=_active_plugins(); page=int(query.data.rsplit("_",1)[1]) if "_" in query.data and query.data.rsplit("_",1)[1].isdigit() else 0
    size=15; pages=max(1,(len(plugins)+size-1)//size); page=min(max(0,page),pages-1)
    subset=plugins[page*size:(page+1)*size]
    rows=[(f"<code>/{PLUGIN_COMMANDS.get(name,name.replace('_',''))}</code>","Active") for name in subset]
    text=rich_heading("Active professional tools",level=2)+rich_kv_table(rows or [("Status","No plugin handlers loaded")])+rich_note(f"Page {page+1}/{pages} · {len(plugins)} active add-ons; core music and moderation commands are listed in /help.")
    await rich_edit(query.message, text,reply_markup=_page_markup(page,pages))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^pro_(music_help|group_help)$"))
async def pro_help_cb(_, query: CallbackQuery):
    if query.data=="pro_music_help":
        text="<b>Music</b>\n<code>/play query</code> · <code>/vplay query</code> · <code>/cplay query</code>\n<code>/queue</code> · <code>/skip</code> · <code>/pause</code> · <code>/resume</code> · <code>/stop</code>\n<code>/seek</code> · <code>/lyrics</code> · <code>/playlist</code> · <code>/effects</code>"
    else:
        text="<b>Group operations</b>\n<code>/ban</code> · <code>/kick</code> · <code>/mute</code> · <code>/warn</code> · <code>/locks</code>\n<code>/welcome</code> · <code>/rules</code> · <code>/filter</code> · <code>/notes</code> · <code>/purge</code>\nUse /help for the bot's current command index."
    await rich_edit(query.message, rich_heading("Videl command guide",level=2)+rich_note(text),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="pro_plugins_0")]]))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^pro_close$"))
async def pro_close_cb(_, query: CallbackQuery):
    await query.message.delete(); await query.answer()


@bot.on_message(filters.command(["statspro","statpro"]))
async def statspro_cmd(_, message: Message):
    if not message.from_user or not config.is_owner(message.from_user.id):
        return await rich_reply(message, rich_note("Owner only."))
    db=get_db(); collections=0; documents=0
    if db is not None:
        try:
            names=db.list_collection_names(); collections=len(names)
            documents=sum(db[name].estimated_document_count() for name in names)
        except Exception:
            documents=-1
    uptime=max(0,int(time.time()-bot_start_time)); h,rem=divmod(uptime,3600); m,s=divmod(rem,60)
    await rich_reply(message,rich_heading("Videl · Operations",level=1)+rich_kv_table([
        ("MongoDB",f"<code>{'connected' if is_connected() else 'disconnected'}</code>"),
        ("Collections",f"<code>{collections}</code>" if documents>=0 else "<code>unavailable</code>"),
        ("Documents",f"<code>{documents}</code>" if documents>=0 else "<code>unavailable</code>"),
        ("Chats",f"<code>{get_served_chats_count()}</code>"),("Users",f"<code>{get_served_users_count()}</code>"),
        ("Music plays",f"<code>{get_total_plays()}</code>"),("Uptime",f"<code>{h}h {m}m {s}s</code>"),
    ])+rich_note("Counts are read from MongoDB at request time. No synthetic activity or sample metrics."),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open dashboard",url=_dashboard_url())]]))


@bot.on_message(filters.command(["helppro","helpp"]))
async def helppro_cmd(_, message: Message):
    await rich_reply(message,rich_heading("Videl · Help",level=1)+rich_kv_table([
        ("Music","<code>/play · /queue · /skip · /pause · /resume · /stop · /lyrics</code>"),
        ("Moderation","<code>/ban · /kick · /mute · /warn · /lock · /purge · /pin</code>"),
        ("Community","<code>/welcome · /goodbye · /rules · /filter · /save · /get</code>"),
        ("Utilities","<code>/weather · /wiki · /calc · /qr · /translate · /currency · /github</code>"),
        ("Operations","<code>/stats · /statspro · /logs · /sysinfo</code>"),
    ])+rich_note("Use /professional to browse active add-ons. Optional services may require their own API keys."),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Browse tools",callback_data="pro_plugins_0"),InlineKeyboardButton("Dashboard",url=_dashboard_url())]]))
