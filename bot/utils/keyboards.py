"""
Videl0 • Keyboards — aiogram InlineKeyboard + Rich Buttons helper
Both plain InlineKeyboardMarkup and Rich BTN HTML rows.
"""
import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import SUPPORT_CHAT, SUPPORT_CHANNEL, BOT_USERNAME, WEBAPP_URL

def _btn(text, **kw): return InlineKeyboardButton(text=text, **kw)

def start_kb(is_owner=False):
    rows=[]
    rows.append([_btn("➕ Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"),
                 _btn("📊 Dashboard", url=WEBAPP_URL)])
    rows.append([_btn("⚙️ Help", callback_data="help"), _btn("📢 Updates", url=SUPPORT_CHANNEL)])
    rows.append([_btn("💬 Support", url=SUPPORT_CHAT), _btn("🎵 Music", callback_data="help:music")])
    if is_owner:
        rows.append([_btn("👑 Owner Panel", callback_data="owner_panel"), _btn("📈 Stats", callback_data="bot_stats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📚 General", callback_data="help:general"), _btn("🎵 Music", callback_data="help:music")],
        [_btn("🤖 AI", callback_data="help:ai"), _btn("🧰 Utility", callback_data="help:utility")],
        [_btn("🛡️ Admin", callback_data="help:admin"), _btn("👑 Owner", callback_data="help:owner")],
        [_btn("🎲 Fun", callback_data="help:fun"), _btn("🔙 Back", callback_data="start_back")],
    ])

def music_controls_kb(chat_id: int|None=None):
    style=random.choice(["primary","success","danger"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏸ Pause", callback_data="music:pause"),
         InlineKeyboardButton(text="▶️ Resume", callback_data="music:resume"),
         InlineKeyboardButton(text="⏭ Skip", callback_data="music:skip"),
         InlineKeyboardButton(text="⏹ Stop", callback_data="music:stop")],
        [InlineKeyboardButton(text="🔀 Shuffle", callback_data="music:shuffle"),
         InlineKeyboardButton(text="📜 Queue", callback_data="music:queue"),
         InlineKeyboardButton(text="🗑 Clear", callback_data="music:clear")],
    ])

def queue_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Skip", callback_data="music:skip"),
         InlineKeyboardButton(text="🗑 Clear", callback_data="music:clear")],
        [InlineKeyboardButton(text="❌ Close", callback_data="close")]
    ])

def close_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Close", callback_data="close")]])

def owner_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats", callback_data="owner:stats"),
         InlineKeyboardButton(text="📢 Broadcast", callback_data="owner:broadcast")],
        [InlineKeyboardButton(text="🚫 Gban List", callback_data="owner:gbans"),
         InlineKeyboardButton(text="👥 Sudo List", callback_data="owner:sudolist")],
        [InlineKeyboardButton(text="📦 Backup", callback_data="owner:backup"),
         InlineKeyboardButton(text="🔄 Restart", callback_data="owner:restart")],
        [InlineKeyboardButton(text="📜 Logs", callback_data="owner:logs"),
         InlineKeyboardButton(text="❌ Close", callback_data="close")],
    ])

# Rich button HTML for Rich Messages (Bot API 10.3)
def rich_start_buttons(bot_username: str):
    from bot.rich_ui import rich_button, rich_button_row
    return (
        rich_button_row(rich_button("Add to Group", url=f"https://t.me/{bot_username}?startgroup=true", style="primary"),
                        rich_button("Dashboard", url=WEBAPP_URL, style="success"))
        + rich_button_row(rich_button("Help", callback_data="help", style="primary"),
                          rich_button("Updates", url=SUPPORT_CHANNEL, style="default"))
        + rich_button_row(rich_button("Owner Panel", callback_data="owner_panel", style="danger"), rich_button("Close", callback_data="close", style="default"))
    )

def rich_music_buttons():
    from bot.rich_ui import rich_button, rich_button_row
    import random as _r
    def _s(): return _r.choice(["primary","success","danger"])
    return (
        rich_button_row(rich_button("Resume", callback_data="music:resume", style=_s()),
                        rich_button("Pause", callback_data="music:pause", style=_s()),
                        rich_button("Skip", callback_data="music:skip", style=_s()),
                        rich_button("Stop", callback_data="music:stop", style=_s()))
        + rich_button_row(rich_button("Queue", callback_data="music:queue", style="primary"),
                          rich_button("Shuffle", callback_data="music:shuffle", style="success"),
                          rich_button("Close", callback_data="close", style="danger"))
    )
