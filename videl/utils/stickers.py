"""Telegram Bot API helpers for personal sticker packs."""
from __future__ import annotations

import re

import requests

import config


class StickerPackError(ValueError):
    pass


def _call(method: str, payload: dict) -> dict:
    token = str(getattr(config, "BOT_TOKEN", "") or "")
    if not token:
        raise StickerPackError("Sticker packs are not configured on this bot.")
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
            timeout=(4, 15),
        )
        data = response.json()
    except Exception:
        raise StickerPackError("Telegram could not be reached. Try again in a moment.") from None
    if not isinstance(data, dict) or not data.get("ok"):
        description = str(data.get("description") or "") if isinstance(data, dict) else ""
        if "STICKERSET_INVALID" in description.upper() or "STICKERSET_INVALID" in str(data).upper():
            raise StickerPackError("PACK_NOT_FOUND")
        if "already in" in description.lower() or "already exists" in description.lower():
            raise StickerPackError("That sticker is already in your pack.")
        raise StickerPackError("Telegram rejected this sticker. It may use an unsupported format or already belong to a pack.")
    result = data.get("result")
    return result if isinstance(result, dict) else {}


def add_to_personal_pack(user_id: int, sticker_file_id: str, emoji: str, sticker_format: str) -> tuple[str, bool]:
    username = re.sub(r"[^a-z0-9_]", "", str(getattr(config, "BOT_USERNAME", "") or "").lstrip("@").lower())
    if not username:
        raise StickerPackError("The bot username is not configured.")
    if sticker_format not in {"static", "animated", "video"}:
        raise StickerPackError("This sticker format is not supported.")
    pack_name = f"{username}_{int(user_id)}_{sticker_format}_by_{username}"
    if len(pack_name) > 64:
        raise StickerPackError("This bot username is too long to create a personal sticker pack.")
    item = {"sticker": sticker_file_id, "emoji_list": [emoji if emoji and len(emoji) <= 8 else "🙂"]}
    payload = {
        "user_id": int(user_id), "name": pack_name,
        "title": "Videl sticker picks",
        "sticker_format": sticker_format, "stickers": [item],
    }
    try:
        _call("getStickerSet", {"name": pack_name})
    except StickerPackError as error:
        if str(error) != "PACK_NOT_FOUND":
            raise
        _call("createNewStickerSet", payload)
        return pack_name, True
    _call("addStickerToSet", {"user_id": int(user_id), "name": pack_name, "sticker": item})
    return pack_name, False
