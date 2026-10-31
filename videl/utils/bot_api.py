"""Small Bot API transport for features outside MTProto; no update polling or webhook changes."""

from __future__ import annotations
import asyncio
import copy
import json
import logging
import re
import requests
import config

log = logging.getLogger(__name__)

def without_visual_extras(payload: dict) -> dict:
    """Preserve destinations, callback actions, URLs, and delivery/privacy options."""
    result = copy.deepcopy(payload)
    # Keep Premium Emoji HTML entities in message text. This fallback removes
    # only optional keyboard decoration; flattening the text hid failed emoji
    # rendering behind ordinary Unicode glyphs.
    for row in (
        result.get("reply_markup", {}).get("inline_keyboard", [])
        if isinstance(result.get("reply_markup"), dict)
        else []
    ):
        for button in row:
            button.pop("style", None)
    return result


def call_bot_api(method: str, payload: dict, files=None):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return None, {"ok": False, "description": "Bot token is not configured"}
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,63}", method):
        return None, {"ok": False, "description": "Invalid Telegram API method"}
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    original = payload
    for attempt in range(2):
        try:
            if files:
                data = {
                    key: json.dumps(value) if isinstance(value, (dict, list)) else value
                    for key, value in payload.items()
                }
                response = requests.post(
                    endpoint, data=data, files=files, timeout=(5, 18)
                )
            else:
                response = requests.post(endpoint, json=payload, timeout=(5, 12))
            try:
                result = response.json()
            except ValueError:
                return response.status_code, {
                    "ok": False,
                    "description": "Telegram returned an invalid response; check delivery before retrying",
                }
            if not isinstance(result, dict):
                return response.status_code, {
                    "ok": False,
                    "description": "Telegram returned an invalid response",
                }
            description = str(result.get("description", "")).casefold()
            visual_rejection = any(marker in description for marker in (
                "button_style", "style_invalid", "style is not allowed", "unsupported button style",
            ))
            if response.status_code == 400 and not result.get("ok") and attempt == 0 and visual_rejection:
                basic = without_visual_extras(original)
                if basic != original:
                    payload = basic
                    continue  # Definite visual rejection; preserve text entities and actions.
            return response.status_code, result
        except requests.RequestException as exc:
            # requests exceptions can contain the complete URL, including BOT_TOKEN.
            log.warning(
                "Telegram %s delivery unconfirmed (%s); not retried",
                method,
                type(exc).__name__,
            )
            return None, {
                "ok": False,
                "description": "Telegram delivery could not be confirmed. Check the destination before retrying.",
            }
    return None, {"ok": False, "description": "Telegram did not confirm delivery"}


async def bot_api(method: str, payload: dict, files=None):
    """Run a Bot API request off-loop, optionally with multipart uploads."""
    return await asyncio.to_thread(call_bot_api, method, payload, files=files)
