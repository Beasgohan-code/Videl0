"""Sticker collection tools using each user's own Telegram sticker pack."""
from __future__ import annotations

import asyncio

from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import body, escape, heading


async def kang(ctx) -> Screen:
    user = ctx.user
    if user is None:
        raise CommandError("Telegram did not identify your account. Send /kang from your own account, not as an anonymous admin.")
    reply = getattr(ctx.message, "reply_to_message", None)
    sticker = getattr(reply, "sticker", None) if reply else None
    if sticker is None:
        raise CommandError("Reply to a sticker with /kang to save it to your personal pack.")
    sticker_format = "video" if getattr(sticker, "is_video", False) else "animated" if getattr(sticker, "is_animated", False) else "static"
    from videl.utils.stickers import StickerPackError, add_to_personal_pack
    try:
        pack, created = await asyncio.to_thread(
            add_to_personal_pack, int(user.id), str(sticker.file_id),
            str(getattr(sticker, "emoji", None) or "🙂"), sticker_format,
        )
    except StickerPackError as error:
        if str(error) == "PACK_NOT_FOUND":
            raise CommandError("Telegram could not open your sticker pack. Try /kang again or contact the bot owner.") from None
        raise CommandError(str(error)) from None
    url = f"https://t.me/addstickers/{pack}"
    action = "Created your personal pack and added the sticker" if created else "Added the sticker to your personal pack"
    return Screen(heading("Sticker saved", 3) + body(f"{escape(action)} ✨<br><a href=\"{escape(url)}\">Open your Videl sticker pack</a><br><code>{escape(url)}</code>"))


COMMANDS = (Command("kang", kang, "Save a replied sticker to your personal Telegram pack", category="tools"),)
