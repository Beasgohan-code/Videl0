"""
Videl0 • Keyboards — Cyber Dark Perfected
◍ ⬪ ⫶  small caps + sans bold  ⫶ ⬪ ◍
"""
import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import SUPPORT_CHAT, SUPPORT_CHANNEL, BOT_USERNAME, WEBAPP_URL
from bot.utils.fonts import sc, sb

def _btn(text, **kw): return InlineKeyboardButton(text=text, **kw)

def start_kb(is_owner=False):
    rows=[]
    rows.append([_btn(f"⬪ {sc('add to group')}", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"),
                 _btn(f"◍ {sc('dashboard')}", url=WEBAPP_URL)])
    rows.append([_btn(f"⫶ {sc('help')}", callback_data="help"), _btn(f"⦿ {sc('updates')}", url=SUPPORT_CHANNEL)])
    rows.append([_btn(f"◎ {sc('support')}", url=SUPPORT_CHAT), _btn(f"⬪ {sc('music')}", callback_data="help:music")])
    if is_owner:
        rows.append([_btn(f"◍ {sc('owner panel')}", callback_data="owner_panel"), _btn(f"⫶ {sc('stats')}", callback_data="bot_stats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"◍ {sc('general')}", callback_data="help:general"), _btn(f"⬪ {sc('music')}", callback_data="help:music")],
        [_btn(f"⦿ {sc('ai')}", callback_data="help:ai"), _btn(f"⫶ {sc('utility')}", callback_data="help:utility")],
        [_btn(f"◎ {sc('admin')}", callback_data="help:admin"), _btn(f"◍ {sc('owner')}", callback_data="help:owner")],
        [_btn(f"⬪ {sc('fun')}", callback_data="help:fun"), _btn(f"⫶ {sc('back')}", callback_data="start_back")],
    ])

def music_controls_kb(chat_id: int|None=None):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"◍ {sc('pause')}", callback_data="music:pause"),
         InlineKeyboardButton(text=f"⬪ {sc('resume')}", callback_data="music:resume"),
         InlineKeyboardButton(text=f"⫶ {sc('skip')}", callback_data="music:skip"),
         InlineKeyboardButton(text=f"⬩ {sc('stop')}", callback_data="music:stop")],
        [InlineKeyboardButton(text=f"◎ {sc('shuffle')}", callback_data="music:shuffle"),
         InlineKeyboardButton(text=f"⦿ {sc('queue')}", callback_data="music:queue"),
         InlineKeyboardButton(text=f"◍ {sc('clear')}", callback_data="music:clear")],
    ])

def queue_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⫶ {sc('skip')}", callback_data="music:skip"),
         InlineKeyboardButton(text=f"◍ {sc('clear')}", callback_data="music:clear")],
        [InlineKeyboardButton(text=f"⬪ {sc('close')}", callback_data="close")]
    ])

def close_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"⬪ {sc('close')}", callback_data="close")]])

def owner_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"◍ {sc('stats')}", callback_data="owner:stats"),
         InlineKeyboardButton(text=f"⬪ {sc('broadcast')}", callback_data="owner:broadcast")],
        [InlineKeyboardButton(text=f"⫶ {sc('gban list')}", callback_data="owner:gbans"),
         InlineKeyboardButton(text=f"◎ {sc('sudo list')}", callback_data="owner:sudolist")],
        [InlineKeyboardButton(text=f"⬩ {sc('backup')}", callback_data="owner:backup"),
         InlineKeyboardButton(text=f"⦿ {sc('restart')}", callback_data="owner:restart")],
        [InlineKeyboardButton(text=f"◍ {sc('logs')}", callback_data="owner:logs"),
         InlineKeyboardButton(text=f"⬪ {sc('close')}", callback_data="close")],
    ])

# Rich button HTML for Rich Messages (Bot API 10.3) — Cyber Dark
def rich_start_buttons(bot_username: str):
    from bot.rich_ui import rich_button, rich_button_row
    return (
        rich_button_row(rich_button(f"⬪ {sc('add to group')}", url=f"https://t.me/{bot_username}?startgroup=true", style="primary"),
                        rich_button(f"◍ {sc('dashboard')}", url=WEBAPP_URL, style="success"))
        + rich_button_row(rich_button(f"⫶ {sc('help')}", callback_data="help", style="primary"),
                          rich_button(f"◎ {sc('updates')}", url=SUPPORT_CHANNEL, style="default"))
        + rich_button_row(rich_button(f"◍ {sc('owner panel')}", callback_data="owner_panel", style="danger"), rich_button(f"⬪ {sc('close')}", callback_data="close", style="default"))
    )

def rich_music_buttons():
    from bot.rich_ui import rich_button, rich_button_row
    import random as _r
    def _s(): return _r.choice(["primary","success","danger"])
    return (
        rich_button_row(rich_button(f"⬪ {sc('resume')}", callback_data="music:resume", style=_s()),
                        rich_button(f"◍ {sc('pause')}", callback_data="music:pause", style=_s()),
                        rich_button(f"⫶ {sc('skip')}", callback_data="music:skip", style=_s()),
                        rich_button(f"⬩ {sc('stop')}", callback_data="music:stop", style=_s()))
        + rich_button_row(rich_button(f"◎ {sc('queue')}", callback_data="music:queue", style="primary"),
                          rich_button(f"⬪ {sc('shuffle')}", callback_data="music:shuffle", style="success"),
                          rich_button(f"◍ {sc('close')}", callback_data="close", style="danger"))
    )
