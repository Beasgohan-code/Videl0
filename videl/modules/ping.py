# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import os
import time
from datetime import timedelta

import psutil
import speedtest
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from videl import bot, assistant, bot_start_time
from videl.modules.block import user_allowed
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_img,
    rich_kv_table,
    rich_send,
)


def supp_markup():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text="🍬 sᴜᴘᴘᴏʀᴛ 🍬", url=config.SUPPORT_GROUP),
    ]])


# ── /ping ──────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command(["ping", "ping@"]))
async def ping_cmd(client, message: Message) -> None:
    chat_id = message.chat.id
    start = time.perf_counter()
    try:
        probe = await bot.send_message(chat_id, "🏓 ᴘɪɴɢɪɴɢ...")
    except Exception:
        probe = None
    latency = round((time.perf_counter() - start) * 1000)

    try:
        uptime = str(timedelta(seconds=int(time.time() - bot_start_time)))
    except Exception:
        uptime = "?"
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        process = psutil.Process(os.getpid())
        ram = process.memory_info().rss / 1024 / 1024
        disk = psutil.disk_usage("/")
        disk_str = f"{disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)"
    except Exception:
        cpu, ram, disk_str = "?", "?", "?"

    try:
        t0 = time.perf_counter()
        await assistant.get_me()
        pytg = f"{round((time.perf_counter() - t0) * 1000)}ms"
    except Exception:
        pytg = "N/A"

    text = (
        f"🏓 <b>ᴘᴏɴɢ</b> : <code>{latency}ms</code>\n\n"
        f"⏱ ᴜᴘᴛɪᴍᴇ: <code>{uptime}</code>\n"
        f"💾 ʀᴀᴍ: <code>{ram if isinstance(ram, str) else f'{ram:.1f} MB'}</code>\n"
        f"🖥 ᴄᴘᴜ: <code>{cpu}%</code>\n"
        f"📀 ᴅɪsᴋ: <code>{disk_str}</code>\n"
        f"🎙 ᴘʏᴛɢᴄ: <code>{pytg}</code>"
    )
    try:
        if probe:
            await probe.edit_text(text)
        else:
            await bot.send_message(chat_id, text)
    except Exception:
        try:
            await message.reply_text(f"🏓 Pong {latency}ms")
        except Exception:
            pass


# ── /speedtest ─────────────────────────────────────────────────────────────────

def _run_speedtest(m):
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        st.download()
        st.upload()
        st.results.share()
        return st.results.dict()
    except Exception:
        return None


@bot.on_message(
    filters.command(["speedtest", "spt"])
    & filters.user(config.OWNER_ID)
)
async def speedtest_cmd(client, message: Message) -> None:

    chat_id = message.chat.id
    m = await rich_send(bot, chat_id, rich_heading("⏳ Running speedtest...", level=3))

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_speedtest, m)

    if result is None:
        from videl.utils.rich_ui import rich_edit
        await rich_edit(m, rich_heading("❌ Speedtest failed", level=3))
        return

    download = result["download"] / 1_000_000
    upload   = result["upload"]   / 1_000_000
    ping     = result["ping"]
    isp      = result["client"]["isp"]
    country  = result["client"]["country"]
    server   = result["server"]["name"]
    sponsor  = result["server"]["sponsor"]
    s_cc     = result["server"]["cc"]
    s_lat    = result["server"]["latency"]
    share    = result["share"]

    caption = (
        rich_heading("⚡ Speedtest Results", level=3)
        + rich_img(share)
        + rich_kv_table([
            ("ɪsᴘ", f"<code>{rich_esc(isp)}</code>"),
            ("ᴄᴏᴜɴᴛʀʏ", f"<code>{rich_esc(country)}</code>"),
        ], headers=["ᴄʟɪᴇɴᴛ ɪɴғᴏ", ""])
        + rich_kv_table([
            ("ɴᴀᴍᴇ", f"<code>{rich_esc(server)}</code>"),
            ("sᴘᴏɴsᴏʀ", f"<code>{rich_esc(sponsor)}</code>"),
            ("ᴄᴏᴜɴᴛʀʏ", f"<code>{rich_esc(s_cc)}</code>"),
            ("ʟᴀᴛᴇɴᴄʏ", f"<code>{s_lat} ms</code>"),
        ], headers=["sᴇʀᴠᴇʀ ɪɴғᴏ", ""])
        + rich_kv_table([
            ("ᴘɪɴɢ", f"<code>{ping:.2f} ms</code>"),
            ("ᴅᴏᴡɴʟᴏᴀᴅ", f"<code>{download:.2f} Mbps</code>"),
            ("ᴜᴘʟᴏᴀᴅ", f"<code>{upload:.2f} Mbps</code>"),
        ], headers=["sᴘᴇᴇᴅ", ""])
        + f"<p>By <a href=\"{config.SUPPORT_GROUP}\">Videl Music</a></p>"
    )

    try:
        await m.delete()
    except Exception:
        pass
    await rich_send(bot, chat_id, caption, reply_markup=supp_markup())

