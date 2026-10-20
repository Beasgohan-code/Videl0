"""One concise guide for actual production handlers; no module-count marketing."""
from pyrogram.types import InlineKeyboardMarkup
from videl.utils.bot_ui import button
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc

GUIDES = {
 "music": ("Music", "/play query · /vplay query · /cplay\n/queue · /skip · /pause · /resume · /stop\n/clear removes upcoming tracks; playback continues\n/seek · /replay · /loop · /shuffle · /playlist\n/song · /vsong · /lyrics\nPlayback needs an authorized assistant and voice-chat access."),
 "manage": ("Group management", "/group or /setup — live controls\n/permissions — check actual bot rights\n/ban · /tban @user 1h · /unban · /kick\n/mute · /tmute @user 10m · /unmute\n/warn · /unwarn · /warnings · /clearwarns\n/promote · /demote · /admins\n/pin · /unpin · /purge · /cleanup\n/report — reply to request admin review\n/invite --request — create an approval-only invite"),
 "protect": ("Protection & saved content", "/lock type · /unlock type · /locks\nTypes: links, media, stickers, forward, polls, photos, videos, audio, voice, documents, animations, contacts, locations, games, inline, mentions, bots\n/approve · /unapprove · /approved\n/addblacklist · /rmblacklist · /blacklistmode\n/setwelcome · /welcome on|off · /setcaptcha on|off\n/setrules · /rules\n/save name content · /get name · /notes\n/filter keyword reply · /stopfilter keyword · /filters"),
 "tools": ("Telegram tools", "/poll Question | A | B\n/quiz Question | *Correct | Other\n/modernhelp — advanced poll options\n/pollstop — reply to close a bot poll (admins)\n/copy text · /commands keyword\n/react 👍 — reply; admins only\n/topicnew Title · /topicrename Title · /topicclose · /topicopen\n/afk reason · /remind 10m take a break\n/id · /whois · /ping\nNo paid actions, arbitrary shell execution or AI commands."),
}


def guide(section="home"):
    if section in GUIDES:
        title, body = GUIDES[section]
        text = rich_heading(title, level=2)
        # Individual readable rows instead of one dense wall of command text.
        rows=[]
        notes=[]
        for line in body.split("\n"):
            if line.startswith("/"):
                syntax, _, explanation = line.partition(" — ")
                rows.append((f"<code>{rich_esc(syntax)}</code>", rich_esc(explanation)))
            else:
                notes.append(line)
        text += rich_kv_table(rows)
        if notes:text += rich_note("\n".join(notes))
        category = "manage" if section == "protect" else section
        keyboard = [[button("Browse commands", callback_data=f"cmds:{category}:0", style="primary"),
                     button("Back to guide", callback_data="guide:home")]]
        return text, InlineKeyboardMarkup(keyboard)
    rows = [[button("Music & playlists", callback_data="guide:music", style="primary"),
             button("Group management", callback_data="guide:manage")],
            [button("Protection & notes", callback_data="guide:protect"),
             button("Telegram tools", callback_data="guide:tools")],
            [button("Search command directory", callback_data="cmds:all:0", style="primary")]]
    return (rich_heading("Videl · Command Center", level=2)
        + rich_kv_table([("Music", "Playback, queue, playlists and repeat controls"),
                         ("Groups", "Moderation, permissions and protection"),
                         ("Create", "Rich posts, copy buttons, polls and forums")])
        + rich_note("Choose a workflow. Administrative actions check current privileges; Telegram enforces the bot’s permissions. Search directly with /commands keyword."),
        InlineKeyboardMarkup(rows))
