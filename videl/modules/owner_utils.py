"""Read-only owner operations. No chat-triggered shell, eval, git pull or process exit."""
import asyncio
import time
import psutil
from pyrogram import filters
from videl import bot, bot_start_time
from videl.core.queue import chat_queues
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc
from videl.utils.command_ui import rich_reply

OWNER = filters.user(6265999542) & filters.private


@bot.on_message(filters.command('sysinfo') & OWNER)
async def system_info(_, message):
    disk = await asyncio.to_thread(psutil.disk_usage, "/")
    rows = [("Uptime", f"{int(time.time() - bot_start_time)} seconds"),
            ("Memory", f"{psutil.Process().memory_info().rss // 1048576} MB"),
            ("Disk free", f"{disk.free // 1048576} MB")]
    await rich_reply(message, rich_heading("System diagnostics", level=2) + rich_kv_table(rows))




@bot.on_message(filters.command("active") & OWNER)
async def active(_, message):
    rows = [(str(cid), f"{len(queue)} tracks · {rich_esc(str(queue[0].get('title', 'Untitled'))[:60])}") for cid, queue in list(chat_queues.items()) if queue]
    await rich_reply(message, rich_heading("Active music queues", level=2) + (rich_kv_table(rows[:20]) if rows else rich_note("No non-empty queues.")))
