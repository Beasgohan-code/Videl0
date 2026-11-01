# Videl © 2026 | Beasgohan-code
"""Inline hub for common group settings."""
from __future__ import annotations
import asyncio
import copy
import hashlib
import json
from time import monotonic
from pyrogram import filters
from pyrogram.types import ForceReply, InlineKeyboardMarkup
from videl import LOGGER, bot
from videl.utils.interactive_settings import Step, engine
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit
from videl.utils.moderation import LOCK_TYPES

_TABS = {"home", "music", "welcome", "safety", "moderation", "retention", "blocklist", "presets", "sessions", "automations", "commands", "more"}
_LOCK_KEYS = {f"lock_{kind}" for kind in LOCK_TYPES} | {"lock_forwards"}
_PROMPTS: dict[tuple[int, int], tuple[int, str, float]] = {}
_TOGGLES = {
 "music": (("Member requests", "music_requests_enabled", True), ("Admin approval", "music_approval_required", False), ("Shuffle new requests", "music_shuffle_enabled", False)),
 "welcome": (("Welcome messages", "welcome_enabled", True), ("Goodbye messages", "goodbye_enabled", False), ("New-member verification", "captcha_enabled", False)),
 "safety": (("Anti-flood", "antispam", False), ("Gemini Guardian assistance", "gemini_guardian_enabled", False)),
}
_RESET_DEFAULTS = {
    "music": {"music_requests_enabled": True, "music_approval_required": False,
              "music_shuffle_enabled": False, "music_dj_session": {},
              "music_track_blocklist": [], "music_session_presets": []},
    "welcome": {"welcome_enabled": True, "goodbye_enabled": False, "captcha_enabled": False},
    "safety": {"antispam": False, "antispam_limit": 7, "antispam_window": 8,
               "gemini_guardian_enabled": False, **{key: False for key in _LOCK_KEYS},
               "raid_mode": {"enabled": False, "window_seconds": 30,
                             "join_threshold": 8, "message_threshold": 20,
                             "duration_minutes": 15}},
    "moderation": {"warn_threshold": 3},
    "blocklist": {"music_track_blocklist": []},
    "presets": {"music_session_presets": []},
}


def _revision(chat_id):
    from videl.utils.settings_store import revision
    return revision(chat_id)


def _tag_keyboard(markup, chat_id):
    """Bind every settings action button to the state revision it displayed."""
    revision = _revision(chat_id)
    rows = []
    for row in markup.inline_keyboard:
        tagged = []
        for item in row:
            button_copy = copy.copy(item)
            data = getattr(button_copy, "callback_data", None)
            if data:
                button_copy.callback_data = f"{data}:v{revision}"
            tagged.append(button_copy)
        rows.append(tagged)
    return InlineKeyboardMarkup(rows)


def _reset_values(chat_id, category):
    defaults = _RESET_DEFAULTS[category]
    current = base.get_settings(chat_id)
    return {key: current.get(key, "__VIDEL_SETTING_UNSET__") for key in defaults}, dict(defaults)


def _reset_signature(chat_id, category):
    current, _ = _reset_values(chat_id, category)
    raw = json.dumps(current, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]

def _switch(chat_id, key, label, default=False):
    enabled=bool(base.get_setting(chat_id,key,default))
    return [button(label),button("On",callback_data=f"settings:{chat_id}:{key}:on",style="success" if enabled else None),button("Off",callback_data=f"settings:{chat_id}:{key}:off",style="danger" if not enabled else None)]

def _nav(chat_id, section="home"):
    """Compact navigation: the overview is a hub; detail pages keep two exits."""
    if section == "home":
        return [
            [button("🎵 Music", callback_data=f"settings:{chat_id}:tab:music", style="primary"),
             button("👋 Welcome", callback_data=f"settings:{chat_id}:tab:welcome")],
            [button("🛡 Protection", callback_data=f"settings:{chat_id}:tab:safety"),
             button("⚖ Moderation", callback_data=f"settings:{chat_id}:tab:moderation")],
            [button("⚙ More settings", callback_data=f"settings:{chat_id}:tab:more")],
        ]
    if section == "more":
        return [
            [button("📌 Music blocklist", callback_data=f"settings:{chat_id}:tab:blocklist"),
             button("🎚 Queue presets", callback_data=f"settings:{chat_id}:tab:presets")],
            [button("🗓 Sessions", callback_data=f"settings:{chat_id}:tab:sessions"),
             button("🧹 Retention", callback_data=f"settings:{chat_id}:tab:retention")],
            [button("🤖 Automations", callback_data=f"settings:{chat_id}:tab:automations"),
             button("⌘ Commands", callback_data=f"settings:{chat_id}:tab:commands")],
            [button("← Overview", callback_data=f"settings:{chat_id}:tab:home")],
        ]
    return [[button("← Overview", callback_data=f"settings:{chat_id}:tab:home"),
             button("More settings", callback_data=f"settings:{chat_id}:tab:more")]]

def _reset_confirmation(chat_id, category):
    current, defaults = _reset_values(chat_id, category)
    rows=[]
    for key, default in defaults.items():
        old=current.get(key, "__VIDEL_SETTING_UNSET__")
        rows.append((base.escape(key), f"{base.escape(str(old)[:60])} → {base.escape(str(default)[:60])}"))
    token=_reset_signature(chat_id,category)
    text=(heading(f"Preview {base.escape(category)} reset",3)
          +body("Only the listed settings will change. Custom welcome text, group rules, command switches, queue contents, pending sessions and other categories are preserved.")
          +table(rows)
          +body("Confirm only if this preview is correct. The reset is audited and will be refused if settings change before confirmation."))
    keyboard=InlineKeyboardMarkup([
        [button("Confirm reset",callback_data=f"settings:{chat_id}:resetconfirm:{category}:{token}",style="danger")],
        [button("Cancel",callback_data=f"settings:{chat_id}:tab:{category}")],
    ])
    return Screen(text,_tag_keyboard(keyboard,chat_id))


def _screen(chat_id, section="home", *, query="", category="all", page=0, connected_dm=False, bot_can_delete_messages=None):
    markup=_nav(chat_id,section)
    if section=="home":
        fields=(("Member music requests","music_requests_enabled",True),("Music request approval","music_approval_required",False),("Shuffle new requests","music_shuffle_enabled",False),("Welcome messages","welcome_enabled",True),("Goodbye messages","goodbye_enabled",False),("New-member verification","captcha_enabled",False),("Anti-flood","antispam",False),("Gemini Guardian assistance","gemini_guardian_enabled",False))
        text=heading("Group settings",3)+body("Choose a section to view and manage this group. Current Telegram group admins are checked before changes.")+table([(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields])+body("For personal DM language, reminders and optional private updates, use <code>/preferences</code> in your private chat. Those settings do not change this group.")
    elif section in _TOGGLES:
        title={"music":"Music","welcome":"Welcome & onboarding","safety":"Protection"}[section]
        description={"music":"Members can request tracks when enabled. Approval sends new requests to admin review; use /requests to review.","welcome":"Control welcome, goodbye and verification flows. Edit content with /setwelcome, /setgoodbye, /setrules and /setfaq.","safety":"Configure content locks and raid mode; anti-flood thresholds are editable here or with /antispam. Enabling anti-flood requires the bot to have Delete Messages permission. Gemini Guardian is off by default. When enabled, /faqassist sends the question and selected FAQ/rules/text notes; admin /safetycheck sends minimized replied-to text (URL hosts only); /guardiansummary sends aggregate counts. These are sent to Google Gemini; no result takes action."}[section]
        fields=_TOGGLES[section]
        rows=[(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields]
        if section=="welcome":
            from videl.plugins.welcome import DEFAULT_WELCOME
            from videl.utils.welcome_checklist import safe_stored
            current=base.get_setting(chat_id,"welcome_message",DEFAULT_WELCOME)
            goodbye=base.get_setting(chat_id,"goodbye_message","Goodbye {name}.")
            rules=base.get_setting(chat_id,"rules",None)
            media=base.get_setting(chat_id,"welcome_media",None)
            links=safe_stored(base.get_setting(chat_id,"welcome_checklist",[]))
            rows.append(("Welcome text",base.escape(str(current)[:180])))
            rows.append(("Goodbye text",base.escape(str(goodbye)[:180])))
            rows.append(("Group rules",base.escape(str(rules)[:180]) if rules else "Not set"))
            rows.append(("Welcome media",base.escape(media.get("type","Unavailable")) if isinstance(media,dict) else "Not set"))
            rows.append(("Welcome buttons",base.escape(" · ".join(item["label"] for item in links)) if links else "No checklist links"))
        if section=="safety":
            from videl.plugins.locks import antispam_config
            flood_limit, flood_window = antispam_config(chat_id)
            rows.append(("Anti-flood threshold", f"{flood_limit} messages / {flood_window}s · set with /antispam"))
            if bot_can_delete_messages is False:
                text_hint = "The bot currently lacks Delete Messages permission. Enabling content locks is unavailable; existing locks may not be enforceable until rights are restored."
            else:
                text_hint = "Enabling content locks requires bot Delete Messages permission, rechecked at the time of change."
        if section=="music":
            dj=base.get_setting(chat_id,"music_dj_session",{}); rows.append(("Temporary DJ",str(dj.get("user_id")) if isinstance(dj,dict) and dj.get("user_id") else "None · use /dj"))
        text=heading(title,3)+body(description)+table(rows)
        if section == "safety": text += body(text_hint)
        for label,key,default in fields:
            if section=="safety" and key=="antispam":
                markup.append([button("Configure anti-flood…",callback_data=f"settings:{chat_id}:antispam:edit",style="primary")])
            elif section=="welcome" and key=="captcha_enabled":
                markup.append([button("Configure join verification…",callback_data=f"settings:{chat_id}:captcha:edit",style="primary")])
            else:
                markup.append(_switch(chat_id,key,label,default))
        if section=="welcome":
            markup.append([button("Edit welcome text…",callback_data=f"settings:{chat_id}:welcome_text:edit",style="primary")])
            markup.append([button("Edit goodbye text…",callback_data=f"settings:{chat_id}:goodbye_text:edit")])
            markup.append([button("Edit group rules…",callback_data=f"settings:{chat_id}:rules_text:edit")])
            if base.get_setting(chat_id,"rules",None):
                markup.append([button("Clear group rules…",callback_data=f"settings:{chat_id}:rules_text:clear",style="danger")])
            markup.append([button("Set or replace welcome media…",callback_data=f"settings:{chat_id}:welcome_media:edit")])
            markup.append([button("Edit checklist buttons…",callback_data=f"settings:{chat_id}:welcome_buttons:edit")])
            if isinstance(base.get_setting(chat_id,"welcome_media",None),dict):
                markup.append([button("Remove welcome media…",callback_data=f"settings:{chat_id}:welcome_media:clear",style="danger")])
        if section=="safety":
            for kind in LOCK_TYPES:
                key="lock_forwards" if kind=="forward" else f"lock_{kind}"
                if bot_can_delete_messages is False:
                    enabled = bool(base.get_setting(chat_id, key, False))
                    markup.append([button(f"Lock {kind}"),
                        button("On" if enabled else "On · needs bot right", style="success" if enabled else "danger"),
                        button("Off", callback_data=f"settings:{chat_id}:{key}:off", style="danger" if not enabled else None)])
                else:
                    markup.append(_switch(chat_id,key,f"Lock {kind}"))
            raid=base.get_setting(chat_id,"raid_mode",{}); enabled=bool(raid.get("enabled")) if isinstance(raid,dict) else False
            markup.append([button("Raid mode"),button("On",callback_data=f"settings:{chat_id}:raid:on",style="success" if enabled else None),button("Off",callback_data=f"settings:{chat_id}:raid:off",style="danger" if not enabled else None)])
            if connected_dm:
                markup.append([button("Approved members…", callback_data=f"settings:{chat_id}:approved:list", style="primary")])
    elif section=="more":
        text=heading("More group settings",3)+body("Additional music, automation and command controls for this group. Use Overview to return to the main settings hub.")
    elif section=="moderation":
        threshold = _saved_warn_threshold(chat_id)
        display = "Unavailable" if threshold is None else base.escape(str(threshold))
        try:
            from videl.utils.db import get_automation, get_db
            if get_db() is None: raise RuntimeError("automation storage unavailable")
            escalation = get_automation(chat_id)["escalation"]
        except Exception:
            escalation = None
        if escalation is None:
            escalation_display = "Unavailable"
        else:
            ladder = list(escalation.get("ladder") or [])
            action = " → ".join(ladder) if ladder else str(escalation.get("action", "ban"))
            escalation_display = f"{'On' if escalation.get('enabled') else 'Off'} · {action} · decay {int(escalation.get('decay_days') or 0)} days"
        text=heading("Moderation",3)+body("Choose the active-warning threshold and shared warning-escalation defaults.")+table([("Warning threshold",display),("Warning escalation",escalation_display)])
        markup.append([button("Edit warning threshold…",callback_data=f"settings:{chat_id}:warn_threshold:edit",style="primary")])
        markup.append([button("Edit warning escalation…",callback_data=f"settings:{chat_id}:warn_escalation:edit",style="primary")])
    elif section=="retention":
        from videl.utils.retention import ALLOWED_DAYS,CATEGORIES,normalize
        policy=normalize(base.get_setting(chat_id,"data_retention",{})); rows=[]
        labels={"case_notes":"Case notes","resolved_reports":"Resolved reports","resolved_join_requests":"Resolved join requests","resolved_appeals":"Resolved appeals","resolved_escalations":"Resolved escalations"}
        for cat in CATEGORIES:
            days=policy[cat]; rows.append((labels.get(cat,cat),f"{days} days" if days else "Keep indefinitely"))
            markup.append([button(str(day),callback_data=f"settings:{chat_id}:retention:{cat}:{day}",style="success" if day==days else None) for day in ALLOWED_DAYS]+[button("Keep",callback_data=f"settings:{chat_id}:retention:{cat}:off",style="success" if days is None else None)])
        text=heading("History retention",3)+table(rows)+body("Only resolved history is eligible. Pending cases, warning state and audit records are retained. Preview with /retention preview.")
    elif section=="blocklist":
        from videl.utils.track_blocklist import normalize
        items=normalize(base.get_setting(chat_id,"music_track_blocklist",[]))
        text=heading("Music track & artist blocklist",3)+body("Entries are matched case-insensitively against track titles and available artist metadata before a request enters the queue. Up to 50 entries, 100 characters each.")+table([(f"{i}. {item['kind'].title()}",item["value"]) for i,item in enumerate(items,1)] if items else [("Blocked entries","None")])
        text += body("Changes are staged and previewed before saving." if connected_dm else "Add prompts and replies are visible in the group.")
        markup.append([button("＋ Block track",callback_data=f"settings:{chat_id}:blocklist:add:track"),button("＋ Block artist",callback_data=f"settings:{chat_id}:blocklist:add:artist")])
        for i,item in enumerate(items,1): markup.append([button(f"Remove {i}: {item['value'][:32]}",callback_data=f"settings:{chat_id}:blocklist:remove:{i}",style="danger")])
    elif section=="presets":
        from videl.utils.music_presets import normalize as normalize_presets
        presets=normalize_presets(base.get_setting(chat_id,"music_session_presets",[]))
        text=heading("Queue session presets",3)+body("Save named snapshots of repeat, shuffle, member-request and approval settings. Applying a preset updates those settings and shuffles the current upcoming queue when shuffle is enabled.")
        if connected_dm: text += body("Creation is staged and previewed before saving.")
        rows=[]
        for i,item in enumerate(presets,1):
            if not isinstance(item,dict): continue
            rows.append((str(i),str(item.get("name","Preset"))[:32]+f" · repeat {item.get('loop','off')} · shuffle {'on' if item.get('shuffle') else 'off'}"))
            markup.append([button(f"Apply {i}",callback_data=f"settings:{chat_id}:preset:apply:{i}",style="success"),button(f"Delete {i}",callback_data=f"settings:{chat_id}:preset:delete:{i}",style="danger")])
        if not rows: rows=[("Presets","None saved")]
        text+=table(rows)
        markup.append([button("Save current settings",callback_data=f"settings:{chat_id}:preset:save")])
    elif section=="sessions":
        from videl.utils.db import get_db
        from videl.utils.listening_sessions import pending
        items=pending(get_db(),chat_id)
        rows=[]
        for item in items:
            due=item.get("due_at")
            stamp=due.strftime("%Y-%m-%d %H:%M UTC") if hasattr(due,"strftime") else "Time unavailable"
            rows.append((stamp,str(item.get("title","Session"))))
            markup.append([button("Cancel session",callback_data=f"settings:{chat_id}:session:cancel:{item['_id']}",style="danger")])
        text=heading("Scheduled listening sessions",3)+body("Schedule a one-time group announcement up to 30 days ahead. When it fires, member music requests are opened automatically. Times are UTC.")+table(rows if rows else [("Upcoming sessions","None")])
        markup.append([button("＋ Schedule a session",callback_data=f"settings:{chat_id}:session:schedule")])
    elif section=="automations":
        store = base.collection("mgmt_filters")
        try:
            if store is None:
                raise RuntimeError("database unavailable")
            filter_count = store.count_documents({"chat_id": int(chat_id)})
        except Exception:
            filter_count = None
        count_label = "Unavailable" if filter_count is None else str(filter_count)
        text = (heading("Automations", 3)
                + body("Group keyword filters send plain-text answers when matching non-command messages arrive. Matching remains case-insensitive; the longest matching keyword wins.")
                + table([("Automatic filters", count_label)])
                + body("Create or edit text-only filters. No regex or media-response behavior is added."))
        if connected_dm:
            text += body("Add is available here. Review or remove existing filters from the group with <code>/filters</code>.")
            markup.append([button("＋ Add Filter", callback_data=f"settings:{chat_id}:filters:add", style="primary")])
        else:
            markup.append([button("＋ Add Filter", callback_data=f"settings:{chat_id}:filters:add", style="primary"),
                           button("Manage Filters", callback_data=f"settings:{chat_id}:filters:manage")])
    elif section=="commands":
        from videl.utils.db import get_db
        from videl.utils.command_catalog import commands as registered_commands
        try:
            db=get_db()
            if db is None: raise RuntimeError("MongoDB unavailable")
            disabled={str(item.get("cmd","")).casefold() for item in db["disabled_cmds"].find({"chat":chat_id},{"_id":0,"cmd":1})}
            entries=[entry for entry in registered_commands() if not entry.get("owner") and entry.get("context")!="private"
                     and (category=="all" or entry.get("category")==category)
                     and (not query or query.casefold() in entry["name"] or query.casefold() in entry["summary"].casefold())]
        except Exception:
            text=heading("Command manager unavailable",3)+body("Videl could not verify the registered commands or read this group’s command switches. No status is guessed; try Refresh later.")
            entries=[]; disabled=set(); unavailable=True
        else: unavailable=False
        if not unavailable:
            categories=("all","manage","music","tools")
            title="Command manager"+(f" · {category}" if category!="all" else "")
            if query: title+=f" · search: {query[:40]}"
            text=heading(title,3)+body("Search with <code>/settings commands word</code> or filter by category. Core recovery commands are protected from new changes here. Changes apply only in this group.")
            markup.append([button(name.title(),callback_data=f"settings:{chat_id}:commands:{name}:0",style="primary" if name==category else None) for name in categories])
            page_size=6; pages=max(1,(len(entries)+page_size-1)//page_size); page=max(0,min(int(page),pages-1))
            current=entries[page*page_size:(page+1)*page_size]
            rows=[]
            protected={"start","help","commands","id","ping","settings","permissions"}
            for entry in current:
                name=entry["name"]; off=name in disabled; state="OFF" if off else "ON"
                rows.append((f"/{name} · {state}",entry["summary"][:72]))
                if name not in protected:
                    markup.append([button(f"/{name}: {'Enable' if off else 'Disable'}",callback_data=f"settings:{chat_id}:cmd:{name}:{'on' if off else 'off'}",style="success" if off else "danger")])
                else:
                    markup.append([button(f"/{name} · protected",callback_data=f"settings:{chat_id}:commands:{category}:{page}")])
            text+=table(rows if rows else [("Commands","No matching group commands")])
            if pages>1:
                controls=[]
                if page>0: controls.append(button("← Previous",callback_data=f"settings:{chat_id}:commands:{category}:{page-1}"))
                controls.append(button(f"Page {page+1}/{pages}"))
                if page+1<pages: controls.append(button("Next →",callback_data=f"settings:{chat_id}:commands:{category}:{page+1}"))
                markup.append(controls)
            text+=body(f"Showing {len(current)} of {len(entries)} commands. Owner-only and private-only commands are excluded.")
    else: raise ValueError("Unknown settings section")
    if section in _RESET_DEFAULTS:
        markup.append([button("Reset this section…", callback_data=f"settings:{chat_id}:reset:{section}", style="danger")])
    markup.append([button("Refresh",callback_data=f"settings:{chat_id}:refresh")])
    if connected_dm:
        safe_rows = []
        for row in markup:
            safe = []
            for item in row:
                data = getattr(item, "callback_data", None)
                if not data:
                    safe.append(item)
                    continue
                raw = data.rsplit(":v", 1)[0]
                prefix = f"settings:{int(chat_id)}:"
                if not raw.startswith(prefix):
                    continue
                action = raw[len(prefix):]
                allowed = (action.startswith("tab:") and action.split(":", 1)[1] in _TABS
                           or action == "refresh"
                           or action.startswith("commands:")
                           or action.startswith("cmd:")
                           or action.startswith("reset:")
                           or action.startswith("resetconfirm:")
                           or action.startswith("warn_threshold:")
                           or action.startswith("warn_escalation:")
                           or action == "preset:save"
                           or action.startswith("preset:apply:")
                           or action.startswith("preset:delete:")
                           or action.startswith("approved:")
                           or action.startswith("filters:add")
                           or action == "session:schedule"
                           or action.startswith("session:cancel:")
                           or action.startswith("blocklist:")
                           or action in {"antispam:edit", "captcha:edit", "welcome_text:edit",
                                         "goodbye_text:edit", "rules_text:edit", "rules_text:clear",
                                         "welcome_media:edit", "welcome_media:clear",
                                         "welcome_buttons:edit"})
                if action.startswith(("lock_", "music_requests_enabled:", "music_approval_required:",
                                      "music_shuffle_enabled:", "welcome_enabled:",
                                      "goodbye_enabled:", "gemini_guardian_enabled:", "raid:")):
                    allowed = True
                if allowed:
                    safe.append(item)
            if safe:
                safe_rows.append(safe)
        markup = safe_rows
        text += body("Connected-group view: only migrated editors are available here; other prompt and media workflows remain hidden. This panel rechecks your saved connection and current admin status before each action.")
    return Screen(text,_tag_keyboard(InlineKeyboardMarkup(markup),chat_id))

async def settings(ctx):
    message = ctx.message
    connected_dm = getattr(message, "target_chat_id", None)
    if base.chat_kind(message) not in {"group","supergroup"}:
        raise CommandError("Open <code>/settings</code> in the group, or connect a group and use this command in your private chat.")
    chat_id = int(connected_dm or message.chat.id)
    arguments=str(getattr(ctx.command,"arguments","") or "").strip()
    if arguments.casefold().startswith("commands"):
        query=arguments[len("commands"):].strip()[:40]
        return _screen(chat_id,"commands",query=query,connected_dm=bool(connected_dm))
    return _screen(chat_id,connected_dm=bool(connected_dm))

_WARN_THRESHOLD_VALUES = tuple(str(value) for value in range(1, 11))


def _saved_warn_threshold(chat_id):
    collection = base.collection(base.SETTINGS_COLLECTION)
    if collection is None:
        return None
    try:
        document = collection.find_one({"chat_id": int(chat_id)})
    except Exception:
        return None
    if not document:
        return 3
    value = document.get("warn_threshold", 3)
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)[:32]


_WARN_CALLBACK = r"^warn_threshold_edit:[A-Za-z0-9_-]{1,24}:(?:pick:(?:[1-9]|10)|edit|save|cancel|back)$"


def _warn_threshold_selection(session):
    current = session.values.get("saved_value")
    rows = []
    values = _WARN_THRESHOLD_VALUES
    for start in (0, 5):
        rows.append([button(f"{value} warnings" + (" · current" if str(current) == value else ""),
                            callback_data=f"warn_threshold_edit:{session.token}:pick:{value}",
                            style="success" if str(current) == value else None)
                     for value in values[start:start + 5]])
    rows.append([button("Cancel", callback_data=f"warn_threshold_edit:{session.token}:cancel", style="danger"),
                 button("Back", callback_data=f"warn_threshold_edit:{session.token}:back")])
    return InlineKeyboardMarkup(rows)


def _warn_threshold_preview(session):
    value = int(session.values["warn_threshold"])
    previous = session.values.get("saved_value", "Unknown")
    previous_display = "Unavailable" if previous is None else base.escape(str(previous))
    text = (heading("Warning threshold preview", 3)
            + table([("Currently saved", previous_display), ("New threshold", f"{value} active warnings")])
            + body("No settings have changed yet. Saving updates only the warning threshold; the existing escalation behavior is unchanged."))
    keyboard = InlineKeyboardMarkup([
        [button("Save", callback_data=f"warn_threshold_edit:{session.token}:save", style="primary"),
         button("Edit Again", callback_data=f"warn_threshold_edit:{session.token}:edit")],
        [button("Cancel", callback_data=f"warn_threshold_edit:{session.token}:cancel", style="danger"),
         button("Back", callback_data=f"warn_threshold_edit:{session.token}:back")],
    ])
    return Screen(text, keyboard)


def _warn_threshold_selection_screen(session):
    saved = session.values.get("saved_value", "Unknown")
    current = "Unavailable" if saved is None else base.escape(str(saved))
    text = (heading("Warning threshold", 3)
            + body(f"Currently saved: <b>{current}</b> active warnings.")
            + body("Choose a value from 1 to 10. You will review a preview before anything is saved."))
    return Screen(text, _warn_threshold_selection(session))


async def _start_warn_threshold_editor(message, chat_id: int, actor_id: int, revision: int, initial=None,
                                       *, interaction_chat_id: int | None = None):
    interaction_chat_id = int(interaction_chat_id if interaction_chat_id is not None else chat_id)
    current = _saved_warn_threshold(chat_id)
    session = await engine.begin(
        chat_id=interaction_chat_id, actor_id=actor_id, target_chat_id=chat_id,
        workflow="warn_threshold", revision=revision,
        steps=(Step("warn_threshold", "Warning threshold", kind="selection",
                    choices=_WARN_THRESHOLD_VALUES),), timeout_seconds=600,
    )
    session.values["saved_value"] = current
    try:
        if initial is None:
            screen = _warn_threshold_selection_screen(session)
        else:
            await engine.bind_prompt(session.token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=int(message.id))
            captured = await engine.capture(session.token, chat_id=interaction_chat_id, actor_id=actor_id,
                                            target_chat_id=chat_id, reply_to_message_id=int(message.id),
                                            value=str(initial))
            if captured.status != "preview":
                raise ValueError("Invalid warning threshold selection.")
            screen = _warn_threshold_preview(captured.session)
        await rich_edit(message, screen.html, reply_markup=screen.keyboard)
        await engine.bind_prompt(session.token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=int(message.id))
    except Exception:
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise RuntimeError("Could not display the warning threshold editor; nothing changed.") from None
    return session


_ESCALATION_LADDERS = {
    "single": [], "mute-kick-ban": ["mute", "kick", "ban"],
    "mute-ban": ["mute", "ban"], "kick-ban": ["kick", "ban"], "mute-kick": ["mute", "kick"],
}
_ESCALATION_CALLBACK = r"^warn_escalation_edit:[A-Za-z0-9_-]{1,24}:(?:save|edit|cancel|back)$"
_ESCALATION_STEPS = (
    Step("enabled", "Enable automatic warning escalation? Reply on or off.", kind="selection", choices=("on", "off")),
    Step("ladder_key", "Choose the sequence: single, mute-kick-ban, mute-ban, kick-ban, or mute-kick.",
         kind="selection", choices=tuple(_ESCALATION_LADDERS)),
    Step("action", "When using a single step, choose none, mute, kick, or ban.", kind="selection",
         choices=("none", "mute", "kick", "ban")),
    Step("mute_hours", "Mute duration in whole hours (1–168).", kind="number", minimum=1, maximum=168),
    Step("decay_days", "Warning decay in days (0–365; 0 means warnings do not expire).", kind="number", minimum=0, maximum=365),
    Step("review_severe", "Require an admin to review kick/ban steps? Reply on or off.",
         kind="selection", choices=("on", "off")),
)


def _escalation_config(values):
    return {
        "enabled": values["enabled"] == "on",
        "ladder": list(_ESCALATION_LADDERS[values["ladder_key"]]),
        "action": values["action"],
        "mute_hours": int(values["mute_hours"]),
        "decay_days": int(values["decay_days"]),
        "review_severe": values["review_severe"] == "on",
    }


def _escalation_preview(session):
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    before = session.values["before"]
    after = _escalation_config(session.values)
    def describe(config):
        ladder = list(config.get("ladder") or [])
        sequence = " → ".join(ladder) if ladder else f"single action: {config.get('action', 'ban')}"
        return [
            ("Enabled", "On" if config.get("enabled") else "Off"),
            ("Sequence", sequence),
            ("Single-action fallback", str(config.get("action", "ban"))),
            ("Mute duration", f"{int(config.get('mute_hours') or 6)} hours"),
            ("Warning decay", f"{int(config.get('decay_days') or 0)} days"),
            ("Severe-action review", "Required" if config.get("review_severe") else "Not required"),
        ]
    text = (heading("Warning escalation preview", 3)
            + body(f"Target group: <code>{session.target_chat_id}</code>. This updates only the existing automation.escalation settings; warning threshold and other automations are unchanged.")
            + table([("Setting", "Currently saved"), *describe(before)])
            + table([("Setting", "Proposed value"), *describe(after)])
            + body("No settings have changed yet. Confirm to save the shared escalation policy."))
    keyboard = InlineKeyboardMarkup([
        [button("Confirm", callback_data=f"warn_escalation_edit:{session.token}:save", style="primary"),
         button("Edit", callback_data=f"warn_escalation_edit:{session.token}:edit")],
        [button("Cancel", callback_data=f"warn_escalation_edit:{session.token}:cancel", style="danger"),
         button("Back", callback_data=f"warn_escalation_edit:{session.token}:back")],
    ])
    return text, keyboard


async def _send_escalation_prompt(client, session):
    from pyrogram.types import ForceReply
    step = session.current_step
    if step is None: raise RuntimeError("Warning escalation input is complete.")
    prompt = await client.send_message(session.chat_id, step.prompt, reply_markup=ForceReply(selective=True))
    await engine.bind_prompt(session.token, chat_id=session.chat_id, actor_id=session.actor_id, message_id=prompt.id)


async def _start_escalation_editor(client, interaction_chat_id: int, actor_id: int, target_chat_id: int,
                                   revision: int, *, connected_dm: bool):
    from videl.utils.db import get_automation, get_db
    if get_db() is None:
        raise RuntimeError("Warning-escalation settings are unavailable because storage is offline.")
    current = get_automation(target_chat_id)["escalation"]
    try:
        session = await engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
            target_chat_id=target_chat_id, workflow="warning_escalation", revision=revision,
            steps=_ESCALATION_STEPS, timeout_seconds=600)
        session.values["before"] = {
            "enabled": bool(current.get("enabled")), "action": current.get("action", "ban"),
            "mute_hours": int(current.get("mute_hours") or 6), "decay_days": int(current.get("decay_days") or 0),
            "ladder": list(current.get("ladder") or []), "review_severe": bool(current.get("review_severe")),
        }
        await _send_escalation_prompt(client, session)
        return session
    except Exception:
        active = await engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id, target_chat_id=target_chat_id)
        if active is not None and active.workflow == "warning_escalation":
            await engine.cancel(active.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


async def _bot_can_restrict_members(client, chat_id: int) -> bool:
    try:
        member = await client.get_chat_member(int(chat_id), int(client.me.id))
        status = str(getattr(member.status, "value", member.status)).casefold()
        return status in {"owner", "creator"} or (status == "administrator"
            and bool(getattr(member, "can_restrict_members", False)))
    except Exception:
        return False


async def connected_escalation_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None: return
    reply = getattr(message, "reply_to_message", None)
    prompt_id = getattr(reply, "id", None)
    if prompt_id is None: return
    session = await engine.for_prompt(chat_id=int(message.chat.id), actor_id=int(actor.id), message_id=int(prompt_id))
    if session is None or session.workflow != "warning_escalation": return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await engine.cancel(session.token, chat_id=session.chat_id, actor_id=session.actor_id)
        return await client.send_message(session.chat_id, "Warning-escalation editor cancelled; nothing changed.")
    captured = await engine.capture(session.token, chat_id=session.chat_id, actor_id=session.actor_id,
        target_chat_id=session.target_chat_id, reply_to_message_id=getattr(reply, "id", None), value=text.casefold())
    if captured.status == "invalid":
        await client.send_message(session.chat_id, captured.error or "That response is not valid for this setting.")
        return await _send_escalation_prompt(client, captured.session)
    if captured.status == "accepted":
        return await _send_escalation_prompt(client, captured.session)
    if captured.status != "preview": return
    rendered, keyboard = _escalation_preview(captured.session)
    preview = await client.send_message(session.chat_id, rendered, reply_markup=keyboard)
    await engine.bind_prompt(session.token, chat_id=session.chat_id, actor_id=session.actor_id, message_id=preview.id)


async def connected_escalation_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None:
        return await query.answer("This warning-escalation action is unavailable.", show_alert=True)
    kind = base.chat_kind(message)
    if kind not in {"private", "group", "supergroup"} or (kind == "private" and int(message.chat.id) != int(actor.id)):
        return await query.answer("This warning-escalation action is unavailable.", show_alert=True)
    try:
        _, token, action = str(query.data).split(":", 2)
    except ValueError:
        return await query.answer("Malformed warning-escalation callback.", show_alert=True)
    session = await engine.get(token, chat_id=int(message.chat.id), actor_id=int(actor.id))
    if session is None or session.workflow != "warning_escalation":
        return await query.answer("This warning-escalation preview expired or is not yours.", show_alert=True)

    async def authorize(target_id, user_id):
        if base.chat_kind(message) == "private":
            from videl.app.connections import connected_target
            _, error = await connected_target(client, user_id, expected_chat_id=target_id)
            return not error
        try:
            member = await client.get_chat_member(target_id, user_id)
            status = str(getattr(member.status, "value", member.status)).casefold()
            return status in {"owner", "creator", "administrator"}
        except Exception:
            return False

    if action.endswith("cancel"):
        await engine.cancel(token, chat_id=session.chat_id, actor_id=session.actor_id)
        await query.answer("Cancelled; escalation settings were unchanged.")
        return await rich_edit(message, "Warning-escalation changes cancelled. Nothing changed.", reply_markup=None)
    if action.endswith("edit") or action.endswith("back"):
        if not await authorize(session.target_chat_id, session.actor_id):
            return await query.answer("Connection or current admin permission changed. Reopen settings to continue.", show_alert=True)
        await engine.cancel(token, chat_id=session.chat_id, actor_id=session.actor_id)
        await query.answer("Restart the editor to change the draft.")
        screen = await _settings_screen(client, session.target_chat_id, "moderation",
            connected_dm=(base.chat_kind(message) == "private"))
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)

    result_flags = {"conflict": False}
    async def save(snapshot):
        from videl.utils import settings_store
        from videl.utils.db import get_automation, get_db, set_automation
        from videl.utils.automation import normalize_escalation
        db = get_db()
        if db is None: return False
        config = normalize_escalation(_escalation_config(snapshot.values))
        actions = list(config["ladder"]) or ([config["action"]] if config["action"] != "none" else [])
        if config["enabled"] and actions and not await _bot_can_restrict_members(client, snapshot.target_chat_id):
            return False
        try:
            set_automation(snapshot.target_chat_id, escalation=config, expected=snapshot.revision)
        except settings_store.SettingsConflict:
            result_flags["conflict"] = True
            return False
        stored = get_automation(snapshot.target_chat_id)["escalation"]
        return normalize_escalation(stored) == config

    outcome, _ = await engine.commit(token, chat_id=session.chat_id, actor_id=session.actor_id,
        target_chat_id=session.target_chat_id, message_id=message.id, authorize=authorize, save=save)
    if outcome == "saved":
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot, session.target_chat_id, "settings",
                action="warning_escalation_updated", detail="warning escalation settings updated", actor=session.actor_id)
        except Exception: pass
        await query.answer("Warning-escalation settings saved.")
        screen = await _settings_screen(client, session.target_chat_id, "moderation",
            connected_dm=(base.chat_kind(message) == "private"))
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)
    messages = {
        "permission_denied": "Connection or current admin permission changed. No settings were saved.",
        "save_failed": ("Settings changed since the preview; reopen and review current values." if result_flags["conflict"]
                        else "Storage or required bot Restrict Members permission is unavailable. No success was reported."),
        "expired": "This warning-escalation preview expired. No settings were saved.",
        "stale": "This preview is stale or already being confirmed.",
        "unauthorized": "This action does not belong to this admin or group.",
    }
    return await query.answer(messages.get(outcome, "Could not save warning escalation."), show_alert=True)


@bot.on_callback_query(filters.regex(_ESCALATION_CALLBACK))
async def _connected_escalation_callback(client, query):
    return await connected_escalation_callback(client, query)


@bot.on_message((filters.private | filters.group) & filters.incoming, group=4)
async def _connected_escalation_reply(client, message):
    return await connected_escalation_reply(client, message)


async def _settings_screen(client, chat_id, section="home", *, query="", category="all", page=0, connected_dm=False):
    can_delete = await _bot_can_delete_messages(client, int(chat_id)) if section == "safety" else None
    return _screen(chat_id, section, query=query, category=category, page=page,
                   connected_dm=connected_dm, bot_can_delete_messages=can_delete)


_PATTERN=r"^settings:-?[0-9]{1,20}:(?:tab:(?:home|music|welcome|safety|moderation|retention|blocklist|presets|sessions|automations|commands|more)|commands:(?:all|manage|music|tools):[0-9]{1,3}|filters:(?:add|manage)|cmd:[a-z][a-z0-9_]{0,31}:(?:on|off)|(?:music_requests_enabled|music_approval_required|music_shuffle_enabled|welcome_enabled|goodbye_enabled|captcha_enabled|antispam|gemini_guardian_enabled|lock_[a-z_]+):(?:on|off)|antispam:edit|captcha:edit|welcome_text:edit|goodbye_text:edit|rules_text:(?:edit|clear)|welcome_media:(?:edit|clear)|welcome_buttons:edit|raid:(?:on|off)|warn_threshold:(?:edit|2|3|5|10)|warn_escalation:edit|retention:[a-z_]+:(?:30|90|180|365|off)|blocklist:(?:add:(?:track|artist)|remove:[1-9][0-9]?)|preset:(?:save|apply:[1-9][0-9]?|delete:[1-9][0-9]?)|session:(?:schedule|cancel:[A-Za-z0-9]+)|approved:(?:list|add|page:[0-9]{1,6}|remove:[1-9][0-9]{0,18})|reset:(?:music|welcome|safety|moderation|blocklist|presets)|resetconfirm:(?:music|welcome|safety|moderation|blocklist|presets):[a-f0-9]{12}|refresh):v[0-9]{1,12}$"
@bot.on_callback_query(filters.regex(_PATTERN))
async def settings_callback(client,query):
    message=getattr(query,"message",None); actor=getattr(query,"from_user",None)
    if message is None or actor is None:
        return await query.answer("Open settings from a valid Telegram account.",show_alert=True)
    kind = base.chat_kind(message)
    connected_dm = kind == "private" and int(message.chat.id) == int(actor.id)
    if kind not in {"group", "supergroup"} and not connected_dm:
        return await query.answer("Open personal settings in your private chat or group settings in a group.",show_alert=True)
    try:
        parts=str(query.data).split(":")
        marker=parts.pop()
        if not marker.startswith("v") or not marker[1:].isdecimal(): raise ValueError
        expected_revision=int(marker[1:])
        chat_id=int(parts[1])
        if not connected_dm and chat_id!=int(message.chat.id):
            return await query.answer("These settings belong to another group.",show_alert=True)
        if connected_dm:
            from videl.app.connections import connected_target
            _, connection_error = await connected_target(client, int(actor.id), expected_chat_id=chat_id)
            if connection_error:
                return await query.answer(connection_error, show_alert=True)
        key=value=None; section="home"; category="all"; page=0
        if len(parts)==4 and parts[2]=="tab" and parts[3] in _TABS: section=parts[3]
        elif len(parts)==5 and parts[2]=="commands" and parts[3] in {"all","manage","music","tools"} and parts[4].isdecimal():
            section,category,page="commands",parts[3],min(int(parts[4]),999)
        elif len(parts)==4 and parts[2]=="filters" and parts[3] in {"add", "manage"}:
            key, value, section = ("__filters_add__" if parts[3] == "add" else "__filters_manage__"), None, "automations"
        elif len(parts)==5 and parts[2]=="cmd" and parts[4] in {"on","off"}:
            key,value,section="__command_toggle__",(parts[3],parts[4]=="on"),"commands"
        elif len(parts)==4 and parts[2]=="antispam" and parts[3]=="edit": key,value,section="__antispam_editor__",None,"safety"
        elif len(parts)==4 and parts[2]=="captcha" and parts[3]=="edit": key,value,section="__captcha_editor__",None,"welcome"
        elif len(parts)==4 and parts[2] in {"welcome_text","goodbye_text","rules_text","welcome_media","welcome_buttons"} and parts[3] in {"edit","clear"}:
            workflow={"welcome_text":"welcome_text","goodbye_text":"goodbye_text","rules_text":"rules_text","welcome_media":"welcome_media","welcome_buttons":"welcome_buttons"}[parts[2]]
            key,value,section="__welcome_flow_start__",workflow,"welcome"
        elif len(parts)==4 and parts[2] in ({k for values in _TOGGLES.values() for _,k,_ in values}|_LOCK_KEYS) and parts[3] in {"on","off"}:
            key,value=parts[2],parts[3]=="on"; section="safety" if key in {"antispam", "gemini_guardian_enabled"} or key in _LOCK_KEYS else ("music" if key.startswith("music_") else "welcome")
        elif len(parts)==4 and parts[2]=="raid" and parts[3] in {"on","off"}:
            from videl.utils.raid import normalize
            value=normalize(base.get_setting(chat_id,"raid_mode",{})); value["enabled"]=parts[3]=="on"; key,section="raid_mode","safety"
        elif len(parts)==4 and parts[2]=="warn_threshold" and parts[3] in {"edit","2","3","5","10"}:
            key,value,section="__warn_threshold_editor__",(None if parts[3]=="edit" else int(parts[3])),"moderation"
        elif len(parts)==4 and parts[2]=="warn_escalation" and parts[3]=="edit":
            key,value,section="__escalation_editor__",None,"moderation"
        elif len(parts)==5 and parts[2]=="retention":
            from videl.utils.retention import ALLOWED_DAYS,CATEGORIES
            cat=parts[3]; days=None if parts[4]=="off" else int(parts[4])
            if cat not in CATEGORIES or (days is not None and days not in ALLOWED_DAYS): raise ValueError
            key,value,section="__retention__",(cat,days),"retention"
        elif len(parts)==5 and parts[2]=="blocklist" and parts[3]=="add" and parts[4] in {"track","artist"}: key,value,section="__prompt__",parts[4],"blocklist"
        elif len(parts)==5 and parts[2]=="blocklist" and parts[3]=="remove" and parts[4].isdecimal(): key,value,section="__remove__",int(parts[4]),"blocklist"
        elif len(parts)==4 and parts[2]=="approved" and parts[3] in {"list", "add"}:
            key,value,section=("__approved_list__" if parts[3] == "list" else "__approved_add__"),None,"safety"
        elif len(parts)==5 and parts[2]=="approved" and parts[3]=="page" and parts[4].isdecimal():
            key,value,section="__approved_list__",int(parts[4]),"safety"
        elif len(parts)==5 and parts[2]=="approved" and parts[3]=="remove" and parts[4].isdecimal():
            key,value,section="__approved_remove__",int(parts[4]),"safety"
        elif len(parts)==4 and parts[2]=="session" and parts[3]=="schedule": key,value,section="__session_schedule__","session","sessions"
        elif len(parts)==5 and parts[2]=="session" and parts[3]=="cancel": key,value,section="__session_cancel__",parts[4],"sessions"
        elif len(parts)==4 and parts[2]=="reset" and parts[3] in _RESET_DEFAULTS: key,value,section="__reset_preview__",parts[3],parts[3]
        elif len(parts)==5 and parts[2]=="resetconfirm" and parts[3] in _RESET_DEFAULTS and len(parts[4])==12: key,value,section="__reset_confirm__",(parts[3],parts[4]),parts[3]
        elif len(parts)==4 and parts[2]=="preset" and parts[3]=="save": key,value,section="__preset_save__","preset","presets"
        elif len(parts)==5 and parts[2]=="preset" and parts[3] in {"apply","delete"} and parts[4].isdecimal(): key,value,section=f"__preset_{parts[3]}__",int(parts[4]),"presets"
        elif len(parts)==3 and parts[2]=="refresh": pass
        else: raise ValueError
    except (TypeError,ValueError,IndexError): return await query.answer("That settings button is invalid.",show_alert=True)
    if connected_dm:
        dm_safe_keys = {None, "music_requests_enabled", "music_approval_required", "music_shuffle_enabled",
                        "welcome_enabled", "goodbye_enabled", "gemini_guardian_enabled", "raid_mode", *_LOCK_KEYS,
                        "__warn_threshold_editor__", "__escalation_editor__", "__antispam_editor__", "__captcha_editor__",
                        "__command_toggle__", "__reset_preview__", "__reset_confirm__",
                        "__session_cancel__", "__session_schedule__"}
        if key not in dm_safe_keys and not (
                key in {"__preset_save__", "__preset_apply__", "__preset_delete__"} and section == "presets"
                or key == "__welcome_flow_start__" and value in {"welcome_text", "goodbye_text", "rules_text", "welcome_media", "welcome_buttons"}
                or key in {"__prompt__", "__remove__"} and section == "blocklist"
                or key in {"__approved_list__", "__approved_add__", "__approved_remove__"} and section == "safety"
                or key == "__filters_add__" and section == "automations"):
            return await query.answer("That editor is not available in connected DM yet. No change was made.", show_alert=True)
    try:
        member=await client.get_chat_member(chat_id,int(actor.id)); status=str(getattr(member.status,"value",member.status)).casefold()
        if status not in {"owner","administrator"}: return await query.answer("Only current group admins can change settings.",show_alert=True)
    except Exception: return await query.answer("I could not verify your current group-admin status.",show_alert=True)
    from videl.utils import settings_store
    from videl.utils.settings_store import SettingsConflict
    try:
        settings_store.check(chat_id,expected_revision)
    except SettingsConflict:
        await query.answer("Settings changed since this panel was opened. Review the refreshed values.",show_alert=True)
        fresh=await _settings_screen(client, chat_id,section,category=category,page=page,connected_dm=connected_dm)
        return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
    if key in {"__filters_add__", "__filters_manage__"}:
        from videl.plugins import notes
        try:
            if key == "__filters_add__":
                await notes.start_filter_editor(client, message, chat_id, int(actor.id), mode="add",
                    interaction_chat_id=int(message.chat.id))
                return await query.answer("Reply privately to the keyword and response prompts; nothing is saved until confirmation.")
            if connected_dm:
                return await query.answer("Existing filters can be managed from /filters in the group; no changes were made.", show_alert=True)
            from types import SimpleNamespace
            screen = await notes.list_filters(SimpleNamespace(message=message, user=actor, client=client))
            await query.answer("Filter list opened.")
            return await rich_edit(message, screen.html, reply_markup=screen.keyboard)
        except Exception as error:
            LOGGER.debug("Could not open filter settings", exc_info=True)
            return await query.answer(str(error) if isinstance(error, (RuntimeError, ValueError))
                                      else "Could not open group filters.", show_alert=True)
    if key in {"__approved_list__", "__approved_add__", "__approved_remove__"}:
        if key == "__approved_list__":
            from videl.utils.db import get_db
            try:
                db = get_db()
                if db is None: raise RuntimeError("database unavailable")
                collection = db["approved"]
                total = collection.count_documents({"chat": chat_id})
                page_size = 10
                last_page = max(0, (total - 1) // page_size)
                list_page = min(max(int(value or 0), 0), last_page)
                cursor = collection.find({"chat": chat_id}, {"user": 1}).sort("user", 1).skip(list_page * page_size).limit(page_size)
                approved_ids = [int(row["user"]) for row in cursor
                                if isinstance(row.get("user"), int) and not isinstance(row.get("user"), bool)
                                and 0 < row["user"] <= 9_223_372_036_854_775_807]
            except Exception:
                return await query.answer("Approved-member list is unavailable; no changes were made.", show_alert=True)
            from pyrogram.types import InlineKeyboardMarkup
            rows = [[button(f"Remove {uid}", callback_data=f"settings:{chat_id}:approved:remove:{uid}", style="danger")]
                    for uid in approved_ids]
            if total > page_size:
                nav = []
                if list_page > 0:
                    nav.append(button("← Previous", callback_data=f"settings:{chat_id}:approved:page:{list_page - 1}"))
                nav.append(button(f"{list_page + 1}/{last_page + 1}", callback_data=f"settings:{chat_id}:approved:page:{list_page}"))
                if list_page < last_page:
                    nav.append(button("Next →", callback_data=f"settings:{chat_id}:approved:page:{list_page + 1}"))
                rows.append(nav)
            rows += [[button("＋ Approve member", callback_data=f"settings:{chat_id}:approved:add", style="primary")],
                     [button("← Protection", callback_data=f"settings:{chat_id}:tab:safety")]]
            first_item = list_page * page_size + 1 if total else 0
            last_item = min((list_page + 1) * page_size, total)
            text = (heading("Approved members", 3)
                    + body("Approved users bypass this group's content locks, blacklist, anti-flood, and join verification. "
                           "This list is not a directory of all group members.")
                    + body(f"Showing {first_item}–{last_item} of {total} approved users; page {list_page + 1} of {last_page + 1}.")
                    + table([(str(uid), "Approved · select Remove to revoke") for uid in approved_ids]
                            or [("Members", "None approved")]))
            await query.answer("Approved members loaded.")
            return await rich_edit(message, text, reply_markup=_tag_keyboard(InlineKeyboardMarkup(rows), chat_id))
        try:
            await _start_connected_approved_action(client, int(message.chat.id), int(actor.id), chat_id,
                "add" if key == "__approved_add__" else "remove", value)
        except Exception:
            return await query.answer("Could not stage approved-member change; nothing changed.", show_alert=True)
        return await query.answer("Reply privately to review the approved-member change. Nothing changed yet.")
    if key=="__escalation_editor__":
        try:
            await _start_escalation_editor(client, int(message.chat.id), int(actor.id), chat_id,
                expected_revision, connected_dm=connected_dm)
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not open warning escalation settings; nothing changed.", show_alert=True)
        return await query.answer("Reply to the prompt to review each warning-escalation setting before saving.")
    if key=="__warn_threshold_editor__":
        try:
            await _start_warn_threshold_editor(message, chat_id, int(actor.id), expected_revision, value,
                                                interaction_chat_id=int(message.chat.id))
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not open the warning threshold editor; nothing changed.", show_alert=True)
        return await query.answer("Choose a threshold and review the preview before saving.")
    if key=="__antispam_editor__":
        try:
            notice=await _start_antispam_editor(client,chat_id,int(actor.id),expected_revision,
                                                interaction_chat_id=int(message.chat.id))
        except RuntimeError as error:
            return await query.answer(str(error),show_alert=True)
        except Exception:
            return await query.answer("Could not start anti-flood settings; nothing changed.",show_alert=True)
        return await query.answer(notice)
    if key=="__captcha_editor__":
        from videl.plugins.welcome import start_welcome_workflow
        try:
            notice=await start_welcome_workflow(client,chat_id,int(actor.id),expected_revision,"captcha_enabled",
                                                interaction_chat_id=int(message.chat.id))
        except RuntimeError as error:
            return await query.answer(str(error),show_alert=True)
        except Exception:
            return await query.answer("Could not start join-verification settings; nothing changed.",show_alert=True)
        return await query.answer(notice)
    if key=="__welcome_flow_start__":
        from videl.plugins.welcome import start_welcome_workflow
        try:
            message_text=await start_welcome_workflow(client,chat_id,int(actor.id),expected_revision,value,
                                                      interaction_chat_id=int(message.chat.id))
        except RuntimeError as error:
            return await query.answer(str(error),show_alert=True)
        except Exception:
            return await query.answer("Could not start the Welcome editor; no settings changed.",show_alert=True)
        return await query.answer(message_text)
    if key == "gemini_guardian_enabled" and value:
        from videl.utils.gemini import configured
        if not configured():
            await query.answer("Gemini is not configured; this option remains off.", show_alert=True)
            fresh = await _settings_screen(client, chat_id, section, category=category, page=page, connected_dm=connected_dm)
            return await rich_edit(message, fresh.html, reply_markup=fresh.keyboard)
    if key=="__reset_preview__":
        preview=_reset_confirmation(chat_id,value)
        await query.answer("Review the reset preview; nothing changed.")
        return await rich_edit(message,preview.html,reply_markup=preview.keyboard)
    if key=="__reset_confirm__":
        reset_category,token=value
        if token!=_reset_signature(chat_id,reset_category):
            preview=_reset_confirmation(chat_id,reset_category)
            await query.answer("Settings changed; review the updated reset preview.",show_alert=True)
            return await rich_edit(message,preview.html,reply_markup=preview.keyboard)
        _,defaults=_reset_values(chat_id,reset_category)
        if not base.set_settings(chat_id,defaults,expected_revision=expected_revision):
            await query.answer("Reset not applied. Settings may have changed; refresh and review again.",show_alert=True)
            fresh=await _settings_screen(client, chat_id,reset_category,connected_dm=connected_dm)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        if reset_category=="safety":
            from videl.utils.raid import clear
            clear(chat_id)
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot,chat_id,"settings",action="settings_reset",detail=f"category={reset_category}; keys={','.join(defaults)}",actor=int(actor.id))
        except Exception: pass
        await query.answer("Section reset and audited.")
        fresh=await _settings_screen(client, chat_id,reset_category,connected_dm=connected_dm)
        return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
    if connected_dm and section == "sessions" and key == "__session_schedule__":
        try:
            await _start_connected_session(client, int(message.chat.id), int(actor.id), chat_id, expected_revision)
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not start the listening-session editor; nothing changed.", show_alert=True)
        return await query.answer("Reply privately to continue; no session is created until you confirm.")
    if connected_dm and section == "presets" and key in {"__preset_apply__", "__preset_delete__"}:
        try:
            await _start_connected_preset_action(client, int(message.chat.id), int(actor.id), chat_id,
                expected_revision, "apply" if key == "__preset_apply__" else "delete", value)
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not start this preset action; nothing changed.", show_alert=True)
        return await query.answer("Reply privately to review the staged preset action. No change has been applied.")
    if connected_dm and section == "presets" and key == "__preset_save__":
        try:
            await _start_connected_preset(client, int(message.chat.id), int(actor.id), chat_id, expected_revision)
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not start the preset editor; nothing changed.", show_alert=True)
        return await query.answer("Reply privately to continue; nothing is saved until confirmation.")
    if connected_dm and section == "blocklist" and key in {"__prompt__", "__remove__"}:
        try:
            await _start_connected_blocklist(client, int(message.chat.id), int(actor.id), chat_id,
                                            expected_revision, "add" if key == "__prompt__" else "remove",
                                            value)
        except RuntimeError as error:
            return await query.answer(str(error), show_alert=True)
        except Exception:
            return await query.answer("Could not start the blocklist editor; nothing changed.", show_alert=True)
        return await query.answer("Reply privately to continue; nothing is saved until confirmation.")
    if key in {"__prompt__","__preset_save__","__session_schedule__"}:
        kind = value if key == "__prompt__" else ("preset" if key == "__preset_save__" else "session")
        prompt_text = ("Reply with a name for this preset (1–32 characters)." if kind == "preset" else ("Reply with YYYY-MM-DD HH:MM UTC | Session title. Example: 2026-11-05 19:30 UTC | Friday listening." if kind == "session" else f"Reply to this message with the {kind} name to block (up to 100 characters). This reply is visible in the group."))
        prompt=await client.send_message(chat_id,prompt_text,reply_markup=ForceReply(selective=True))
        expired=[key for key,item in _PROMPTS.items() if item[2] < monotonic()]
        for expired_key in expired: _PROMPTS.pop(expired_key,None)
        if len(_PROMPTS)>=500: _PROMPTS.pop(next(iter(_PROMPTS)),None)
        _PROMPTS[(chat_id,int(actor.id))]=(int(prompt.id),kind,monotonic()+300,expected_revision)
        await query.answer("Reply to the prompt to continue."); return
    if key=="__command_toggle__":
        try: settings_store.write(chat_id,{},expected=expected_revision)
        except SettingsConflict:
            await query.answer("Settings changed; refresh before changing command switches.",show_alert=True)
            fresh=await _settings_screen(client, chat_id,section,category=category,page=page,connected_dm=connected_dm)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        name,enable=value
        from videl.utils.command_catalog import commands as registered_commands
        from videl.utils.db import disable_cmd,enable_cmd,get_db
        protected={"start","help","commands","id","ping","settings","permissions"}
        entry=next((item for item in registered_commands() if item["name"]==name),None)
        if entry is None or entry.get("owner") or entry.get("context")=="private" or name in protected:
            return await query.answer("That command cannot be changed here.",show_alert=True)
        db=get_db()
        if db is None: return await query.answer("Command switches are unavailable because the database is not connected.",show_alert=True)
        try:
            if enable: enable_cmd(chat_id,name)
            else: disable_cmd(chat_id,name)
            from videl.utils import db as db_module
            db_module._DISABLED_CACHE.pop(chat_id,None)
            persisted=db["disabled_cmds"].find_one({"chat":chat_id,"cmd":name}) is not None
            if persisted==enable:
                return await query.answer("The command switch could not be verified; no success was reported.",show_alert=True)
        except Exception:
            return await query.answer("The command switch could not be saved or verified.",show_alert=True)
    if key=="__session_cancel__":
        from videl.utils.db import get_db
        from videl.utils.listening_sessions import cancel
        try: await asyncio.to_thread(settings_store.write,chat_id,{},expected=expected_revision)
        except SettingsConflict:
            await query.answer("Settings changed; refresh before cancelling this session.",show_alert=True)
            fresh=await _settings_screen(client, chat_id,section,category=category,page=page,connected_dm=connected_dm)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        if not await asyncio.to_thread(cancel,get_db(),chat_id,value): return await query.answer("Session not found or already started.",show_alert=True)
        key=None
    if key in {"__preset_apply__","__preset_delete__"}:
        from videl.utils.music_presets import get as get_preset, normalize as normalize_presets, remove as remove_preset
        presets=normalize_presets(base.get_setting(chat_id,"music_session_presets",[]))
        preset=get_preset(presets,value)
        if preset is None: return await query.answer("That preset no longer exists.",show_alert=True)
        if key=="__preset_delete__":
            presets=remove_preset(presets,value)
            if not base.set_setting(chat_id,"music_session_presets",presets,expected_revision=expected_revision): return await query.answer("Preset could not be deleted; refresh and review settings.",show_alert=True)
        else:
            from videl.core import player,queue
            from videl.core.playback_state import lock
            import random
            values={"music_requests_enabled":bool(preset.get("requests",True)),"music_approval_required":bool(preset.get("approval",False)),"music_shuffle_enabled":bool(preset.get("shuffle",False))}
            if not base.set_settings(chat_id,values,expected_revision=expected_revision): return await query.answer("Preset could not be applied; refresh and review settings.",show_alert=True)
            async with lock(chat_id):
                player.set_loop(chat_id,preset.get("loop","off") if preset.get("loop") in {"off","one","all"} else "off")
                if values["music_shuffle_enabled"]:
                    items=queue.get_queue(chat_id)
                    upcoming=items[1:]
                    random.shuffle(upcoming)
                    items[1:]=upcoming
                    queue.note_queue_mutation(chat_id)
        key=None
    if key=="__remove__":
        from videl.utils.track_blocklist import normalize,remove
        try: value=remove(base.get_setting(chat_id,"music_track_blocklist",[]),value)
        except ValueError: return await query.answer("That entry is no longer available.",show_alert=True)
        key="music_track_blocklist"
    if key=="__retention__":
        from videl.utils.db import get_db
        from videl.utils.retention import save
        cat,days=value
        try: await asyncio.to_thread(settings_store.write,chat_id,{},expected=expected_revision)
        except SettingsConflict:
            await query.answer("Settings changed; refresh and review retention before retrying.",show_alert=True)
            fresh=await _settings_screen(client, chat_id,section,category=category,page=page,connected_dm=connected_dm)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        saved=await asyncio.to_thread(save,get_db(),chat_id,cat,days)
        if saved is None: return await query.answer("Retention could not be saved.",show_alert=True)
    elif key in _LOCK_KEYS and value and not await _bot_can_delete_messages(client, chat_id):
        return await query.answer("The bot needs Delete Messages permission to enable content locks. Nothing changed.", show_alert=True)
    elif key and key!="__command_toggle__" and not base.set_setting(chat_id,key,value,expected_revision=expected_revision): return await query.answer("The setting could not be saved; refresh and review before retrying.",show_alert=True)
    if key == "antispam":
        from videl.plugins.locks import invalidate_antispam_config
        invalidate_antispam_config(chat_id)
    if key:
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot,chat_id,"settings",action="group_setting",detail=f"{key}={value}",actor=int(actor.id))
        except Exception: pass
    await query.answer("Settings refreshed." if key is None else "Setting saved.")
    screen=await _settings_screen(client, chat_id,section,category=category,page=page,connected_dm=connected_dm); await rich_edit(message,screen.html,reply_markup=screen.keyboard)

@bot.on_callback_query(filters.regex(_WARN_CALLBACK))
async def warn_threshold_editor_callback(client, query):
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or actor is None:
        return await query.answer("Open the warning editor from a valid Telegram account.", show_alert=True)
    interaction_kind = base.chat_kind(message)
    connected_dm = interaction_kind == "private" and int(message.chat.id) == int(actor.id)
    if interaction_kind not in {"group", "supergroup"} and not connected_dm:
        return await query.answer("This warning editor is not available in this chat.", show_alert=True)
    interaction_chat_id, actor_id = int(message.chat.id), int(actor.id)
    try:
        _, token, action, *selected = str(query.data).split(":")
    except ValueError:
        return await query.answer("That warning editor action is invalid.", show_alert=True)
    session = await engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "warn_threshold":
        return await query.answer("This warning threshold edit expired or belongs to another admin.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if connected_dm:
        from videl.app.connections import connected_target
        _, connection_error = await connected_target(client, actor_id, expected_chat_id=target_chat_id)
        if connection_error:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer(connection_error, show_alert=True)
    elif target_chat_id != interaction_chat_id:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await query.answer("This editor belongs to another group.", show_alert=True)
    try:
        member = await client.get_chat_member(target_chat_id, actor_id)
        status = str(getattr(getattr(member, "status", None), "value", getattr(member, "status", None))).casefold()
        if status not in {"owner", "administrator"}:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer("Current group-admin permission could not be verified. Nothing was saved.", show_alert=True)
    except Exception:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await query.answer("Current group-admin status could not be verified. Nothing was saved.", show_alert=True)

    if action in {"cancel", "back"}:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved." if action == "cancel" else "Back to moderation settings.")
        screen = _screen(target_chat_id, "moderation", connected_dm=connected_dm)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)

    if action == "edit":
        saved_value = session.values.get("saved_value", 3)
        edited = await engine.edit_again(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                         message_id=int(message.id))
        if edited is None:
            return await query.answer("This preview is no longer active.", show_alert=True)
        edited.values["saved_value"] = saved_value
        screen = _warn_threshold_selection_screen(edited)
        await rich_edit(message, screen.html, reply_markup=screen.keyboard)
        await engine.bind_prompt(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                 message_id=int(message.id))
        return await query.answer("Choose a value from 1 to 10.")

    if action == "pick":
        if len(selected) != 1 or selected[0] not in _WARN_THRESHOLD_VALUES:
            return await query.answer("Choose a warning threshold from 1 to 10.", show_alert=True)
        result = await engine.capture(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                      target_chat_id=target_chat_id, reply_to_message_id=int(message.id),
                                      value=selected[0])
        if result.status != "preview":
            return await query.answer("This selection is no longer active. Reopen the editor.", show_alert=True)
        screen = _warn_threshold_preview(result.session)
        await rich_edit(message, screen.html, reply_markup=screen.keyboard)
        await engine.bind_prompt(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                 message_id=int(message.id))
        return await query.answer("Review the preview; nothing has been saved.")

    if action != "save":
        return await query.answer("That warning editor action is invalid.", show_alert=True)

    async def authorize(target_id: int, user_id: int) -> bool:
        if connected_dm:
            from videl.app.connections import connected_target
            _, error = await connected_target(client, user_id, expected_chat_id=target_id)
            if error:
                return False
        try:
            member = await client.get_chat_member(target_id, user_id)
            status = str(getattr(getattr(member, "status", None), "value",
                                 getattr(member, "status", None))).casefold()
            return status in {"owner", "administrator"}
        except Exception:
            return False

    save_error = {"conflict": False}

    async def save(snapshot) -> bool:
        from videl.utils.settings_store import SettingsConflict, write
        try:
            await asyncio.to_thread(write, snapshot.target_chat_id,
                                    {"warn_threshold": int(snapshot.values["warn_threshold"])},
                                    expected=snapshot.revision)
            return True
        except SettingsConflict:
            save_error["conflict"] = True
            return False
        except Exception:
            return False

    outcome, _ = await engine.commit(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                     target_chat_id=target_chat_id, message_id=int(message.id),
                                     authorize=authorize, save=save)
    if outcome == "saved":
        try:
            from videl.utils.audit import record_bot
            value = int(session.values["warn_threshold"])
            await asyncio.to_thread(record_bot, target_chat_id, "settings",
                                    action="warn_threshold_interactive_saved",
                                    detail=f"warn_threshold={value}", actor=actor_id)
        except Exception:
            LOGGER.debug("Warning threshold audit write failed", exc_info=True)
        await query.answer("Warning threshold saved.")
        screen = _screen(target_chat_id, "moderation", connected_dm=connected_dm)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)
    if outcome == "permission_denied":
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Current group-admin permission could not be verified. Nothing was saved.", show_alert=True)
        screen = _screen(target_chat_id, "moderation", connected_dm=connected_dm)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)
    if outcome == "save_failed" and save_error["conflict"]:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Settings changed elsewhere. No warning threshold was saved; review the latest value.", show_alert=True)
        screen = _screen(target_chat_id, "moderation", connected_dm=connected_dm)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)
    if outcome == "save_failed":
        await query.answer("Could not save the warning threshold. Nothing was reported as saved; retry from this preview.", show_alert=True)
        return
    if outcome == "expired":
        return await query.answer("This warning threshold edit expired. Nothing was saved.", show_alert=True)
    return await query.answer("This warning threshold preview is no longer active.", show_alert=True)


# Run after the declarative command router (group 0). A broad text listener in
# the same Pyrogram group would consume every group message before /start/help.
@bot.on_message(filters.group & filters.text, group=1)
async def blocklist_prompt_reply(client,message):
    user=getattr(message,"from_user",None); reply=getattr(message,"reply_to_message",None)
    if not user or not reply: return
    chat_id=int(message.chat.id); prompt=_PROMPTS.get((chat_id,int(user.id)))
    if not prompt or int(reply.id)!=prompt[0]: return
    del _PROMPTS[(chat_id,int(user.id))]
    if prompt[2] < monotonic(): return await message.reply_text("That settings prompt expired. Reopen /settings to try again.")
    try:
        member=await client.get_chat_member(chat_id,int(user.id)); status=str(getattr(member.status,"value",member.status)).casefold()
        if status not in {"owner","administrator"}: return await message.reply_text("Only current group admins can change the blocklist.")
    except Exception: return await message.reply_text("I could not verify your current group-admin status.")
    if prompt[1] == "session":
        from videl.utils.db import get_db
        from videl.utils.listening_sessions import parse_schedule, schedule
        try: due,title=parse_schedule(message.text or "")
        except ValueError as error: return await message.reply_text(str(error))
        try:
            from videl.utils import settings_store
            await asyncio.to_thread(settings_store.write,chat_id,{},expected=prompt[3])
        except Exception:
            return await message.reply_text("Settings changed while the prompt was open. Reopen /settings and review before scheduling.")
        identifier=await asyncio.to_thread(schedule,get_db(),chat_id,int(user.id),due,title)
        if identifier is None: return await message.reply_text("Could not schedule this session. Each group may have up to five pending sessions; check that the database is available.")
        await message.reply_text(f"Session scheduled for {due.strftime('%Y-%m-%d %H:%M UTC')}. Requests will open when it starts. Manage it in /settings → Listening sessions.")
        return
    if prompt[1] == "preset":
        name=(message.text or "").strip()
        try:
            from videl.core.player import get_loop
            from videl.utils.music_presets import add as add_preset, normalize as normalize_presets
            snapshot={"loop":get_loop(chat_id),"shuffle":bool(base.get_setting(chat_id,"music_shuffle_enabled",False)),
                      "requests":bool(base.get_setting(chat_id,"music_requests_enabled",True)),
                      "approval":bool(base.get_setting(chat_id,"music_approval_required",False))}
            presets=add_preset(base.get_setting(chat_id,"music_session_presets",[]),name,snapshot)
        except ValueError as error: return await message.reply_text(str(error))
        except Exception: return await message.reply_text("Could not read the current playback settings.")
        if not base.set_setting(chat_id,"music_session_presets",presets,expected_revision=prompt[3]): return await message.reply_text("The preset could not be saved because settings changed or the database is unavailable. Reopen /settings and review first.")
        await message.reply_text("Saved this group music preset. Open /settings → Queue presets to apply it.")
        return
    try:
        from videl.utils.track_blocklist import add
        current=base.get_setting(chat_id,"music_track_blocklist",[])
        updated=add(current,prompt[1],message.text or "")
    except ValueError as error: return await message.reply_text(str(error))
    if not base.set_setting(chat_id,"music_track_blocklist",updated,expected_revision=prompt[3]): return await message.reply_text("The blocklist could not be saved because settings changed or the database is unavailable. Reopen /settings and review first.")
    try:
        from videl.utils.audit import record_bot
        await asyncio.to_thread(record_bot,chat_id,"settings",action="music_blocklist_add",detail=f"{prompt[1]} entry",actor=int(user.id))
    except Exception: pass
    await message.reply_text("Added to the group music blocklist. Open /settings → Music blocklist to review it.")

async def _group_bot_can_announce(client, target_chat_id: int) -> bool:
    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
        bot_member = await client.get_chat_member(target_chat_id, int(bot_user.id))
        status = str(getattr(getattr(bot_member, "status", None), "value",
                             getattr(bot_member, "status", ""))).casefold()
        if status in {"owner", "administrator"}:
            return True
        permissions = getattr(bot_member, "permissions", None)
        if permissions is None:
            permissions = getattr(bot_member, "privileges", None)
        return status in {"member", "restricted"} and bool(getattr(permissions, "can_send_messages", False))
    except Exception:
        return False


async def _start_connected_session(client, interaction_chat_id: int, actor_id: int,
                                   target_chat_id: int, revision: int) -> None:
    from videl.utils.interactive_settings import Step, engine as interaction_engine
    if not await _group_bot_can_announce(client, target_chat_id):
        raise RuntimeError("The bot cannot currently send announcements in the connected group.")
    session = await interaction_engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
        target_chat_id=target_chat_id, workflow="listening_session_schedule",
        steps=(Step("details", "UTC start and session title", max_length=300),),
        revision=revision, timeout_seconds=600)
    try:
        prompt = await client.send_message(interaction_chat_id,
            "Reply as <code>YYYY-MM-DD HH:MM UTC | Session title</code> (up to 100 title characters, within 30 days). "
            "The bot needs permission to send messages in the group. Send /cancel to stop.",
            reply_markup=ForceReply(selective=True))
        await interaction_engine.bind_prompt(session.token, chat_id=interaction_chat_id,
                                             actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


@bot.on_message(filters.private & filters.incoming, group=2)
async def connected_session_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None or int(message.chat.id) != int(actor.id): return
    from videl.utils.interactive_settings import engine as interaction_engine
    actor_id = int(actor.id); interaction_chat_id = int(message.chat.id)
    session = await interaction_engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "listening_session_schedule": return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Listening-session scheduling cancelled; nothing was created.")
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id: return
    from videl.utils.listening_sessions import parse_schedule
    try:
        due, title = parse_schedule(text)
    except ValueError as error:
        return await client.send_message(interaction_chat_id, f"{error} Reply to the prompt again or /cancel.")
    result = await interaction_engine.capture(session.token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=session.target_chat_id,
        reply_to_message_id=getattr(reply, "id", None), value=text)
    if result.status == "invalid":
        return await client.send_message(interaction_chat_id, result.error or "Invalid schedule details.")
    if result.status != "preview": return
    result.session.values["due_at"] = due
    result.session.values["title"] = title
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.plugins.base import escape
    preview_text = ("<b>Listening-session schedule preview</b>\n"
        f"Group: <code>{result.session.target_chat_id}</code>\n"
        f"Starts: <b>{due.strftime('%Y-%m-%d %H:%M UTC')}</b>\nTitle: <b>{escape(title)}</b>\n"
        "The existing scheduler will enable member music requests and post the announcement at this time. "
        "No session has been created yet.")
    markup = InlineKeyboardMarkup([[button("Edit", callback_data=f"listensession_edit:{result.session.token}"),
        button("Confirm", callback_data=f"listensession_save:{result.session.token}", style="primary"),
        button("Cancel", callback_data=f"listensession_cancel:{result.session.token}", style="danger")]])
    try:
        preview = await client.send_message(interaction_chat_id, preview_text, reply_markup=markup)
        await interaction_engine.bind_prompt(result.session.token, chat_id=interaction_chat_id,
            actor_id=actor_id, message_id=preview.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        await client.send_message(interaction_chat_id, "Could not render schedule preview; no session was created.")


@bot.on_callback_query(filters.regex(r"^listensession_(?:edit|save|cancel):[A-Za-z0-9_-]{1,24}$"))
async def connected_session_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) != "private" or int(message.chat.id) != int(actor.id):
        return await query.answer("This listening-session action is unavailable.", show_alert=True)
    action, token = str(query.data).split(":", 1)
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "listening_session_schedule":
        return await query.answer("This session draft expired or is not yours. Nothing was created.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if action.endswith("cancel"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; no scheduled session was created.")
        return await rich_edit(message, "Listening-session scheduling cancelled. Nothing was created.", reply_markup=None)
    if action.endswith("edit"):
        edited = await interaction_engine.edit_again(token, chat_id=interaction_chat_id,
            actor_id=actor_id, message_id=message.id)
        if edited is None: return await query.answer("This preview is no longer active.", show_alert=True)
        edited.values.clear()
        try:
            prompt = await client.send_message(interaction_chat_id,
                "Reply as <code>YYYY-MM-DD HH:MM UTC | Session title</code>. Send /cancel to stop.",
                reply_markup=ForceReply(selective=True))
            await interaction_engine.bind_prompt(token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=prompt.id)
        except Exception:
            await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer("Could not restart editor; no session was created.", show_alert=True)
        return await query.answer("Reply privately to edit the schedule.")

    async def authorize(target_id, user_id):
        from videl.app.connections import connected_target
        _, error = await connected_target(client, user_id, expected_chat_id=target_id)
        if error: return False
        return await _group_bot_can_announce(client, target_id)

    async def save(snapshot):
        from videl.utils import settings_store
        from videl.utils.settings_store import SettingsConflict
        from videl.utils.db import get_db
        from videl.utils.listening_sessions import parse_schedule, schedule
        try:
            settings_store.check(target_chat_id, snapshot.revision)
            due, title = parse_schedule(snapshot.values["details"])
        except (SettingsConflict, ValueError):
            return False
        import hashlib
        identifier = hashlib.sha256(snapshot.token.encode("utf-8")).hexdigest()[:24]
        return await asyncio.to_thread(schedule, get_db(), target_chat_id, actor_id,
                                       due, title, identifier=identifier) is not None

    outcome, _ = await interaction_engine.commit(token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id, message_id=message.id,
        authorize=authorize, save=save)
    if outcome == "saved":
        await query.answer("Listening session scheduled.")
        return await rich_edit(message, "Listening session scheduled. Open /settings → Sessions to review it.", reply_markup=None)
    messages = {"permission_denied": "Connection, admin access, or bot send permission changed. No session was created.",
                "save_failed": "Could not schedule this session, or the draft became stale. No success was reported; refresh the Sessions page and retry.",
                "expired": "This draft expired. No session was created.",
                "stale": "This preview is stale or already being confirmed.",
                "unauthorized": "This draft does not belong to this admin or group."}
    return await query.answer(messages.get(outcome, "Could not schedule session."), show_alert=True)


async def _start_connected_approved_action(client, interaction_chat_id: int, actor_id: int,
                                          target_chat_id: int, operation: str, user_id: int | None) -> None:
    from videl.utils.interactive_settings import Step, engine as interaction_engine
    steps = ((Step("user_id", "Telegram user ID", kind="number", minimum=1,
                   maximum=9_223_372_036_854_775_807),) if operation == "add" else
             (Step("review", "Review removal", kind="selection", choices=("preview",)),))
    session = await interaction_engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
        target_chat_id=target_chat_id, workflow=f"approved_member_{operation}",
        steps=steps, timeout_seconds=600)
    if operation == "remove":
        session.values["user_id"] = int(user_id)
    try:
        prompt_text = ("Reply with a numeric Telegram user ID or @username to approve. Usernames are resolved by Telegram, then only the numeric ID is stored. This grants an exemption from this group's content locks, blacklist, anti-flood, and join verification. Reply /cancel to stop." if operation == "add" else
                       f"Selected user <code>{int(user_id)}</code> for approval removal in group <code>{target_chat_id}</code>. "
                       "Reply <code>PREVIEW</code> to review the exact change, or /cancel to stop.")
        prompt = await client.send_message(interaction_chat_id, prompt_text,
            reply_markup=ForceReply(selective=True))
        await interaction_engine.bind_prompt(session.token, chat_id=interaction_chat_id,
                                             actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


async def _send_connected_approved_preview(client, session) -> None:
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.utils.db import get_db
    from videl.plugins.base import escape
    db = get_db()
    if db is None: raise RuntimeError("Approved-member storage is unavailable.")
    uid = int(session.values["user_id"])
    present = db["approved"].find_one({"chat": int(session.target_chat_id), "user": uid}) is not None
    operation = "add" if session.workflow == "approved_member_add" else "remove"
    if operation == "add" and present:
        raise ValueError("This user is already approved. Refresh the list; nothing changed.")
    if operation == "remove" and not present:
        raise ValueError("This user is no longer approved. Refresh the list; nothing changed.")
    session.values["was_approved"] = present
    effect = ("will be added to the existing approved collection and bypass this group's content locks, blacklist, anti-flood, and join verification."
              if operation == "add" else "will be removed from the existing approved collection and lose those exemptions.")
    text = (f"<b>{'Approve' if operation == 'add' else 'Remove approved status'} preview</b>\n"
            f"Group: <code>{int(session.target_chat_id)}</code>\nUser ID: <code>{uid}</code>\n"
            f"Effect: {escape(effect)}\nNo change has been made yet.")
    markup = InlineKeyboardMarkup([[button("Edit", callback_data=f"approved_action_edit:{session.token}"),
        button("Confirm", callback_data=f"approved_action_save:{session.token}", style="primary"),
        button("Cancel", callback_data=f"approved_action_cancel:{session.token}", style="danger")]])
    preview = await client.send_message(session.chat_id, text, reply_markup=markup)
    from videl.utils.interactive_settings import engine as interaction_engine
    await interaction_engine.bind_prompt(session.token, chat_id=session.chat_id,
        actor_id=session.actor_id, message_id=preview.id)


@bot.on_message(filters.private & filters.incoming, group=2)
async def connected_approved_action_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None or int(message.chat.id) != int(actor.id): return
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"approved_member_add", "approved_member_remove"}: return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Approved-member change cancelled; nothing changed.")
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id: return
    capture_value = text.casefold() if session.workflow.endswith("remove") else text
    if session.workflow == "approved_member_add" and text.startswith("@"):
        import re
        if not re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}", text):
            return await client.send_message(interaction_chat_id,
                "That username is malformed. Send a numeric Telegram user ID or a valid @username.")
        try:
            resolved = await asyncio.wait_for(client.get_users(text), timeout=8)
            uid = int(getattr(resolved, "id", 0))
            if not 0 < uid <= 9_223_372_036_854_775_807:
                raise ValueError("invalid Telegram user")
            capture_value = str(uid)
        except Exception:
            return await client.send_message(interaction_chat_id,
                "Telegram could not resolve that user. Check the @username and try again; nothing changed.")
    captured = await interaction_engine.capture(session.token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=session.target_chat_id,
        reply_to_message_id=getattr(reply, "id", None), value=capture_value)
    if captured.status == "invalid":
        prompt = "Reply PREVIEW or /cancel." if session.workflow.endswith("remove") else "Send a positive numeric Telegram user ID or resolvable @username, or /cancel."
        return await client.send_message(interaction_chat_id, prompt)
    if captured.status != "preview": return
    try:
        await _send_connected_approved_preview(client, captured.session)
    except ValueError as error:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, str(error))
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Could not render approved-member preview; nothing changed.")


@bot.on_callback_query(filters.regex(r"^approved_action_(?:edit|save|cancel):[A-Za-z0-9_-]{1,24}$"))
async def connected_approved_action_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) != "private" or int(message.chat.id) != int(actor.id):
        return await query.answer("This approved-member action is unavailable.", show_alert=True)
    action, token = str(query.data).split(":", 1)
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"approved_member_add", "approved_member_remove"}:
        return await query.answer("This action expired or is not yours. No approved-user change was made.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if action.endswith("cancel"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; approved-member access was unchanged.")
        return await rich_edit(message, "Approved-member change cancelled. Nothing changed.", reply_markup=None)
    if action.endswith("edit"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Reopen the approved-member list to edit this draft.")
        screen = await _settings_screen(client, target_chat_id, "safety", connected_dm=True)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)

    async def authorize(target_id, user_id):
        from videl.app.connections import connected_target
        _, error = await connected_target(client, user_id, expected_chat_id=target_id)
        return not error

    async def save(snapshot):
        from videl.utils.db import get_db
        db = get_db()
        if db is None: return False
        uid = int(snapshot.values["user_id"]); collection = db["approved"]
        present = collection.find_one({"chat": target_chat_id, "user": uid}) is not None
        if present != bool(snapshot.values["was_approved"]): return False
        if snapshot.workflow == "approved_member_add":
            collection.update_one({"chat": target_chat_id, "user": uid},
                {"$set": {"chat": target_chat_id, "user": uid}}, upsert=True)
            return collection.find_one({"chat": target_chat_id, "user": uid}) is not None
        result = collection.delete_one({"chat": target_chat_id, "user": uid})
        return result.deleted_count == 1 and collection.find_one({"chat": target_chat_id, "user": uid}) is None

    outcome, _ = await interaction_engine.commit(token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id, message_id=message.id,
        authorize=authorize, save=save)
    if outcome == "saved":
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot, target_chat_id, "settings",
                action="approved_member_added" if session.workflow.endswith("add") else "approved_member_removed",
                detail="approved-user access changed", actor=actor_id)
        except Exception: pass
        label = "approved" if session.workflow.endswith("add") else "removed from the approved list"
        await query.answer("Approved-member change saved.")
        return await rich_edit(message, f"User <code>{int(session.values['user_id'])}</code> {label} in the connected group.", reply_markup=None)
    messages = {"permission_denied": "Connection or current admin permission changed. No approved-member change was made.",
                "save_failed": "Approved-member state changed or storage failed. Nothing was reported as complete; refresh and preview again.",
                "expired": "This approved-member preview expired. No change was made.",
                "stale": "This preview is stale or already being confirmed.",
                "unauthorized": "This action does not belong to this admin or group."}
    return await query.answer(messages.get(outcome, "Approved-member action failed; no success was reported."), show_alert=True)


async def _queue_state_snapshot(chat_id: int) -> dict:
    from videl.core import queue, player
    from videl.core.playback_state import lock
    async with lock(chat_id):
        tracks = list(queue.get_queue(chat_id))
        signature = tuple((id(song), repr(song)) for song in tracks)
        return {"queue_revision": queue.mutation_revision(chat_id),
                "queue_signature": signature, "queue_length": len(tracks),
                "loop": player.get_loop(chat_id),
                "requests": bool(base.get_setting(chat_id, "music_requests_enabled", True)),
                "approval": bool(base.get_setting(chat_id, "music_approval_required", False)),
                "shuffle": bool(base.get_setting(chat_id, "music_shuffle_enabled", False))}


async def _start_connected_preset_action(client, interaction_chat_id: int, actor_id: int,
                                         target_chat_id: int, revision: int,
                                         operation: str, index: int) -> None:
    from videl.utils.interactive_settings import Step, engine as interaction_engine
    from videl.utils.music_presets import get, normalize
    presets = normalize(base.get_setting(target_chat_id, "music_session_presets", []))
    selected = get(presets, int(index))
    if selected is None:
        raise RuntimeError("That preset no longer exists. Refresh the Queue presets page.")
    workflow = "music_preset_apply" if operation == "apply" else "music_preset_delete"
    session = await interaction_engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
        target_chat_id=target_chat_id, workflow=workflow,
        steps=(Step("review", "Review selected preset", kind="selection", choices=("preview",)),),
        revision=revision, timeout_seconds=600)
    session.values.update({"preset_index": int(index), "preset": selected})
    try:
        label = "apply" if operation == "apply" else "delete"
        prompt = await client.send_message(interaction_chat_id,
            f"Selected preset <b>{selected['name']}</b> for {label} in group <code>{target_chat_id}</code>. "
            "Reply <code>PREVIEW</code> to review the exact action. Send <code>/cancel</code> to stop.",
            reply_markup=ForceReply(selective=True))
        await interaction_engine.bind_prompt(session.token, chat_id=interaction_chat_id,
                                             actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


async def _send_connected_preset_action_preview(client, session) -> None:
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.plugins.base import escape
    from videl.utils.music_presets import get, normalize
    target = int(session.target_chat_id)
    current = normalize(base.get_setting(target, "music_session_presets", []))
    selected = get(current, session.values["preset_index"])
    if selected is None or selected != session.values["preset"]:
        raise ValueError("The selected preset changed. Reopen Queue presets for a fresh preview.")
    session.values["preset"] = dict(selected)
    if session.workflow == "music_preset_apply":
        live = await _queue_state_snapshot(target)
        session.values["queue_revision"] = live["queue_revision"]
        session.values["queue_signature"] = live["queue_signature"]
        session.values["queue_length"] = live["queue_length"]
        session.values["live_state"] = {key: live[key] for key in ("loop", "shuffle", "requests", "approval")}
        shuffle = bool(selected.get("shuffle", False))
        if shuffle:
            queue_effect = (f"The current track remains in place. The {max(0, live['queue_length'] - 1)} upcoming tracks "
                            "will be shuffled in place; no queue item will be removed.")
        else:
            queue_effect = "The active queue will remain in its current order; no queue item will be removed."
        text = ("<b>Apply queue preset preview</b>\n"
            f"Group: <code>{target}</code>\nPreset: <b>{escape(selected['name'])}</b> · saved settings revision {session.revision}\n"
            f"Repeat: {live['loop']} → {selected['loop']}\n"
            f"Member requests: {'On' if live['requests'] else 'Off'} → {'On' if selected['requests'] else 'Off'}\n"
            f"Approval required: {'On' if live['approval'] else 'Off'} → {'On' if selected['approval'] else 'Off'}\n"
            f"Shuffle for new requests: {'On' if live['shuffle'] else 'Off'} → {'On' if shuffle else 'Off'}\n{queue_effect}\n"
            "Confirm applies these settings only if both the preset and queue are unchanged since this preview.")
        action = "apply"
    else:
        text = ("<b>Delete queue preset preview</b>\n"
            f"Group: <code>{target}</code>\nPreset to delete: <b>{escape(selected['name'])}</b> · saved settings revision {session.revision}\n"
            f"Repeat: {selected['loop']} · Shuffle: {'On' if selected['shuffle'] else 'Off'} · "
            f"Requests: {'On' if selected['requests'] else 'Off'} · Approval: {'On' if selected['approval'] else 'Off'}\n"
            "Only this saved preset will be deleted. The active queue and playback settings will not change.")
        action = "delete"
    session.values["action"] = action
    markup = InlineKeyboardMarkup([[button("Edit", callback_data=f"preset_action_edit:{session.token}"),
        button("Confirm", callback_data=f"preset_action_save:{session.token}", style="primary"),
        button("Cancel", callback_data=f"preset_action_cancel:{session.token}", style="danger")]])
    preview = await client.send_message(session.chat_id, text, reply_markup=markup)
    from videl.utils.interactive_settings import engine as interaction_engine
    await interaction_engine.bind_prompt(session.token, chat_id=session.chat_id,
        actor_id=session.actor_id, message_id=preview.id)


@bot.on_message(filters.private & filters.incoming, group=2)
async def connected_preset_action_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None or int(message.chat.id) != int(actor.id): return
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"music_preset_apply", "music_preset_delete"}: return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Preset action cancelled; nothing changed.")
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id: return
    result = await interaction_engine.capture(session.token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=session.target_chat_id,
        reply_to_message_id=getattr(reply, "id", None), value=text.casefold())
    if result.status == "invalid":
        return await client.send_message(interaction_chat_id, "Reply <code>PREVIEW</code> to continue or <code>/cancel</code> to stop.")
    if result.status != "preview": return
    try:
        await _send_connected_preset_action_preview(client, result.session)
    except ValueError as error:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, str(error))
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Could not render preset preview; nothing changed.")


@bot.on_callback_query(filters.regex(r"^preset_action_(?:edit|save|cancel):[A-Za-z0-9_-]{1,24}$"))
async def connected_preset_action_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) != "private" or int(message.chat.id) != int(actor.id):
        return await query.answer("This preset action is unavailable.", show_alert=True)
    action, token = str(query.data).split(":", 1)
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"music_preset_apply", "music_preset_delete"}:
        return await query.answer("This preset action expired or is not yours. No change was made.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if action.endswith("cancel"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; no preset or queue change was made.")
        return await rich_edit(message, "Preset action cancelled. No change was made.", reply_markup=None)
    if action.endswith("edit"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        screen = _screen(target_chat_id, "presets", connected_dm=True)
        await query.answer("Choose the preset/action again to edit the draft.")
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)

    async def authorize(target_id, user_id):
        from videl.app.connections import connected_target
        _, error = await connected_target(client, user_id, expected_chat_id=target_id)
        return not error

    async def save(snapshot):
        from videl.utils import settings_store
        from videl.utils.music_presets import get, normalize, remove
        try:
            settings_store.check(target_chat_id, snapshot.revision)
            saved = normalize(base.get_setting(target_chat_id, "music_session_presets", []))
            selected = get(saved, snapshot.values["preset_index"])
            if selected is None or selected != snapshot.values["preset"]:
                return False
        except Exception:
            return False
        if snapshot.workflow == "music_preset_delete":
            try:
                updated = remove(saved, snapshot.values["preset_index"])
            except ValueError:
                return False
            if not base.set_setting(target_chat_id, "music_session_presets", updated,
                                    expected_revision=snapshot.revision):
                return False
            try:
                from videl.utils.audit import record_bot
                await asyncio.to_thread(record_bot, target_chat_id, "settings",
                    action="music_preset_delete", detail="saved preset deleted", actor=actor_id)
            except Exception: pass
            return True

        from videl.core import player, queue
        from videl.core.playback_state import lock
        import random
        desired = snapshot.values["preset"]
        async with lock(target_chat_id):
            try:
                settings_store.check(target_chat_id, snapshot.revision)
                latest = normalize(base.get_setting(target_chat_id, "music_session_presets", []))
                latest_selected = get(latest, snapshot.values["preset_index"])
                if latest_selected is None or latest_selected != desired:
                    return False
                tracks = queue.get_queue(target_chat_id)
                signature = tuple((id(song), repr(song)) for song in tracks)
                if (queue.mutation_revision(target_chat_id) != snapshot.values["queue_revision"]
                        or signature != snapshot.values["queue_signature"]
                        or player.get_loop(target_chat_id) != snapshot.values["live_state"]["loop"]
                        or bool(base.get_setting(target_chat_id, "music_shuffle_enabled", False)) != snapshot.values["live_state"]["shuffle"]
                        or bool(base.get_setting(target_chat_id, "music_requests_enabled", True)) != snapshot.values["live_state"]["requests"]
                        or bool(base.get_setting(target_chat_id, "music_approval_required", False)) != snapshot.values["live_state"]["approval"]):
                    return False
                reordered = list(tracks)
                if bool(desired.get("shuffle", False)):
                    upcoming = reordered[1:]
                    random.shuffle(upcoming)
                    reordered[1:] = upcoming
                old_tracks = list(tracks); old_loop = player.get_loop(target_chat_id)
                if bool(desired.get("shuffle", False)):
                    tracks[:] = reordered
                    queue.note_queue_mutation(target_chat_id)
                player.set_loop(target_chat_id, desired.get("loop", "off"))
                values = {"music_requests_enabled": bool(desired.get("requests", True)),
                          "music_approval_required": bool(desired.get("approval", False)),
                          "music_shuffle_enabled": bool(desired.get("shuffle", False))}
                persisted = base.set_settings(target_chat_id, values, expected_revision=snapshot.revision)
                if not persisted:
                    # Resolve an ambiguous response only if the exact CAS result
                    # is now visible. Otherwise restore the in-memory queue/loop.
                    try:
                        current_doc = base.get_settings(target_chat_id)
                        current_revision = settings_store.revision(target_chat_id)
                        persisted = (current_revision == snapshot.revision + 1
                            and all(current_doc.get(key) == value for key, value in values.items()))
                    except Exception:
                        persisted = False
                if not persisted:
                    if bool(desired.get("shuffle", False)):
                        tracks[:] = old_tracks
                        queue.note_queue_mutation(target_chat_id)
                    player.set_loop(target_chat_id, old_loop)
                    return False
            except Exception:
                # Queue mutations are in-memory and can be rolled back while the
                # playback lock excludes competing transitions.
                try:
                    if "tracks" in locals() and "old_tracks" in locals() and bool(snapshot.values["preset"].get("shuffle", False)):
                        tracks[:] = old_tracks
                        queue.note_queue_mutation(target_chat_id)
                    if "old_loop" in locals(): player.set_loop(target_chat_id, old_loop)
                except Exception: pass
                return False
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot, target_chat_id, "settings",
                action="music_preset_apply", detail="saved preset applied", actor=actor_id)
        except Exception: pass
        return True

    outcome, _ = await interaction_engine.commit(token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id, message_id=message.id,
        authorize=authorize, save=save)
    if outcome == "saved":
        await query.answer("Preset applied." if session.workflow == "music_preset_apply" else "Preset deleted.")
        detail = "Preset applied. Current track is unchanged; upcoming tracks follow the preview." if session.workflow == "music_preset_apply" else "Preset deleted. The active queue was not changed."
        return await rich_edit(message, detail, reply_markup=None)
    messages = {"permission_denied": "Connection or current admin permission changed. No preset or queue change was made.",
                "save_failed": "Preset, settings, or queue changed, or persistence failed. Nothing was reported as complete; refresh and preview again.",
                "expired": "This preset action expired. No change was made.",
                "stale": "This preview is stale or already being confirmed.",
                "unauthorized": "This action does not belong to this admin or group."}
    return await query.answer(messages.get(outcome, "Preset action failed; no success was reported."), show_alert=True)


async def _preset_snapshot(chat_id: int) -> dict:
    from videl.core.player import get_loop
    return {"loop": get_loop(chat_id),
            "shuffle": bool(base.get_setting(chat_id, "music_shuffle_enabled", False)),
            "requests": bool(base.get_setting(chat_id, "music_requests_enabled", True)),
            "approval": bool(base.get_setting(chat_id, "music_approval_required", False))}


async def _start_connected_preset(client, interaction_chat_id: int, actor_id: int,
                                  target_chat_id: int, revision: int) -> None:
    from videl.utils.interactive_settings import Step, engine as interaction_engine
    session = await interaction_engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
        target_chat_id=target_chat_id, workflow="music_preset_create",
        steps=(Step("name", "Preset name", max_length=32),), revision=revision, timeout_seconds=600)
    try:
        prompt = await client.send_message(interaction_chat_id,
            "Reply with a preset name (1–32 characters). Send /cancel to stop.",
            reply_markup=ForceReply(selective=True))
        await interaction_engine.bind_prompt(session.token, chat_id=interaction_chat_id,
                                             actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


async def _send_connected_preset_preview(client, session) -> None:
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.utils.music_presets import add, normalize
    current = normalize(base.get_setting(session.target_chat_id, "music_session_presets", []))
    updated = add(current, session.values["name"], session.values["snapshot"])
    session.values["updated"] = updated
    item = updated[-1]
    text = ("<b>Queue preset preview</b>\nNothing has been saved yet.\n"
            f"Name: <b>{item['name']}</b>\nRepeat: {item['loop']}\nShuffle: {'On' if item['shuffle'] else 'Off'}\n"
            f"Member requests: {'On' if item['requests'] else 'Off'}\nApproval required: {'On' if item['approval'] else 'Off'}")
    markup = InlineKeyboardMarkup([[button("Edit", callback_data=f"preset_edit:{session.token}"),
        button("Confirm", callback_data=f"preset_save:{session.token}", style="primary"),
        button("Cancel", callback_data=f"preset_cancel:{session.token}", style="danger")]])
    preview = await client.send_message(session.chat_id, text, reply_markup=markup)
    from videl.utils.interactive_settings import engine as interaction_engine
    await interaction_engine.bind_prompt(session.token, chat_id=session.chat_id,
        actor_id=session.actor_id, message_id=preview.id)


@bot.on_message(filters.private & filters.incoming, group=2)
async def connected_preset_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None or int(message.chat.id) != int(actor.id): return
    from videl.utils.interactive_settings import engine as interaction_engine
    actor_id = int(actor.id); interaction_chat_id = int(message.chat.id)
    session = await interaction_engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "music_preset_create": return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Preset creation cancelled; nothing was saved.")
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id: return
    from videl.utils.music_presets import add, normalize
    try:
        snapshot = await _preset_snapshot(session.target_chat_id)
        add(normalize(base.get_setting(session.target_chat_id, "music_session_presets", [])), text, snapshot)
    except ValueError as error:
        return await client.send_message(interaction_chat_id, str(error) + " Reply to the prompt again or /cancel.")
    except Exception:
        return await client.send_message(interaction_chat_id, "Could not read current playback settings; nothing was saved.")
    result = await interaction_engine.capture(session.token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=session.target_chat_id,
        reply_to_message_id=getattr(reply, "id", None), value=text)
    if result.status == "invalid":
        return await client.send_message(interaction_chat_id, result.error or "Invalid preset name.")
    if result.status != "preview": return
    result.session.values["snapshot"] = snapshot
    try:
        await _send_connected_preset_preview(client, result.session)
    except ValueError as error:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, str(error))
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Could not render preset preview; nothing was saved.")


@bot.on_callback_query(filters.regex(r"^preset_(?:edit|save|cancel):[A-Za-z0-9_-]{1,24}$"))
async def connected_preset_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) != "private" or int(message.chat.id) != int(actor.id):
        return await query.answer("This preset action is unavailable.", show_alert=True)
    action, token = str(query.data).split(":", 1)
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "music_preset_create":
        return await query.answer("This preset edit expired or is not yours.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if action.endswith("cancel"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved.")
        return await rich_edit(message, "Preset creation cancelled. Nothing was saved.", reply_markup=None)
    if action.endswith("edit"):
        edited = await interaction_engine.edit_again(token, chat_id=interaction_chat_id,
            actor_id=actor_id, message_id=message.id)
        if edited is None: return await query.answer("This preview is no longer active.", show_alert=True)
        edited.values.pop("updated", None); edited.values.pop("name", None); edited.values.pop("snapshot", None)
        try:
            prompt = await client.send_message(interaction_chat_id,
                "Reply with a preset name (1–32 characters). Send /cancel to stop.",
                reply_markup=ForceReply(selective=True))
            await interaction_engine.bind_prompt(token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=prompt.id)
        except Exception:
            await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer("Could not restart editor; nothing was saved.", show_alert=True)
        return await query.answer("Reply to the private prompt to edit again.")

    async def authorize(target_id, user_id):
        from videl.app.connections import connected_target
        _, error = await connected_target(client, user_id, expected_chat_id=target_id)
        return not error

    async def save(snapshot):
        return bool(base.set_setting(target_chat_id, "music_session_presets", snapshot.values["updated"],
                                     expected_revision=snapshot.revision))

    outcome, _ = await interaction_engine.commit(token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id, message_id=message.id,
        authorize=authorize, save=save)
    if outcome == "saved":
        await query.answer("Queue preset saved.")
        return await rich_edit(message, "Queue preset saved.", reply_markup=None)
    messages = {"permission_denied": "Connection or group-admin access changed. Nothing was saved.",
                "save_failed": "Could not save the preset; refresh settings and retry.",
                "expired": "This edit expired. Nothing was saved.",
                "stale": "This preview is stale or already being confirmed.",
                "unauthorized": "This action does not belong to this group or admin."}
    return await query.answer(messages.get(outcome, "Could not save preset."), show_alert=True)


async def _start_connected_blocklist(client, interaction_chat_id: int, actor_id: int, target_chat_id: int,
                                    revision: int, operation: str, value) -> None:
    from videl.utils.interactive_settings import Step, engine as interaction_engine
    workflow = "music_blocklist_add" if operation == "add" else "music_blocklist_remove"
    steps = (Step("value", "Blocklist entry", max_length=100),) if operation == "add" else (Step("index", "Entry number", kind="number", minimum=1, maximum=50),)
    if operation == "remove":
        value = int(value)
        items = __import__("videl.utils.track_blocklist", fromlist=["normalize"]).normalize(
            base.get_setting(target_chat_id, "music_track_blocklist", []))
        if not 1 <= value <= len(items):
            raise RuntimeError("That entry is no longer available. Refresh the blocklist.")
        steps = (Step("index", "Entry number", kind="number", minimum=value, maximum=value),)
    session = await interaction_engine.begin(chat_id=interaction_chat_id, actor_id=actor_id,
        target_chat_id=target_chat_id, workflow=workflow, steps=steps, revision=revision, timeout_seconds=600)
    session.values["operation"] = operation
    if operation == "add":
        session.values["kind"] = value
        prompt_text = f"Reply with the {value} name to block (1–100 characters). /cancel stops without saving."
    else:
        items = __import__("videl.utils.track_blocklist", fromlist=["normalize"]).normalize(
            base.get_setting(target_chat_id, "music_track_blocklist", []))
        prompt_text = "Reply with the entry number to remove:\n" + "\n".join(
            f"{i}. {entry['kind'].title()}: {entry['value']}" for i, entry in enumerate(items, 1)) + "\n/cancel stops without saving."
    try:
        prompt = await client.send_message(interaction_chat_id, prompt_text,
                                          reply_markup=ForceReply(selective=True))
        await interaction_engine.bind_prompt(session.token, chat_id=interaction_chat_id,
                                             actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise


async def _send_connected_blocklist_preview(client, session) -> None:
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.utils.track_blocklist import add, normalize, remove
    current = normalize(base.get_setting(session.target_chat_id, "music_track_blocklist", []))
    if session.workflow == "music_blocklist_add":
        updated = add(current, session.values["kind"], session.values["value"])
    else:
        updated = remove(current, session.values["index"])
    session.values["updated"] = updated
    rows = [[button("Edit", callback_data=f"blocklist_edit:{session.token}"),
             button("Confirm", callback_data=f"blocklist_save:{session.token}", style="primary"),
             button("Cancel", callback_data=f"blocklist_cancel:{session.token}", style="danger")]]
    text = "<b>Music blocklist preview</b>\nNothing has been saved.\n"
    text += "\n".join(f"{i}. {item['kind'].title()}: {item['value']}" for i, item in enumerate(updated, 1)) or "No blocked entries."
    preview = await client.send_message(session.chat_id, text,
        reply_markup=InlineKeyboardMarkup(rows))
    from videl.utils.interactive_settings import engine as interaction_engine
    await interaction_engine.bind_prompt(session.token, chat_id=session.chat_id,
        actor_id=session.actor_id, message_id=preview.id)


@bot.on_message(filters.private & filters.incoming, group=2)
async def connected_blocklist_reply(client, message):
    actor = getattr(message, "from_user", None)
    if actor is None or int(message.chat.id) != int(actor.id):
        return
    from videl.utils.interactive_settings import engine as interaction_engine
    actor_id = int(actor.id); interaction_chat_id = int(message.chat.id)
    session = await interaction_engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"music_blocklist_add", "music_blocklist_remove"}:
        return
    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Blocklist edit cancelled; nothing was saved.")
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id:
        return
    target_chat_id = int(session.target_chat_id)
    value = text
    result = await interaction_engine.capture(session.token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id,
        reply_to_message_id=getattr(reply, "id", None), value=value)
    if result.status == "invalid":
        return await client.send_message(interaction_chat_id, result.error or "Invalid value. Reply to the prompt again.")
    if result.status != "preview":
        return
    try:
        await _send_connected_blocklist_preview(client, result.session)
    except ValueError as error:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, str(error))
    except Exception:
        await interaction_engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Could not render the preview; nothing was saved.")


@bot.on_callback_query(filters.regex(r"^blocklist_(?:edit|save|cancel):[A-Za-z0-9_-]{1,24}$"))
async def connected_blocklist_callback(client, query):
    message = getattr(query, "message", None); actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) != "private" or int(message.chat.id) != int(actor.id):
        return await query.answer("This blocklist action is unavailable.", show_alert=True)
    action, token = str(query.data).split(":", 1)
    from videl.utils.interactive_settings import engine as interaction_engine
    interaction_chat_id = int(message.chat.id); actor_id = int(actor.id)
    session = await interaction_engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"music_blocklist_add", "music_blocklist_remove"}:
        return await query.answer("This blocklist edit expired or is not yours.", show_alert=True)
    target_chat_id = int(session.target_chat_id)
    if action.endswith("cancel"):
        await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved.")
        return await rich_edit(message, "Blocklist edit cancelled. Nothing was saved.", reply_markup=None)
    if action.endswith("edit"):
        edited = await interaction_engine.edit_again(token, chat_id=interaction_chat_id,
            actor_id=actor_id, message_id=message.id)
        if edited is None:
            return await query.answer("This preview is no longer active.", show_alert=True)
        edited.values.pop("updated", None)
        try:
            if edited.workflow == "music_blocklist_add": prompt_text = f"Reply with the {edited.values['kind']} name to block. /cancel stops."
            else: prompt_text = "Reply with the entry number to remove. /cancel stops."
            prompt = await client.send_message(interaction_chat_id, prompt_text, reply_markup=ForceReply(selective=True))
            await interaction_engine.bind_prompt(token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=prompt.id)
        except Exception:
            await interaction_engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer("Could not restart editor; nothing was saved.", show_alert=True)
        return await query.answer("Reply to the private prompt to edit again.")

    async def authorize(target_id, user_id):
        from videl.app.connections import connected_target
        _, error = await connected_target(client, user_id, expected_chat_id=target_id)
        if error: return False
        member = await client.get_chat_member(target_id, user_id)
        status = str(getattr(getattr(member, "status", None), "value", getattr(member, "status", None))).casefold()
        return status in {"owner", "administrator"}

    async def save(snapshot):
        return bool(base.set_setting(target_chat_id, "music_track_blocklist", snapshot.values["updated"],
                                     expected_revision=snapshot.revision))

    outcome, _ = await interaction_engine.commit(token, chat_id=interaction_chat_id,
        actor_id=actor_id, target_chat_id=target_chat_id, message_id=message.id,
        authorize=authorize, save=save)
    if outcome == "saved":
        await query.answer("Blocklist saved.")
        return await rich_edit(message, "Blocklist updated and saved.", reply_markup=None)
    messages = {"permission_denied": "Connection or group-admin access changed. Nothing was saved.",
                "save_failed": "Could not save the blocklist; refresh settings and retry.",
                "expired": "This edit expired. Nothing was saved.",
                "stale": "This preview is stale or already being confirmed.",
                "unauthorized": "This action does not belong to this group or admin."}
    return await query.answer(messages.get(outcome, "Could not save blocklist."), show_alert=True)


async def _bot_can_delete_messages(client, chat_id: int) -> bool:
    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
        member = await client.get_chat_member(chat_id, int(bot_user.id))
        status = str(getattr(getattr(member, "status", None), "value", getattr(member, "status", None))).casefold()
        if status == "owner":
            return True
        privileges = getattr(member, "privileges", None)
        return status == "administrator" and bool(getattr(privileges, "can_delete_messages", False))
    except Exception:
        return False


async def _send_antispam_prompt(client, session) -> None:
    step = session.current_step
    if step is None:
        return
    stored_enabled = bool(base.get_setting(session.target_chat_id, "antispam", False))
    from videl.plugins.locks import antispam_config
    stored_limit, stored_window = antispam_config(session.target_chat_id)
    enabled = session.values.get("enabled", "on" if stored_enabled else "off") == "on"
    limit = session.values.get("limit", stored_limit)
    window = session.values.get("window", stored_window)
    prompts = {
        "enabled": f"Anti-flood is currently {'On' if enabled else 'Off'}. It deletes messages above the burst limit. Reply <code>on</code> or <code>off</code>.",
        "limit": f"Current burst limit: {limit}. Reply with a whole number from 3 to 30.",
        "window": f"Current time window: {window} seconds. Reply with a whole number from 3 to 60.",
    }
    if step.key == "enabled" and step.choices == ("off",):
        prompts["enabled"] += " The bot currently lacks Delete Messages permission, so only Off is available."
    prompt = await client.send_message(session.chat_id, prompts[step.key], reply_markup=ForceReply(selective=True))
    await engine.bind_prompt(session.token, chat_id=session.chat_id, actor_id=session.actor_id, message_id=prompt.id)


async def _start_antispam_editor(client, chat_id: int, actor_id: int, revision: int,
                                *, interaction_chat_id: int | None = None) -> str:
    interaction_chat_id = int(interaction_chat_id if interaction_chat_id is not None else chat_id)
    can_delete = await _bot_can_delete_messages(client, chat_id)
    enabled_choices = ("on", "off") if can_delete else ("off",)
    session = await engine.begin(
        chat_id=interaction_chat_id, actor_id=actor_id, target_chat_id=chat_id, workflow="antispam",
        revision=revision,
        steps=(Step("enabled", "Enable anti-flood?", kind="selection", choices=enabled_choices),
               Step("limit", "Message burst limit", kind="number", minimum=3, maximum=30),
               Step("window", "Time window in seconds", kind="number", minimum=3, maximum=60)),
        timeout_seconds=600,
    )
    try:
        await _send_antispam_prompt(client, session)
    except Exception:
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        raise RuntimeError("Could not send anti-flood settings prompts; nothing changed.") from None
    return "Reply to each prompt. Settings remain unchanged until the preview is confirmed."


def _antispam_preview_keyboard(token: str):
    return InlineKeyboardMarkup([[
        button("Edit Again", callback_data=f"antispam_edit:{token}:edit"),
        button("Save", callback_data=f"antispam_edit:{token}:save", style="primary"),
        button("Cancel", callback_data=f"antispam_edit:{token}:cancel", style="danger"),
    ]])


@bot.on_message(filters.incoming, group=3)
async def antispam_settings_message(client, message):
    user = getattr(message, "from_user", None)
    if not user:
        return
    kind = base.chat_kind(message)
    interaction_chat_id, actor_id = int(message.chat.id), int(user.id)
    connected_dm = kind == "private" and interaction_chat_id == actor_id
    if kind not in {"group", "supergroup"} and not connected_dm:
        return
    session = await engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "antispam":
        return
    target_chat_id = int(session.target_chat_id)
    if not connected_dm and target_chat_id != interaction_chat_id:
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return
    if connected_dm:
        from videl.app.connections import connected_target
        _, connection_error = await connected_target(client, actor_id, expected_chat_id=target_chat_id)
        if connection_error:
            await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
            await client.send_message(interaction_chat_id, connection_error)
            return
    try:
        member = await client.get_chat_member(target_chat_id, actor_id)
        status = str(getattr(getattr(member, "status", None), "value",
                             getattr(member, "status", None))).casefold()
        if status not in {"owner", "administrator"}:
            await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
            await client.send_message(interaction_chat_id, "Current group-admin permission could not be verified. Nothing was saved.")
            return
    except Exception:
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        await client.send_message(interaction_chat_id, "Could not verify current group-admin status. Nothing was saved.")
        return

    text = str(getattr(message, "text", "") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].casefold() if text else ""
    if command == "/cancel":
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        await client.send_message(interaction_chat_id, "Anti-flood editing cancelled. Nothing was saved.")
        return
    if getattr(getattr(message, "reply_to_message", None), "id", None) != session.expected_message_id:
        return
    step = session.current_step
    value = text.casefold() if step and step.kind == "selection" else text
    result = await engine.capture(session.token, chat_id=interaction_chat_id, actor_id=actor_id,
                                  target_chat_id=target_chat_id,
                                  reply_to_message_id=getattr(getattr(message, "reply_to_message", None), "id", None),
                                  value=value)
    if result.status == "invalid":
        await _send_antispam_prompt(client, result.session)
        await client.send_message(interaction_chat_id, result.error or "That value is invalid.")
        return
    if result.status in {"stale", "expired", "unauthorized"}:
        return
    if result.status == "accepted":
        await _send_antispam_prompt(client, result.session)
        return
    if result.status != "preview":
        return
    enabled = result.session.values["enabled"] == "on"
    preview = await client.send_message(
        interaction_chat_id,
        heading("Anti-flood settings preview", 3)
        + table([("Status", "On" if enabled else "Off"),
                 ("Burst limit", f"{result.session.values['limit']} messages"),
                 ("Window", f"{result.session.values['window']} seconds")])
        + body("No settings have changed yet. Confirm to save these values."),
        reply_markup=_antispam_preview_keyboard(result.session.token),
    )
    await engine.bind_prompt(result.session.token, chat_id=interaction_chat_id,
                             actor_id=actor_id, message_id=preview.id)


@bot.on_callback_query(filters.regex(r"^antispam_edit:[A-Za-z0-9_-]{1,24}:(?:edit|save|cancel)$"))
async def antispam_settings_callback(client, query):
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or actor is None:
        await query.answer("This anti-flood edit is unavailable.", show_alert=True)
        return
    kind = base.chat_kind(message)
    interaction_chat_id, actor_id = int(message.chat.id), int(actor.id)
    connected_dm = kind == "private" and interaction_chat_id == actor_id
    if kind not in {"group", "supergroup"} and not connected_dm:
        await query.answer("Open anti-flood settings in the connected group or your private chat.", show_alert=True)
        return
    _, token, action = str(query.data).split(":")
    session = await engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow != "antispam":
        await query.answer("This anti-flood edit expired or belongs to another admin.", show_alert=True)
        return
    target_chat_id = int(session.target_chat_id)
    if not connected_dm and target_chat_id != interaction_chat_id:
        await query.answer("This editor no longer matches the group.", show_alert=True)
        return
    if connected_dm:
        from videl.app.connections import connected_target
        _, connection_error = await connected_target(client, actor_id, expected_chat_id=target_chat_id)
        if connection_error:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            await query.answer(connection_error, show_alert=True)
            return
    try:
        member = await client.get_chat_member(target_chat_id, actor_id)
        status = str(getattr(getattr(member, "status", None), "value",
                             getattr(member, "status", None))).casefold()
        if status not in {"owner", "administrator"}:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            await query.answer("Current group-admin permission could not be verified. Nothing was saved.", show_alert=True)
            return
    except Exception:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Could not verify current group-admin status. Nothing was saved.", show_alert=True)
        return
    if action == "cancel":
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved.")
        return await rich_edit(message, heading("Anti-flood edit cancelled", 3) + body("No settings changed."), reply_markup=None)
    if action == "edit":
        edited = await engine.edit_again(token, chat_id=interaction_chat_id, actor_id=actor_id, message_id=int(message.id))
        if edited is None:
            await query.answer("This preview is no longer active.", show_alert=True)
            return
        await rich_edit(message, heading("Edit anti-flood settings again", 3) + body("Reply to the prompts; nothing is saved yet."), reply_markup=None)
        try:
            await _send_antispam_prompt(client, edited)
        except Exception:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            await query.answer("Could not restart the editor; nothing was saved.", show_alert=True)
            return
        await query.answer("Reply to the prompts to edit again.")
        return

    rights_denial = {"reason": None}
    async def authorize(target: int, user_id: int) -> bool:
        if target != target_chat_id or user_id != actor_id:
            rights_denial["reason"] = "admin"
            return False
        try:
            if connected_dm:
                from videl.app.connections import connected_target
                _, error = await connected_target(client, user_id, expected_chat_id=target)
                if error:
                    rights_denial["reason"] = "admin"
                    return False
            member_now = await client.get_chat_member(target, user_id)
            current_status = str(getattr(getattr(member_now, "status", None), "value",
                                         getattr(member_now, "status", None))).casefold()
            if current_status not in {"owner", "administrator"}:
                rights_denial["reason"] = "admin"
                return False
            if session.values["enabled"] == "on" and not await _bot_can_delete_messages(client, target):
                rights_denial["reason"] = "bot_rights"
                return False
            return True
        except Exception:
            rights_denial["reason"] = "admin"
            return False

    async def save(snapshot):
        from videl.utils.settings_store import write
        try:
            await asyncio.to_thread(write, snapshot.target_chat_id,
                                    {"antispam": snapshot.values["enabled"] == "on",
                                     "antispam_limit": snapshot.values["limit"],
                                     "antispam_window": snapshot.values["window"]},
                                    snapshot.revision)
            return True
        except Exception:
            return False

    outcome, _ = await engine.commit(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                     target_chat_id=target_chat_id, message_id=int(message.id),
                                     authorize=authorize, save=save)
    if outcome == "saved":
        from videl.plugins.locks import invalidate_antispam_config
        invalidate_antispam_config(target_chat_id)
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot, target_chat_id, "settings", action="antispam_interactive_saved",
                                    detail=f"enabled={session.values['enabled']}; limit={session.values['limit']}; window={session.values['window']}", actor=actor_id)
        except Exception:
            LOGGER.debug("Anti-flood audit write failed", exc_info=True)
        await query.answer("Anti-flood settings saved.")
        return await rich_edit(message, heading("Anti-flood settings saved", 3) + body("The selected values are now active."), reply_markup=None)
    if outcome == "permission_denied":
        if rights_denial["reason"] == "bot_rights":
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            await query.answer("Bot lacks Delete Messages permission. Anti-flood was not enabled.", show_alert=True)
            return await rich_edit(message, heading("Anti-flood not saved", 3) + body("No settings changed. Grant the bot Delete Messages permission and start again."), reply_markup=None)
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Current group-admin permission could not be verified. Nothing was saved.", show_alert=True)
        return await rich_edit(message, heading("Anti-flood not saved", 3) + body("Current admin status could not be verified."), reply_markup=None)
    if outcome == "save_failed":
        from videl.utils.settings_store import SettingsConflict, check
        try:
            check(target_chat_id, session.revision)
        except SettingsConflict:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            await query.answer("Settings changed elsewhere. No anti-flood values were saved.", show_alert=True)
            fresh = await _settings_screen(client, target_chat_id, "safety", connected_dm=connected_dm)
            return await rich_edit(message, fresh.html, reply_markup=fresh.keyboard)
        await query.answer("Could not save anti-flood settings; nothing was reported as saved. Retry from this preview.", show_alert=True)
        return
    if outcome == "expired":
        await query.answer("This anti-flood edit expired. Nothing was saved.", show_alert=True)
        return
    await query.answer("This anti-flood preview is no longer active.", show_alert=True)


COMMANDS=(
    Command("settings",settings,"Open the full group control center",category="manage",policy="group"),
)
