"""Modern Telegram tools; every action is permission-checked and actually calls Telegram."""

from __future__ import annotations
import html
from importlib.metadata import version
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import CopyTextButton, InlineKeyboardMarkup
import config
from videl import bot
from videl.utils.bot_api import bot_api
from videl.utils.bot_ui import button
from videl.utils.permissions import is_user_authorized
from videl.utils.premium_emojis import PREMIUM_IDS, USE_PREMIUM
from videl.utils.rich_ui import rich_heading, rich_note, rich_reply, rich_edit

HELP = (
    rich_heading("Telegram tools", level=2)
    + rich_note(
        "Real API actions. No paid gifts, Stars spending or automatic reactions are enabled."
    )
    + "<p><b>Polls</b><br><code>/poll Question | A | B</code><br><code>/quiz Question | *Correct | Other</code></p>"
    + "<p>Flags before the question: <code>--multiple --public --shuffle --revote --add-options --hide-results --members-only</code>. Quiz answers marked * can have multiple correct options. Polls are anonymous unless --public is requested.</p>"
    + "<p><b>Group admins</b><br><code>/react 👍</code> on a replied message; <code>/react clear</code> removes the bot’s reaction.<br><code>/topicnew Topic title</code> in a forum; <code>/topicclose</code> and <code>/topicopen</code> inside a topic.</p>"
    + "<p><b>Owner diagnostics</b><br><code>/apiinfo</code> checks the bot identity with Telegram.<br><code>/emojiinfo</code> on a custom-emoji message extracts IDs; <code>/emojiinfo check</code> validates the configured IDs with Telegram. Valid IDs alone do not grant permission to render them.</p>"
)


@bot.on_message(filters.command("modernhelp"))
async def modern_help(_, message):
    await rich_reply(message, HELP)


@bot.on_callback_query(filters.regex(r"^modern_tools_help$"))
async def modern_help_callback(_, query):
    await query.answer()
    await rich_edit(query, HELP)


async def outcome(message, method, payload, success):
    status, data = await bot_api(method, payload)
    if not status or not data.get("ok"):
        description = html.escape(
            str(data.get("description", "Telegram rejected the request"))
        )
        await rich_reply(
            message,
            rich_heading("Request not confirmed", level=3) + rich_note(description),
        )
        return None
    await rich_reply(message, rich_heading(success, level=3))
    return data.get("result")


@bot.on_message(filters.command("react"))
async def react_command(_, message):
    if not await is_user_authorized(message):
        return await rich_reply(
            message, rich_note("Group admins or the bot owner can set bot reactions.")
        )
    target = message.reply_to_message
    if not target:
        return await rich_reply(
            message,
            rich_note(
                "Reply to a message with <code>/react 👍</code> or <code>/react clear</code>."
            ),
        )
    emoji = " ".join((message.command or [])[1:]).strip() or "👍"
    if emoji not in {
        "👍",
        "👎",
        "❤",
        "❤️",
        "🔥",
        "🥰",
        "👏",
        "🎉",
        "🤔",
        "😢",
        "clear",
    }:
        return await rich_reply(
            message,
            rich_note(
                "Choose 👍 👎 ❤ 🔥 🥰 👏 🎉 🤔 😢 or clear. The chat must allow the chosen reaction."
            ),
        )
    if emoji == "❤️":
        emoji = "❤"
    await outcome(
        message,
        "setMessageReaction",
        {
            "chat_id": message.chat.id,
            "message_id": target.id,
            "reaction": [] if emoji == "clear" else [{"type": "emoji", "emoji": emoji}],
        },
        "Reaction updated",
    )


@bot.on_message(filters.command(["topicnew", "topicclose", "topicopen"]))
async def topic_command(_, message):
    if (
        not getattr(message.chat, "is_forum", False)
        or message.chat.type != ChatType.SUPERGROUP
    ):
        return await rich_reply(
            message,
            rich_note("This tool requires a forum supergroup with topics enabled."),
        )
    if not await is_user_authorized(message):
        return await rich_reply(
            message, rich_note("Only group admins or the bot owner can manage topics.")
        )
    command = message.command[0].split("@", 1)[0].lower()
    payload = {"chat_id": message.chat.id}
    if command == "topicnew":
        title = " ".join(message.command[1:]).strip()
        if not title or len(title) > 128:
            return await rich_reply(
                message,
                rich_note(
                    "Use <code>/topicnew Topic title</code> with 1–128 characters."
                ),
            )
        payload["name"] = title
        await outcome(message, "createForumTopic", payload, "Topic created")
    else:
        topic_id = getattr(message, "message_thread_id", None)
        if not topic_id or topic_id == 1:
            return await rich_reply(
                message, rich_note("Run this command inside a non-General forum topic.")
            )
        payload["message_thread_id"] = topic_id
        await outcome(
            message,
            "closeForumTopic" if command == "topicclose" else "reopenForumTopic",
            payload,
            "Topic updated",
        )


@bot.on_message(filters.command("apiinfo") & filters.user(config.OWNER_ID))
async def api_info(_, message):
    status, data = await bot_api("getMe", {})
    if not status or not data.get("ok"):
        return await rich_reply(
            message,
            rich_note(
                "Telegram identity could not be verified. Check backend connectivity and configuration."
            ),
        )
    me = data["result"]
    info = (
        rich_heading("Telegram API status", level=2)
        + rich_note(
            f"Verified bot: <b>{html.escape(me.get('first_name', 'Bot'))}</b> · @{html.escape(me.get('username', ''))}"
        )
        + f"<p>Bot ID: <code>{me['id']}</code><br>Kurigram: <code>{version('kurigram')}</code><br>Visual emoji configuration: <b>{'Enabled' if USE_PREMIUM else 'Disabled'}</b></p>"
        + "<p>Rich cards, styled keyboards, forum-aware replies, copy buttons and advanced polls are integrated. Server permission and client support still apply. Telegram does not expose a Bot API version through getMe.</p>"
    )
    await rich_reply(
        message,
        info,
        reply_markup=InlineKeyboardMarkup(
            [[button("Copy bot ID", copy_text=CopyTextButton(text=str(me["id"])))]]
        ),
    )


@bot.on_message(filters.command("emojiinfo") & filters.user(config.OWNER_ID))
async def emoji_info(_, message):
    if len(message.command) > 1 and message.command[1].lower() == "check":
        ids = list(dict.fromkeys(PREMIUM_IDS.values()))[:200]
        status, data = await bot_api(
            "getCustomEmojiStickers", {"custom_emoji_ids": ids}
        )
        if not status or not data.get("ok"):
            return await rich_reply(
                message,
                rich_note(
                    "Telegram could not validate the configured IDs. No IDs were marked verified."
                ),
            )
        valid = {str(item.get("custom_emoji_id")) for item in data.get("result", [])}
        missing = [emoji_id for emoji_id in ids if emoji_id not in valid]
        text = f"Telegram resolved <b>{len(valid)} / {len(ids)}</b> configured IDs."
        if missing:
            text += "<br>Unresolved: " + ", ".join(
                f"<code>{html.escape(x)}</code>" for x in missing
            )
        return await rich_reply(
            message,
            rich_heading("Emoji lookup", level=3)
            + rich_note(text)
            + "<p>Lookup success does not confirm Premium rendering eligibility. Rejected icons fall back to readable buttons.</p>",
        )
    source = message.reply_to_message
    ids = (
        list(
            dict.fromkeys(
                str(entity.custom_emoji_id)
                for entity in (
                    getattr(source, "entities", None)
                    or getattr(source, "caption_entities", None)
                    or []
                )
                if getattr(entity, "custom_emoji_id", None)
            )
        )
        if source
        else []
    )
    if not ids:
        return await rich_reply(
            message,
            rich_note(
                "Reply to a custom-emoji message with <code>/emojiinfo</code>, or use <code>/emojiinfo check</code> to look up the configured IDs."
            ),
        )
    text = "<br>".join(f"<code>{html.escape(value)}</code>" for value in ids[:50])
    keys = [
        [button(f"Copy ID {i+1}", copy_text=CopyTextButton(text=value))]
        for i, value in enumerate(ids[:6])
    ]
    await rich_reply(
        message,
        rich_heading("Custom emoji IDs", level=3) + rich_note(text),
        reply_markup=InlineKeyboardMarkup(keys),
    )
