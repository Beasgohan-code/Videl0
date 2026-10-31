# Videl © 2026 | Beasgohan-code
"""Inline hub for common group settings."""
from __future__ import annotations
import asyncio
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

_TABS = {"home", "music", "welcome", "safety", "moderation", "retention", "blocklist", "presets", "sessions"}
_LOCK_KEYS = {f"lock_{kind}" for kind in LOCK_TYPES} | {"lock_forwards"}
_PROMPTS: dict[tuple[int, int], tuple[int, str, float]] = {}
_TOGGLES = {
 "music": (("Member requests", "music_requests_enabled", True), ("Admin approval", "music_approval_required", False), ("Shuffle new requests", "music_shuffle_enabled", False)),
 "welcome": (("Welcome messages", "welcome_enabled", True), ("Goodbye messages", "goodbye_enabled", False), ("New-member verification", "captcha_enabled", False)),
 "safety": (("Anti-flood", "antispam", False),),
}

def _switch(chat_id, key, label, default=False):
    enabled=bool(base.get_setting(chat_id,key,default))
    return [button(label),button("On",callback_data=f"settings:{chat_id}:{key}:on",style="success" if enabled else None),button("Off",callback_data=f"settings:{chat_id}:{key}:off",style="danger" if not enabled else None)]

def _nav(chat_id):
    return [[button("Overview",callback_data=f"settings:{chat_id}:tab:home"),button("Music",callback_data=f"settings:{chat_id}:tab:music"),button("Welcome",callback_data=f"settings:{chat_id}:tab:welcome")],
            [button("Protection",callback_data=f"settings:{chat_id}:tab:safety"),button("Moderation",callback_data=f"settings:{chat_id}:tab:moderation"),button("Retention",callback_data=f"settings:{chat_id}:tab:retention")],
            [button("Music blocklist",callback_data=f"settings:{chat_id}:tab:blocklist"),button("Queue presets",callback_data=f"settings:{chat_id}:tab:presets"),button("Listening sessions",callback_data=f"settings:{chat_id}:tab:sessions")]]

def _screen(chat_id, section="home"):
    markup=_nav(chat_id)
    if section=="home":
        fields=(("Member music requests","music_requests_enabled",True),("Music request approval","music_approval_required",False),("Shuffle new requests","music_shuffle_enabled",False),("Welcome messages","welcome_enabled",True),("Goodbye messages","goodbye_enabled",False),("New-member verification","captcha_enabled",False),("Anti-flood","antispam",False))
        text=heading("Full group settings",3)+body("Choose a section. Only current group admins can change settings.")+table([(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields])+body("Advanced text and custom configuration remain available through their existing commands.")
    elif section in _TOGGLES:
        title={"music":"Music","welcome":"Welcome & onboarding","safety":"Protection"}[section]
        description={"music":"Members can request tracks when enabled. Approval sends new requests to admin review; use /requests to review.","welcome":"Control welcome, goodbye and verification flows. Edit content with /setwelcome, /setgoodbye, /setrules and /setfaq.","safety":"Configure content locks, anti-flood and raid mode. Admins and approved members are exempt."}[section]
        fields=_TOGGLES[section]
        rows=[(label,"On" if base.get_setting(chat_id,key,default) else "Off") for label,key,default in fields]
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
    else: raise ValueError("Unknown settings section")
    markup.append([button("Refresh",callback_data=f"settings:{chat_id}:refresh")])
    return Screen(text,InlineKeyboardMarkup(markup))

async def settings(ctx):
    if base.chat_kind(ctx.message) not in {"group","supergroup"}: raise CommandError("Open <code>/settings</code> in the group you want to configure.")
    return _screen(int(ctx.message.chat.id))

_PATTERN=r"^settings:-?[0-9]{1,20}:(?:tab:(?:home|music|welcome|safety|moderation|retention|blocklist|presets|sessions)|(?:music_requests_enabled|music_approval_required|welcome_enabled|goodbye_enabled|captcha_enabled|antispam|lock_[a-z_]+):(?:on|off)|raid:(?:on|off)|warn_threshold:(?:2|3|5|10)|retention:[a-z_]+:(?:30|90|180|365|off)|blocklist:(?:add:(?:track|artist)|remove:[1-9][0-9]?)|preset:(?:save|apply:[1-9][0-9]?|delete:[1-9][0-9]?)|session:(?:schedule|cancel:[A-Za-z0-9]+)|refresh)$"
@bot.on_callback_query(filters.regex(_PATTERN))
async def settings_callback(client,query):
    message=getattr(query,"message",None); actor=getattr(query,"from_user",None)
    if message is None or actor is None or base.chat_kind(message) not in {"group","supergroup"}: return await query.answer("Open settings in the group.",show_alert=True)
    try:
        parts=str(query.data).split(":"); chat_id=int(parts[1])
        if chat_id!=int(message.chat.id): return await query.answer("These settings belong to another group.",show_alert=True)
        key=value=None; section="home"
        if len(parts)==4 and parts[2]=="tab" and parts[3] in _TABS: section=parts[3]
        elif len(parts)==4 and parts[2] in ({k for values in _TOGGLES.values() for _,k,_ in values}|_LOCK_KEYS) and parts[3] in {"on","off"}:
            key,value=parts[2],parts[3]=="on"; section="safety" if key=="antispam" or key in _LOCK_KEYS else ("music" if key.startswith("music_") else "welcome")
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
        elif len(parts)==4 and parts[2]=="preset" and parts[3]=="save": key,value,section="__preset_save__","preset","presets"
        elif len(parts)==5 and parts[2]=="preset" and parts[3] in {"apply","delete"} and parts[4].isdecimal(): key,value,section=f"__preset_{parts[3]}__",int(parts[4]),"presets"
        elif len(parts)==3 and parts[2]=="refresh": pass
        else: raise ValueError
    except (TypeError,ValueError,IndexError): return await query.answer("That settings button is invalid.",show_alert=True)
    try:
        member=await client.get_chat_member(chat_id,int(actor.id)); status=str(getattr(member.status,"value",member.status)).casefold()
        if status not in {"owner","administrator"}: return await query.answer("Only current group admins can change settings.",show_alert=True)
    except Exception: return await query.answer("I could not verify your current group-admin status.",show_alert=True)
    if key in {"__prompt__","__preset_save__","__session_schedule__"}:
        kind = value if key == "__prompt__" else ("preset" if key == "__preset_save__" else "session")
        prompt_text = ("Reply with a name for this preset (1–32 characters)." if kind == "preset" else ("Reply with YYYY-MM-DD HH:MM UTC | Session title. Example: 2026-11-05 19:30 UTC | Friday listening." if kind == "session" else f"Reply to this message with the {kind} name to block (up to 100 characters). This reply is visible in the group."))
        prompt=await client.send_message(chat_id,prompt_text,reply_markup=ForceReply(selective=True))
        expired=[key for key,item in _PROMPTS.items() if item[2] < monotonic()]
        for expired_key in expired: _PROMPTS.pop(expired_key,None)
        if len(_PROMPTS)>=500: _PROMPTS.pop(next(iter(_PROMPTS)),None)
        _PROMPTS[(chat_id,int(actor.id))]=(int(prompt.id),kind,monotonic()+300)
        await query.answer("Reply to the prompt to continue."); return
    if key=="__session_cancel__":
        from videl.utils.db import get_db
        from videl.utils.listening_sessions import cancel
        if not await asyncio.to_thread(cancel,get_db(),chat_id,value): return await query.answer("Session not found or already started.",show_alert=True)
        key=None
    if key in {"__preset_apply__","__preset_delete__"}:
        from videl.utils.music_presets import get as get_preset, normalize as normalize_presets, remove as remove_preset
        presets=normalize_presets(base.get_setting(chat_id,"music_session_presets",[]))
        preset=get_preset(presets,value)
        if preset is None: return await query.answer("That preset no longer exists.",show_alert=True)
        if key=="__preset_delete__":
            presets=remove_preset(presets,value)
            if not base.set_setting(chat_id,"music_session_presets",presets): return await query.answer("Preset could not be deleted.",show_alert=True)
        else:
            from videl.core import player,queue
            from videl.core.playback_state import lock
            import random
            values={"music_requests_enabled":bool(preset.get("requests",True)),"music_approval_required":bool(preset.get("approval",False)),"music_shuffle_enabled":bool(preset.get("shuffle",False))}
            if not base.set_setting(chat_id,values): return await query.answer("Preset could not be applied.",show_alert=True)
            async with lock(chat_id):
                player.set_loop(chat_id,preset.get("loop","off") if preset.get("loop") in {"off","one","all"} else "off")
                if values["music_shuffle_enabled"]:
                    items=queue.get_queue(chat_id)
                    upcoming=items[1:]
                    random.shuffle(upcoming)
                    items[1:]=upcoming
        key=None
    if key=="__remove__":
        from videl.utils.track_blocklist import normalize,remove
        try: value=remove(base.get_setting(chat_id,"music_track_blocklist",[]),value)
        except ValueError: return await query.answer("That entry is no longer available.",show_alert=True)
        key="music_track_blocklist"
    if key=="__retention__":
        from videl.utils.db import get_db
        from videl.utils.retention import save
        cat,days=value; saved=await asyncio.to_thread(save,get_db(),chat_id,cat,days)
        if saved is None: return await query.answer("Retention could not be saved.",show_alert=True)
    elif key and not base.set_setting(chat_id,key,value): return await query.answer("The setting could not be saved.",show_alert=True)
    if key:
        try:
            from videl.utils.audit import record_bot
            await asyncio.to_thread(record_bot,chat_id,"settings",action="group_setting",detail=f"{key}={value}",actor=int(actor.id))
        except Exception: pass
    await query.answer("Settings refreshed." if key is None else "Setting saved.")
    screen=_screen(chat_id,section); await rich_edit(message,screen.html,reply_markup=screen.keyboard)

@bot.on_message(filters.group & filters.text)
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
        if not base.set_setting(chat_id,"music_session_presets",presets): return await message.reply_text("The preset could not be saved.")
        await message.reply_text("Saved this group music preset. Open /settings → Queue presets to apply it.")
        return
    try:
        from videl.utils.track_blocklist import add
        current=base.get_setting(chat_id,"music_track_blocklist",[])
        updated=add(current,prompt[1],message.text or "")
    except ValueError as error: return await message.reply_text(str(error))
    if not base.set_setting(chat_id,"music_track_blocklist",updated): return await message.reply_text("The blocklist could not be saved.")
    try:
        from videl.utils.audit import record_bot
        await asyncio.to_thread(record_bot,chat_id,"settings",action="music_blocklist_add",detail=f"{prompt[1]} entry",actor=int(user.id))
    except Exception: pass
    await message.reply_text("Added to the group music blocklist. Open /settings → Music blocklist to review it.")

COMMANDS=(Command("settings",settings,"Open full group settings",category="manage",policy="group"),)
