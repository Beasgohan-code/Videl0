"""Owner-only maintenance; general commands live in the replacement application."""
import config
from pyrogram import filters
from pyrogram.types import Message
from videl import bot
from videl.utils.rich_ui import rich_heading,rich_kv_table,rich_note
from videl.utils.command_ui import rich_reply

# Owner-only, private-chat maintenance. Preview first; no group/user purge.
@bot.on_message(filters.command("dbcleanup", prefixes=config.COMMAND_PREFIX_LIST) & filters.private & filters.user(6265999542))
async def cleanup_cmd(_, message: Message) -> None:
    import asyncio
    from videl.utils.db import cleanup_old_data
    args = (message.text or "").split()[1:]
    apply = args == ["apply"]
    if args and not apply:
        return await rich_reply(message, "Use /dbcleanup to preview or /dbcleanup apply to prune safe temporary records.")
    stats = await asyncio.to_thread(cleanup_old_data, 30, apply=apply)
    rows = [(name, str(count)) for name, count in stats.get("counts", {}).items()]
    await rich_reply(message,
        rich_heading("Retention results" if apply else "Retention preview", level=3)
        + rich_kv_table(rows)
        + rich_note("Complete." if stats.get("ok") else "Database unavailable or partial failure; check logs.")
        + rich_note("Only 30-day activity telemetry and delivered reminder records qualify. Playlists, settings, memberships, pending reminders and moderation history are preserved.")
        + ("" if apply else rich_note("Use /dbcleanup apply to run this safe retention policy.")))


@bot.on_message(filters.command("watchdog", prefixes=config.COMMAND_PREFIX_LIST) & filters.private & filters.user(6265999542))
async def watchdog_cmd(_, message: Message) -> None:
    from videl.core.watcher import watchdog_status
    state = watchdog_status()
    await rich_reply(message, rich_heading("Maintenance watchdog", level=3)
        + rich_kv_table([("Running", str(state["running"])), ("Checks healthy", str(state["healthy"]))]
                         + list(state["checks"].items()))
        + rich_note("Checks Telegram transport and MongoDB, recovers the CAPTCHA worker, leaves idle voice calls and runs safe retention. It does not restart the bot process."))
