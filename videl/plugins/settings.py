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
from videl import bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit
from videl.utils.moderation import LOCK_TYPES

_TABS = {"home", "music", "welcome", "safety", "moderation", "retention", "blocklist", "presets", "sessions", "commands"}
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

def _nav(chat_id):
    return [[button("Overview",callback_data=f"settings:{chat_id}:tab:home"),button("Music",callback_data=f"settings:{chat_id}:tab:music"),button("Welcome",callback_data=f"settings:{chat_id}:tab:welcome")],
            [button("Protection",callback_data=f"settings:{chat_id}:tab:safety"),button("Moderation",callback_data=f"settings:{chat_id}:tab:moderation"),button("Retention",callback_data=f"settings:{chat_id}:tab:retention")],
            [button("Music blocklist",callback_data=f"settings:{chat_id}:tab:blocklist"),button("Queue presets",callback_data=f"settings:{chat_id}:tab:presets"),button("Listening sessions",callback_data=f"settings:{chat_id}:tab:sessions")],
            [button("Command manager",callback_data=f"settings:{chat_id}:tab:commands")]]

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


def _screen(chat_id, section="home", *, query="", category="all", page=0):
    markup=_nav(chat_id)
    if section=="home":
        fields=(("Member music requests","music_requests_enabled",True),("Music request approval","music_approval_required",False),("Shuffle new requests","music_shuffle_enabled",False),("Welcome messages","welcome_enabled",True),("Goodbye messages","goodbye_enabled",False),("New-member verification","captcha_enabled",False),("Anti-flood","antispam",False),("Gemini Guardian assistance","gemini_guardian_enabled",False))
        text=heading("Full group settings",3)+body("Choose a section. Only current group admins can change settings.")+table([(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields])+body("Advanced text and custom configuration remain available through their existing commands.")
    elif section in _TOGGLES:
        title={"music":"Music","welcome":"Welcome & onboarding","safety":"Protection"}[section]
        description={"music":"Members can request tracks when enabled. Approval sends new requests to admin review; use /requests to review.","welcome":"Control welcome, goodbye and verification flows. Edit content with /setwelcome, /setgoodbye, /setrules and /setfaq.","safety":"Configure content locks, anti-flood (custom thresholds via /antispam) and raid mode. Gemini Guardian is off by default. When enabled, /faqassist sends the question and selected FAQ/rules/text notes; admin /safetycheck sends minimized replied-to text (URL hosts only); /guardiansummary sends aggregate counts. These are sent to Google Gemini; no result takes action."}[section]
        fields=_TOGGLES[section]
        rows=[(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields]
        if section=="safety":
            from videl.plugins.locks import antispam_config
            flood_limit, flood_window = antispam_config(chat_id)
            rows.append(("Anti-flood threshold", f"{flood_limit} messages / {flood_window}s · set with /antispam"))
        if section=="music":
            dj=base.get_setting(chat_id,"music_dj_session",{}); rows.append(("Temporary DJ",str(dj.get("user_id")) if isinstance(dj,dict) and dj.get("user_id") else "None · use /dj"))
        text=heading(title,3)+body(description)+table(rows)
        markup += [_switch(chat_id,key,label,default) for label,key,default in fields]
        if section=="safety":
            for kind in LOCK_TYPES:
                key="lock_forwards" if kind=="forward" else f"lock_{kind}"
                markup.append(_switch(chat_id,key,f"Lock {kind}"))
            raid=base.get_setting(chat_id,"raid_mode",{}); enabled=bool(raid.get("enabled")) if isinstance(raid,dict) else False
            markup.append([button("Raid mode"),button("On",callback_data=f"settings:{chat_id}:raid:on",style="success" if enabled else None),button("Off",callback_data=f"settings:{chat_id}:raid:off",style="danger" if not enabled else None)])
    elif section=="moderation":
        try: threshold=int(base.get_setting(chat_id,"warn_threshold",3) or 3)
        except (TypeError,ValueError): threshold=3
        text=heading("Moderation",3)+body("Choose the active-warning threshold. The configured escalation action is unchanged.")+table([("Warning threshold",str(threshold))])
        markup.append([button(f"{n} warnings",callback_data=f"settings:{chat_id}:warn_threshold:{n}",style="success" if n==threshold else None) for n in (2,3,5,10)])
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
        text=heading("Music track & artist blocklist",3)+body("Entries are matched case-insensitively against track titles and available artist metadata before a request enters the queue. Up to 50 entries, 100 characters each.")+table([(f"{i}. {item['kind'].title()}",item["value"]) for i,item in enumerate(items,1)] if items else [("Blocked entries","None")])+body("Add prompts and replies are visible in the group.")
        markup.append([button("＋ Block track",callback_data=f"settings:{chat_id}:blocklist:add:track"),button("＋ Block artist",callback_data=f"settings:{chat_id}:blocklist:add:artist")])
        for i,item in enumerate(items,1): markup.append([button(f"Remove {i}: {item['value'][:32]}",callback_data=f"settings:{chat_id}:blocklist:remove:{i}",style="danger")])
    elif section=="presets":
        from videl.utils.music_presets import normalize as normalize_presets
        presets=normalize_presets(base.get_setting(chat_id,"music_session_presets",[]))
        text=heading("Queue session presets",3)+body("Save named snapshots of repeat, shuffle, member-request and approval settings. Applying a preset updates those settings and shuffles the current upcoming queue when shuffle is enabled.")
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
            protected={"start","help","commands","id","ping","settings","setup","permissions"}
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
    return Screen(text,_tag_keyboard(InlineKeyboardMarkup(markup),chat_id))

async def settings(ctx):
    if base.chat_kind(ctx.message) not in {"group","supergroup"}: raise CommandError("Open <code>/settings</code> in the group you want to configure.")
    chat_id=int(ctx.message.chat.id)
    arguments=str(getattr(ctx.command,"arguments","") or "").strip()
    if arguments.casefold().startswith("commands"):
        query=arguments[len("commands"):].strip()[:40]
        return _screen(chat_id,"commands",query=query)
    return _screen(chat_id)

_PATTERN=r"^settings:-?[0-9]{1,20}:(?:tab:(?:home|music|welcome|safety|moderation|retention|blocklist|presets|sessions|commands)|commands:(?:all|manage|music|tools):[0-9]{1,3}|cmd:[a-z][a-z0-9_]{0,31}:(?:on|off)|(?:music_requests_enabled|music_approval_required|welcome_enabled|goodbye_enabled|captcha_enabled|antispam|gemini_guardian_enabled|lock_[a-z_]+):(?:on|off)|raid:(?:on|off)|warn_threshold:(?:2|3|5|10)|retention:[a-z_]+:(?:30|90|180|365|off)|blocklist:(?:add:(?:track|artist)|remove:[1-9][0-9]?)|preset:(?:save|apply:[1-9][0-9]?|delete:[1-9][0-9]?)|session:(?:schedule|cancel:[A-Za-z0-9]+)|reset:(?:music|welcome|safety|moderation|blocklist|presets)|resetconfirm:(?:music|welcome|safety|moderation|blocklist|presets):[a-f0-9]{12}|refresh):v[0-9]{1,12}$"
@bot.on_callback_query(filters.regex(_PATTERN))
async def settings_callback(client,query):
    message=getattr(query,"message",None); actor=getattr(query,"from_user",None)
    if message is None or actor is None or base.chat_kind(message) not in {"group","supergroup"}: return await query.answer("Open settings in the group.",show_alert=True)
    try:
        parts=str(query.data).split(":")
        marker=parts.pop()
        if not marker.startswith("v") or not marker[1:].isdecimal(): raise ValueError
        expected_revision=int(marker[1:])
        chat_id=int(parts[1])
        if chat_id!=int(message.chat.id): return await query.answer("These settings belong to another group.",show_alert=True)
        key=value=None; section="home"; category="all"; page=0
        if len(parts)==4 and parts[2]=="tab" and parts[3] in _TABS: section=parts[3]
        elif len(parts)==5 and parts[2]=="commands" and parts[3] in {"all","manage","music","tools"} and parts[4].isdecimal():
            section,category,page="commands",parts[3],min(int(parts[4]),999)
        elif len(parts)==5 and parts[2]=="cmd" and parts[4] in {"on","off"}:
            key,value,section="__command_toggle__",(parts[3],parts[4]=="on"),"commands"
        elif len(parts)==4 and parts[2] in ({k for values in _TOGGLES.values() for _,k,_ in values}|_LOCK_KEYS) and parts[3] in {"on","off"}:
            key,value=parts[2],parts[3]=="on"; section="safety" if key in {"antispam", "gemini_guardian_enabled"} or key in _LOCK_KEYS else ("music" if key.startswith("music_") else "welcome")
        elif len(parts)==4 and parts[2]=="raid" and parts[3] in {"on","off"}:
            from videl.utils.raid import normalize
            value=normalize(base.get_setting(chat_id,"raid_mode",{})); value["enabled"]=parts[3]=="on"; key,section="raid_mode","safety"
        elif len(parts)==4 and parts[2]=="warn_threshold" and parts[3] in {"2","3","5","10"}: key,value,section="warn_threshold",int(parts[3]),"moderation"
        elif len(parts)==5 and parts[2]=="retention":
            from videl.utils.retention import ALLOWED_DAYS,CATEGORIES
            cat=parts[3]; days=None if parts[4]=="off" else int(parts[4])
            if cat not in CATEGORIES or (days is not None and days not in ALLOWED_DAYS): raise ValueError
            key,value,section="__retention__",(cat,days),"retention"
        elif len(parts)==5 and parts[2]=="blocklist" and parts[3]=="add" and parts[4] in {"track","artist"}: key,value,section="__prompt__",parts[4],"blocklist"
        elif len(parts)==5 and parts[2]=="blocklist" and parts[3]=="remove" and parts[4].isdecimal(): key,value,section="__remove__",int(parts[4]),"blocklist"
        elif len(parts)==4 and parts[2]=="session" and parts[3]=="schedule": key,value,section="__session_schedule__","session","sessions"
        elif len(parts)==5 and parts[2]=="session" and parts[3]=="cancel": key,value,section="__session_cancel__",parts[4],"sessions"
        elif len(parts)==4 and parts[2]=="reset" and parts[3] in _RESET_DEFAULTS: key,value,section="__reset_preview__",parts[3],parts[3]
        elif len(parts)==5 and parts[2]=="resetconfirm" and parts[3] in _RESET_DEFAULTS and len(parts[4])==12: key,value,section="__reset_confirm__",(parts[3],parts[4]),parts[3]
        elif len(parts)==4 and parts[2]=="preset" and parts[3]=="save": key,value,section="__preset_save__","preset","presets"
        elif len(parts)==5 and parts[2]=="preset" and parts[3] in {"apply","delete"} and parts[4].isdecimal(): key,value,section=f"__preset_{parts[3]}__",int(parts[4]),"presets"
        elif len(parts)==3 and parts[2]=="refresh": pass
        else: raise ValueError
    except (TypeError,ValueError,IndexError): return await query.answer("That settings button is invalid.",show_alert=True)
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
        fresh=_screen(chat_id,section,category=category,page=page)
        return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
    if key == "gemini_guardian_enabled" and value:
        from videl.utils.gemini import configured
        if not configured():
            await query.answer("Gemini is not configured; this option remains off.", show_alert=True)
            fresh = _screen(chat_id, section, category=category, page=page)
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
            fresh=_screen(chat_id,reset_category)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        if reset_category=="safety":
            from videl.utils.raid import clear
            clear(chat_id)
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot,chat_id,"settings",action="settings_reset",detail=f"category={reset_category}; keys={','.join(defaults)}",actor=int(actor.id))
        except Exception: pass
        await query.answer("Section reset and audited.")
        fresh=_screen(chat_id,reset_category)
        return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
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
            fresh=_screen(chat_id,section,category=category,page=page)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        name,enable=value
        from videl.utils.command_catalog import commands as registered_commands
        from videl.utils.db import disable_cmd,enable_cmd,get_db
        protected={"start","help","commands","id","ping","settings","setup","permissions"}
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
            fresh=_screen(chat_id,section,category=category,page=page)
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
            fresh=_screen(chat_id,section,category=category,page=page)
            return await rich_edit(message,fresh.html,reply_markup=fresh.keyboard)
        saved=await asyncio.to_thread(save,get_db(),chat_id,cat,days)
        if saved is None: return await query.answer("Retention could not be saved.",show_alert=True)
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
    screen=_screen(chat_id,section,category=category,page=page); await rich_edit(message,screen.html,reply_markup=screen.keyboard)

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

COMMANDS=(
    Command("settings",settings,"Open the full group control center",category="manage",policy="group"),
    Command("setup",settings,"Alias for /settings; open group settings",category="manage",policy="group"),
)
