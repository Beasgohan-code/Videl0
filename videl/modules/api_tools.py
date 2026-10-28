"""Modern Telegram tools; every action is permission-checked and actually calls Telegram."""

from __future__ import annotations
import asyncio
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
from videl.utils.premium_emojis import PREMIUM_IDS, SUPPLIED_EMOJI_PACKS, USE_PREMIUM, pe
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_table, rich_hr
from videl.utils.command_ui import rich_reply, rich_edit, notice, usage, result as ui_result

PUBLIC_HELP = (
    rich_heading("Telegram tools", level=2)
    + rich_note("Real Telegram actions with permission checks. No paid gifts, Stars spending or automatic reactions are enabled.")
    + rich_heading("Polls & quizzes", level=3)
    + rich_table(["Command", "What it does"], [
        ("<code>/poll Question | A | B</code>", "Create a poll; polls are anonymous unless <code>--public</code> is set."),
        ("<code>/quiz Question | *Correct | Other</code>", "Create a quiz; mark correct answer(s) with <code>*</code>."),
        ("<code>/pollstop</code>", "Close a replied-to poll created by this bot (admins only)."),
    ])
    + rich_note("Optional flags: <code>--multiple --public --shuffle --revote --add-options --hide-results --members-only --silent --protect --seconds=60</code>. Timers allow 5–600 seconds.")
    + rich_hr()
    + rich_heading("Forum & reaction tools", level=3)
    + rich_table(["Command", "Where / purpose"], [
        ("<code>/react 👍</code> · <code>/react clear</code>", "Reply to a message; group admins or the owner can set or clear the bot reaction."),
        ("<code>/topicnew Title</code>", "Create a topic in a forum supergroup."),
        ("<code>/topicrename Title</code>", "Rename the topic you are currently in."),
        ("<code>/topicclose</code> · <code>/topicopen</code>", "Close or reopen the current topic."),
    ])
    + rich_hr()
    + rich_heading("Copy & formatting", level=3)
    + rich_table(["Command", "Result"], [
        ("<code>/copy text</code>", "Create a native Telegram copy-text button (or reply to a text message)."),
    ])
    + rich_note("Rich cards, custom emoji and styled buttons depend on Telegram client support and the bot owner’s eligibility. Ordinary Unicode emoji fallbacks remain available.")
)

OWNER_HELP = (
    rich_hr()
    + rich_heading("Owner diagnostics", level=3)
    + rich_table(["Command", "Diagnostic"], [
        ("<code>/apiinfo</code>", "Verify the bot identity with Telegram."),
        ("<code>/emojiinfo</code>", "Reply to a custom-emoji message to extract its IDs."),
        ("<code>/emojiinfo list</code>", "Browse, preview, and copy IDs from every supplied emoji pack."),
        ("<code>/emojiinfo check</code>", "Ask Telegram to resolve configured IDs; lookup does not grant rendering permission."),
        ("<code>/setbotphoto</code>", "Owner-only: use the bundled image, a replied photo, or a direct HTTPS image URL. Examples: <code>/setbotphoto https://example.com/photo.jpg</code>, or reply to a photo with <code>/setbotphoto</code>."),
    ])
)
HELP = PUBLIC_HELP + OWNER_HELP


def public_help(message):
    owner = bool(message and message.from_user and message.from_user.id == config.OWNER_ID
                 and str(getattr(message.chat.type, "value", message.chat.type)) == "private")
    return HELP if owner else PUBLIC_HELP


@bot.on_callback_query(filters.regex(r"^modern_tools_help$"))
async def modern_help_callback(_, query):
    await query.answer()
    await rich_edit(query, PUBLIC_HELP)


async def outcome(message, method, payload, success, *, forum_controls=False):
    status, data = await bot_api(method, payload)
    if not status or not data.get("ok"):
        description = html.escape(
            str(data.get("description", "Telegram rejected the request"))
        )
        await rich_reply(
            message,
            ui_result(
                "Telegram request not confirmed",
                [("Status", "Not confirmed")],
                body=description,
            ),
        )
        return None
    result = data.get("result")
    markup = None
    if forum_controls:
        topic_id = payload.get("message_thread_id") or (result.get("message_thread_id") if isinstance(result, dict) else None)
        if topic_id and topic_id != 1:
            markup = topic_keyboard(payload["chat_id"], topic_id)
    await rich_reply(
        message,
        ui_result(success, [("Status", "Confirmed")], body="Telegram confirmed this change."),
        reply_markup=markup,
    )
    return result


@bot.on_message(filters.command("react", prefixes=config.COMMAND_PREFIX_LIST))
async def react_command(_, message):
    if not await is_user_authorized(message):
        return await rich_reply(
            message,
            notice("Only group admins or the bot owner can set bot reactions.", status="error", title="Admin permission required"),
        )
    target = message.reply_to_message
    if not target:
        return await rich_reply(
            message,
            usage("/react 👍 or /react clear", "Reply to the message whose reaction you want to set or remove."),
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
            notice("Choose 👍 👎 ❤ 🔥 🥰 👏 🎉 🤔 😢 or clear. The chat must allow the chosen reaction.", status="warning", title="Reaction not supported"),
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


@bot.on_message(filters.command(["topicnew", "topicrename", "topicclose", "topicopen"], prefixes=config.COMMAND_PREFIX_LIST))
async def topic_command(_, message):
    if (
        not getattr(message.chat, "is_forum", False)
        or message.chat.type != ChatType.SUPERGROUP
    ):
        return await rich_reply(
            message,
            notice("This tool requires a forum supergroup with topics enabled.", status="warning", title="Forum topics required"),
        )
    if not await is_user_authorized(message):
        return await rich_reply(
            message,
            notice("Only group admins or the bot owner can manage topics.", status="error", title="Admin permission required"),
        )
    command = message.command[0].split("@", 1)[0].lower()
    payload = {"chat_id": message.chat.id}
    if command == "topicnew":
        title = " ".join(message.command[1:]).strip()
        if not title or len(title.encode("utf-16-le")) // 2 > 128:
            return await rich_reply(
                message,
                usage("/topicnew Topic title", "Use 1–128 Telegram UTF-16 units."),
            )
        payload["name"] = title
        await outcome(message, "createForumTopic", payload, "Topic created", forum_controls=True)
    else:
        topic_id = getattr(message, "message_thread_id", None)
        if not topic_id or topic_id == 1:
            return await rich_reply(
                message,
                notice("Run this command inside a non-General forum topic.", status="warning", title="Open the target topic first"),
            )
        payload["message_thread_id"] = topic_id
        if command == "topicrename":
            title = " ".join(message.command[1:]).strip()
            if not title or len(title.encode("utf-16-le")) // 2 > 128:
                return await rich_reply(message, usage("/topicrename Topic title", "Use 1–128 Telegram UTF-16 units inside a non-General topic."))
            payload["name"] = title
            return await outcome(message, "editForumTopic", payload, "Topic renamed", forum_controls=True)
        await outcome(
            message,
            "closeForumTopic" if command == "topicclose" else "reopenForumTopic",
            payload,
            "Topic updated",
            forum_controls=True,
        )


@bot.on_message(filters.command("apiinfo", prefixes=config.COMMAND_PREFIX_LIST) & filters.user(6265999542) & filters.private)
async def api_info(_, message):
    status, data = await bot_api("getMe", {})
    if not status or not data.get("ok"):
        return await rich_reply(
            message,
            notice(
                "Telegram identity could not be verified. Check backend connectivity and configuration.",
                status="error", title="Identity check failed",
            ),
        )
    me = data["result"]
    info = (
        rich_heading("Verified Telegram bot", level=2)
        + rich_kv_table([
            ("Bot name", html.escape(me.get("first_name", "Bot"))),
            ("Username", "@" + html.escape(me.get("username", ""))),
            ("Bot ID", f"<code>{me['id']}</code>"),
            ("Kurigram", f"<code>{html.escape(version('kurigram'))}</code>"),
            ("Custom emoji", "Enabled" if USE_PREMIUM else "Unicode fallback"),
        ])
        + rich_note("Rich cards, styled keyboards, forum-aware replies, copy buttons and advanced polls are integrated. Telegram does not expose a Bot API version through <code>getMe</code>; actual rendering also depends on client support and eligibility.")
    )
    await rich_reply(
        message,
        info,
        reply_markup=InlineKeyboardMarkup(
            [[button("Copy bot ID", copy_text=CopyTextButton(text=str(me["id"])), icon="ios_file")]]
        ),
    )


EMOJI_BROWSER_PAGE_SIZE = 10


def emoji_browser_menu():
    """Build the private owner menu for every configured emoji pack."""
    from videl.utils.rich_ui import rich_esc

    body = rich_heading("Premium emoji library", level=2)
    body += rich_note("Browse each supplied set, preview its custom artwork, and copy the exact IDs for a page. Telegram eligibility still controls custom rendering.")
    rows = []
    for name, entries in SUPPLIED_EMOJI_PACKS.items():
        count = len(entries.strip().splitlines())
        rows.append((rich_esc(name.replace("_", " ").title()), str(count)))
    body += rich_table(["Pack", "Emojis"], rows)
    choices = [
        button(name.replace("_", " ").title() + f" · {len(entries.strip().splitlines())}",
               callback_data=f"emojilist:{name}:0", style="primary", icon=f"{name}_001")
        for name, entries in SUPPLIED_EMOJI_PACKS.items()
    ]
    keyboard_rows = [choices[i:i + 2] for i in range(0, len(choices), 2)]
    return body, InlineKeyboardMarkup(keyboard_rows)


def emoji_browser_page(pack: str, page: int):
    """Return one bounded, copyable page of custom-emoji IDs."""
    from videl.utils.premium_emojis import tg_emoji

    if pack not in SUPPLIED_EMOJI_PACKS:
        raise ValueError("Unknown premium emoji pack")
    if isinstance(page, bool) or not isinstance(page, int) or page < 0:
        raise ValueError("Invalid premium emoji page")
    entries = [row.rsplit(maxsplit=1) for row in SUPPLIED_EMOJI_PACKS[pack].strip().splitlines()]
    pages = max(1, (len(entries) + EMOJI_BROWSER_PAGE_SIZE - 1) // EMOJI_BROWSER_PAGE_SIZE)
    if page >= pages:
        raise ValueError("Premium emoji page is out of range")
    start = page * EMOJI_BROWSER_PAGE_SIZE
    current = entries[start:start + EMOJI_BROWSER_PAGE_SIZE]
    body = rich_heading(f"{pack.replace('_', ' ').title()} · {start + 1}–{start + len(current)}", level=2)
    body += rich_table(
        ["#", "Preview", "Fallback", "Bot alias", "Emoji ID"],
        [
            (str(start + index + 1), tg_emoji(emoji_id, fallback), fallback,
             f"<code>{pack}_{start + index + 1:03d}</code>", f"<code>{emoji_id}</code>")
            for index, (fallback, emoji_id) in enumerate(current)
        ],
    )
    body += rich_note(f"Page {page + 1} of {pages}. Bot aliases such as <code>{pack}_{start + 1:03d}</code> work with the premium emoji helper; copy IDs for direct use. IDs do not grant Premium eligibility.")
    controls = []
    if page > 0:
        controls.append(button("Previous", callback_data=f"emojilist:{pack}:{page - 1}", icon="left"))
    if page + 1 < pages:
        controls.append(button("Next", callback_data=f"emojilist:{pack}:{page + 1}", icon="right"))
    keyboard_rows = [controls] if controls else []
    ids = "\n".join(emoji_id for _, emoji_id in current)
    aliases = "\n".join(f"{pack}_{start + index + 1:03d}" for index in range(len(current)))
    keyboard_rows.append([
        button("Copy IDs", copy_text=CopyTextButton(text=ids), icon="ios_file"),
        button("Copy bot aliases", copy_text=CopyTextButton(text=aliases), icon=f"{pack}_001"),
    ])
    keyboard_rows.append([button("All emoji packs", callback_data="emojilist:menu:0", icon="ios_folder")])
    return body, InlineKeyboardMarkup(keyboard_rows)


@bot.on_message(filters.command("emojiinfo", prefixes=config.COMMAND_PREFIX_LIST) & filters.user(config.OWNER_ID) & filters.private)
async def emoji_info(_, message):
    if len(message.command) > 1 and message.command[1].lower() == "list":
        pack = message.command[2].lower() if len(message.command) > 2 else ""
        if not pack:
            body, markup = emoji_browser_menu()
        else:
            try:
                body, markup = emoji_browser_page(pack, 0)
            except ValueError:
                names = ", ".join(SUPPLIED_EMOJI_PACKS)
                return await rich_reply(message, usage("/emojiinfo list [pack]", f"Choose one pack: {names}"))
        return await rich_reply(message, body, reply_markup=markup)
    if len(message.command) > 1 and message.command[1].lower() == "check":
        ids = list(dict.fromkeys(PREMIUM_IDS.values()))
        valid = set()
        for offset in range(0, len(ids), 200):
            chunk = ids[offset:offset + 200]
            status, data = await bot_api(
                "getCustomEmojiStickers", {"custom_emoji_ids": chunk}
            )
            if not status or not data.get("ok"):
                return await rich_reply(
                    message,
                    notice(
                        "Telegram could not validate this batch of configured IDs. No IDs in that batch were marked verified.",
                        status="error", title="Emoji lookup unavailable",
                    ),
                )
            valid.update(
                str(item.get("custom_emoji_id")) for item in data.get("result", [])
            )
        missing = [emoji_id for emoji_id in ids if emoji_id not in valid]
        shown = missing[:20]
        fields = [
            ("Resolved", f"{len(valid)} / {len(ids)}"),
            ("Status", "All IDs resolved" if not missing else f"{len(missing)} unresolved"),
        ]
        body = "Lookup confirms only that Telegram can resolve an ID; it does not grant permission to render custom emoji. Unicode fallbacks remain available."
        if len(missing) > len(shown):
            body += f" Showing the first {len(shown)} unresolved IDs; {len(missing) - len(shown)} more are omitted."
        card = rich_heading("Configured custom emoji lookup", level=2) + rich_kv_table(fields)
        if shown:
            card += rich_table(["Unresolved custom emoji ID"], [(f"<code>{html.escape(value)}</code>",) for value in shown])
        card += rich_note(body)
        return await rich_reply(message, card)
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
            usage("/emojiinfo", "Reply to a message containing custom emoji to extract IDs; use /emojiinfo list to browse packs or /emojiinfo check to validate IDs."),
        )
    shown = ids[:50]
    table = rich_table(
        ["No.", "Custom emoji ID"],
        [(str(index), f"<code>{html.escape(value)}</code>") for index, value in enumerate(shown, 1)],
    )
    keys = [
        [button(f"Copy ID {i+1}", copy_text=CopyTextButton(text=value), icon="ios_file")]
        for i, value in enumerate(ids[:6])
    ]
    card = rich_heading("Custom emoji IDs", level=2) + table
    if len(ids) > len(shown):
        card += rich_note(f"Showing {len(shown)} of {len(ids)} IDs. Reply to a smaller selection to copy a specific one.")
    await rich_reply(message, card, reply_markup=InlineKeyboardMarkup(keys))


@bot.on_callback_query(filters.regex(r"^emojilist:[a-z_]{2,20}:[0-9]{1,3}$"))
async def emoji_browser_callback(_, query):
    if (not query.message or not query.from_user or query.from_user.id != config.OWNER_ID
            or query.message.chat.type != ChatType.PRIVATE):
        return await query.answer("This private owner-only emoji browser is not available here.", show_alert=True)
    _, pack, raw_page = query.data.split(":")
    try:
        body, markup = emoji_browser_menu() if pack == "menu" else emoji_browser_page(pack, int(raw_page))
    except (ValueError, TypeError):
        return await query.answer("That pack or page is no longer available. Reopen /emojiinfo list.", show_alert=True)
    await query.answer()
    await rich_edit(query, body, reply_markup=markup)


@bot.on_message(filters.command("setbotphoto", prefixes=config.COMMAND_PREFIX_LIST) & filters.user(config.OWNER_ID) & filters.private)
async def set_bot_profile_photo(client, message):
    """Set the bot avatar from a replied photo, HTTPS image URL, or bundled default."""
    from videl.utils.bot_profile import download_profile_image, profile_photo_upload

    try:
        target = getattr(message, "reply_to_message", None)
        supplied = " ".join((getattr(message, "command", None) or [])[1:]).strip()
        if target and (getattr(target, "photo", None) or getattr(target, "document", None)):
            media = target.photo or target.document
            if getattr(media, "mime_type", "image/unknown").startswith("image/"):
                image_file = await client.download_media(media.file_id, in_memory=True)
                if image_file is None:
                    raise ValueError("Telegram could not download the replied image.")
                payload, files = profile_photo_upload(image_file.getvalue())
            else:
                raise ValueError("Reply to a photo or image document to use it as the bot photo.")
        elif supplied:
            # Accept a bare URL, optionally wrapped in angle brackets.
            image_url = supplied.strip("<>")
            source = await asyncio.to_thread(download_profile_image, image_url)
            payload, files = profile_photo_upload(source)
        else:
            payload, files = profile_photo_upload()
    except (OSError, ValueError) as error:
        return await rich_reply(
            message,
            notice(
                str(error), status="error", title="Bot profile image unavailable"
            ),
        )
    status, result = await bot_api("setMyProfilePhoto", payload, files=files)
    if status and result.get("ok"):
        return await rich_reply(
            message,
            notice(
                "The bundled Videl profile photo was accepted by Telegram. Refresh the bot profile if the old avatar remains cached.",
                status="success",
                title="Bot profile updated",
            ),
        )
    detail = html.escape(str(result.get("description") or "Telegram did not confirm the profile photo change."))
    return await rich_reply(
        message,
        notice(detail, status="error", title="Bot profile was not updated"),
    )


@bot.on_message(filters.command("copy", prefixes=config.COMMAND_PREFIX_LIST))
async def copy_command(_, message):
    """Create a native copy-text button from up to 256 UTF-16 units."""
    from videl.utils.command_ui import usage, notice
    text=" ".join((message.command or [])[1:]).strip()
    if not text and message.reply_to_message:
        text=(message.reply_to_message.text or message.reply_to_message.caption or '').strip()
    if not text or len(text.encode('utf-16-le'))//2>256:
        return await rich_reply(message,usage('/copy Text to copy','Or reply to a text message. Copy payloads allow 1–256 Telegram UTF-16 units.'))
    keyboard=InlineKeyboardMarkup([[button('Copy text',copy_text=CopyTextButton(text=text),style='primary',icon='ios_paperclip')]])
    await rich_reply(message,notice(f'<code>{html.escape(text)}</code>',title='Ready to copy'),reply_markup=keyboard)




@bot.on_message(filters.command("pollstop", prefixes=config.COMMAND_PREFIX_LIST))
async def stop_poll_command(_, message):
    """Admin: stop a replied poll sent by this bot."""
    from videl.utils.command_ui import usage,notice
    if not await is_user_authorized(message):
        return await rich_reply(message,notice('Only group admins or the bot owner can stop polls.',status='error',title='Admin permission required'))
    target=message.reply_to_message
    if not target or not getattr(target,'poll',None):
        return await rich_reply(message,usage('/pollstop','Reply to a poll sent by this bot. Telegram enforces ownership.'))
    await outcome(message,'stopPoll',{'chat_id':message.chat.id,'message_id':target.id},'Poll closed')


def topic_keyboard(chat_id, topic_id):
    return InlineKeyboardMarkup([
        [button("Close topic", callback_data=f"topicctl:close:{chat_id}:{topic_id}", style="danger", icon="ios_close"),
         button("Reopen topic", callback_data=f"topicctl:open:{chat_id}:{topic_id}", style="success", icon="ios_check")],
        [button("Forum commands", callback_data="cmds:tools:0", style="primary", icon="ios_symbols")],
    ])


@bot.on_callback_query(filters.regex(r"^topicctl:(?:close|open):-?[0-9]{1,20}:[0-9]{1,10}$"))
async def topic_control_callback(_, query):
    """Every click is checked against its message context and current admin rights."""
    if not query.message:
        return await query.answer("Open the topic controls inside the group.", show_alert=True)
    _, action, chat, topic = query.data.split(":")
    if int(chat) != query.message.chat.id or int(topic) <= 1:
        return await query.answer("These controls do not belong to this group/topic.", show_alert=True)
    if not await is_user_authorized(query):
        return await query.answer("Current group admin privileges are required.", show_alert=True)
    await query.answer()
    status, data = await bot_api("closeForumTopic" if action == "close" else "reopenForumTopic",
                                {"chat_id": int(chat), "message_thread_id": int(topic)})
    from videl.utils.command_ui import notice
    text = notice("Topic closed." if action == "close" else "Topic reopened.", status="success") if status and data.get("ok") else notice("Telegram did not confirm the change. Check the topic before retrying.", status="warning")
    await rich_edit(query, text, reply_markup=topic_keyboard(int(chat), int(topic)))
