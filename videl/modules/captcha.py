# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Captcha / Verification ✦ Perfect
#  Math + button — Richgram premium costume perfect
# --------------------------------------------------------------------------------

import asyncio, random, time
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button, rich_img, rich_send, rich_edit
from videl.utils.db import get_captcha, set_captcha
try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb="◍"):
        return fb

_HERO = "https://iili.io/n5ClDil.jpg"
def _hdr(t, lvl=3):
    return rich_heading(pe("orb","◍") + " " + t + " " + pe("spark","𖦹"), level=lvl)
def _hero():
    return rich_img(_HERO)

_PENDING = {}

def _gen_math():
    a = random.randint(1, 25)
    b = random.randint(1, 25)
    op = random.choice(["+", "-", "×"])
    if op == "+":
        ans = a + b
        expr = str(a) + " + " + str(b)
    elif op == "-":
        if a < b:
            a,b = b,a
        ans = a - b
        expr = str(a) + " − " + str(b)
    else:
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        ans = a * b
        expr = str(a) + " × " + str(b)
    return expr, ans

async def _kick_pending(chat_id, user_id, msg_id, reason):
    _PENDING.pop((chat_id,user_id), None)
    try:
        if msg_id:
            await bot.delete_messages(chat_id, msg_id)
    except Exception:
        pass
    try:
        await bot.ban_chat_member(chat_id, user_id)
    except Exception as e:
        LOGGER.debug("[captcha] kick fail: " + str(e))

@bot.on_message(filters.command(["captcha","welcome_captcha","verification"]) & filters.group & group_allowed & user_allowed)
async def captcha_cmd(_, m):
    if not await is_user_authorized(m):
        return
    args = (m.text or "").split()
    if len(args) == 1:
        cur = get_captcha(m.chat.id)
        body = _hero() + _hdr(sb("Captcha") + " • " + sc("verification"),2) + rich_kv_table([(pe("diamond","⬪") + " " + sc("status"), "<b>" + ("ON" if cur["enabled"] else "OFF") + "</b>"), (pe("target","◎") + " " + sc("mode"), "<code>" + rich_esc(cur["mode"]) + "</code>"), (pe("hex","⬢") + " " + sc("timeout"), "<code>" + str(cur["timeout"]) + "s</code>")], headers=[pe("spark","𖦹") + " " + sc("captcha config"), ""])
        body += rich_table([sc("command"), sc("action")], [("<code>/captcha on</code>", pe("check","✅") + " " + sc("enable verification")), ("<code>/captcha off</code>", pe("cross","❌") + " " + sc("disable")), ("<code>/captcha math</code>", pe("target","◎") + " " + sc("math puzzle") + " (" + pe("star","⭐️") + " " + sc("recommended") + ")"), ("<code>/captcha button</code>", pe("circle","⦿") + " " + sc("tap to verify")), ("<code>/captcha 90</code>", pe("hex","⬢") + " " + sc("set timeout 30–600s"))])
        body += rich_details(pe("info","ℹ️") + " " + sc("how it works"), rich_note(pe("line","⫶") + " " + sc("new members get muted + must solve captcha within timeout") + "<br>" + pe("line","⫶") + " " + sc("fail or timeout → kicked automatically") + "<br>" + pe("line","⫶") + " " + sc("approved users bypass captcha") + " " + pe("diamond","⬪")))
        body += "<p>" + rich_button(pe("check","✅") + " " + sc("enable"), callback_data="captcha:enable") + " " + rich_button(pe("cross","❌") + " " + sc("disable"), callback_data="captcha:disable", style="danger") + " " + rich_button(pe("target","◎") + " " + sc("math"), callback_data="captcha:mode:math") + " " + rich_button(pe("circle","⦿") + " " + sc("button"), callback_data="captcha:mode:button") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("check","✅") + " " + sc("enable"), callback_data="captcha:enable"), InlineKeyboardButton(pe("cross","❌") + " " + sc("disable"), callback_data="captcha:disable")],[InlineKeyboardButton(pe("target","◎") + " " + sc("math"), callback_data="captcha:mode:math"), InlineKeyboardButton(pe("circle","⦿") + " " + sc("button"), callback_data="captcha:mode:button")],[InlineKeyboardButton(pe("hex","⬢") + " 60s", callback_data="captcha:timeout:60"), InlineKeyboardButton(pe("hex","⬢") + " 120s", callback_data="captcha:timeout:120"), InlineKeyboardButton(pe("hex","⬢") + " 300s", callback_data="captcha:timeout:300")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    arg = args[1].lower()
    cur = get_captcha(m.chat.id)
    if arg in ("on","yes","enable","true"):
        set_captcha(m.chat.id, True, cur["mode"], cur["timeout"])
        return await rich_send(bot, m.chat.id, _hdr(pe("check","✅") + " " + sc("captcha enabled"),3) + rich_note(pe("diamond","⬪") + " " + sc("mode") + ": <code>" + rich_esc(cur["mode"]) + "</code> " + pe("hex","⬢") + " " + str(cur["timeout"]) + "s") + "<p>" + rich_button(pe("crown","👑") + " " + sc("test captcha"), callback_data="captcha:test") + "</p>")
    if arg in ("off","no","disable","false"):
        set_captcha(m.chat.id, False, cur["mode"], cur["timeout"])
        return await rich_send(bot, m.chat.id, _hdr(pe("cross","❌") + " " + sc("captcha disabled"),3))
    if arg in ("math","button"):
        set_captcha(m.chat.id, cur["enabled"], arg, cur["timeout"])
        return await rich_send(bot, m.chat.id, _hdr(pe("target","◎") + " " + sc("captcha mode"),3) + rich_kv_table([(pe("diamond","⬪") + " " + sc("mode"), "<code>" + rich_esc(arg) + "</code>")]))
    if arg.isdigit():
        t = int(arg)
        set_captcha(m.chat.id, cur["enabled"], cur["mode"], max(30, min(t, 600)))
        return await rich_send(bot, m.chat.id, _hdr(pe("hex","⬢") + " " + sc("timeout updated"),3) + rich_kv_table([(pe("hex","⬢") + " " + sc("timeout"), "<code>" + str(max(30, min(t,600))) + "s</code>")]))
    return await rich_send(bot, m.chat.id, _hdr(sc("usage"),3) + rich_note("<code>/captcha on/off/math/button/120</code>"))

@bot.on_callback_query(filters.regex(r"^captcha:"))
async def captcha_cbs(_, q):
    if not await is_user_authorized(q):
        return await q.answer(pe("warn","⚠️") + " " + sc("admin only"), show_alert=True)
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    data = (q.data or "").split(":")
    cur = get_captcha(chat_id)
    if data[1] == "enable":
        set_captcha(chat_id, True, cur["mode"], cur["timeout"])
        await q.answer(pe("check","✅") + " " + sc("captcha enabled"))
        try:
            await rich_edit(q.message, _hdr(pe("check","✅") + " " + sc("captcha enabled"),3) + rich_kv_table([(pe("diamond","⬪") + " " + sc("mode"), "<code>" + cur["mode"] + "</code>")]))
        except Exception:
            pass
    elif data[1] == "disable":
        set_captcha(chat_id, False, cur["mode"], cur["timeout"])
        await q.answer(pe("cross","❌") + " " + sc("disabled"))
        try:
            await rich_edit(q.message, _hdr(pe("cross","❌") + " " + sc("captcha disabled"),3))
        except Exception:
            pass
    elif data[1] == "mode":
        mode = data[2] if len(data) > 2 else "math"
        set_captcha(chat_id, cur["enabled"], mode, cur["timeout"])
        await q.answer(pe("target","◎") + " " + mode)
        try:
            await rich_edit(q.message, _hdr(pe("target","◎") + " " + sc("captcha mode"),3) + rich_kv_table([(pe("diamond","⬪") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>")]))
        except Exception:
            pass
    elif data[1] == "timeout":
        try:
            t = int(data[2])
            set_captcha(chat_id, cur["enabled"], cur["mode"], max(30,min(t,600)))
            await q.answer(pe("hex","⬢") + " " + data[2] + "s")
        except Exception:
            await q.answer(pe("warn","⚠️") + " " + sc("invalid"), show_alert=True)
        try:
            await rich_edit(q.message, _hdr(pe("hex","⬢") + " " + sc("timeout") + " • " + data[2] + "s",3))
        except Exception:
            pass
    else:
        await q.answer()

@bot.on_message(filters.new_chat_members & group_allowed, group=2)
async def captcha_on_join(_, m):
    chat_id = m.chat.id
    cap = get_captcha(chat_id)
    if not cap.get("enabled"):
        return
    mode = cap.get("mode","math")
    timeout = int(cap.get("timeout",120))
    for user in m.new_chat_members:
        if getattr(user, "is_bot", False):
            continue
        try:
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(chat_id, user.id, ChatPermissions(can_send_messages=False))
        except Exception:
            pass
        if mode == "math":
            expr, ans = _gen_math()
            opts = {ans}
            while len(opts) < 4:
                v = ans + random.randint(-8,8)
                if v != 0:
                    opts.add(v)
            opts = list(opts)
            random.shuffle(opts)
            rows = []
            for o in opts:
                cb = "captcha_ok" if o == ans else "captcha_fail:" + str(ans)
                rows.append(InlineKeyboardButton(pe("target","◎") + " " + str(o), callback_data=cb))
            kb = InlineKeyboardMarkup([rows[i:i+2] for i in range(0, len(rows), 2)])
            rich = _hdr(sc("welcome") + " " + rich_esc(user.first_name or ""),3) + rich_note(pe("line","⫶") + " " + sc("verify you are human") + " " + pe("diamond","⬪") + "<br><b>" + pe("target","◎") + " " + rich_esc(expr) + " = ?</b> " + pe("spark","𖦹") + " " + sc("you have") + " <code>" + str(timeout) + "s</code>")
            rich += "<p>" + rich_button(pe("check","✅") + " " + sc("verify"), url="https://t.me/") + "</p>"
            try:
                sent = await rich_send(bot, chat_id, rich + "<br>" + pe("orb","◍") + ' <a href="tg://user?id=' + str(user.id) + '">' + rich_esc(user.first_name) + '</a> ' + pe("orb","◍"), reply_markup=kb)
                _PENDING[(chat_id,user.id)] = {"answer": ans, "msg": sent.id if sent else 0, "expire": time.time()+timeout}
                async def _timeout():
                    await asyncio.sleep(timeout)
                    pending = _PENDING.get((chat_id,user.id))
                    if not pending:
                        return
                    await _kick_pending(chat_id, user.id, pending["msg"], "timeout")
                    try:
                        await bot.send_message(chat_id, pe("warn","⚠️") + " <code>" + str(user.id) + "</code> " + sc("kicked — captcha timeout") + " " + pe("spark","𖦹"))
                    except Exception:
                        pass
                asyncio.create_task(_timeout())
            except Exception as e:
                LOGGER.warning("[captcha] send fail: " + str(e))
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("check","✅") + " " + sc("i am human") + " " + pe("spark","𖦹"), callback_data="captcha_ok")]])
            try:
                rich = _hdr(sc("welcome") + " " + rich_esc(user.first_name or ""),3) + rich_note(pe("diamond","⬪") + " " + sc("click to verify") + " " + pe("hex","⬢") + " <code>" + str(timeout) + "s</code>") + "<p>" + rich_button(pe("check","✅") + " " + sc("verify"), callback_data="captcha_ok") + "</p>"
                sent = await rich_send(bot, chat_id, rich, reply_markup=kb)
                _PENDING[(chat_id,user.id)] = {"answer": 0, "msg": sent.id if sent else 0, "expire": time.time()+timeout}
                async def _timeout2():
                    await asyncio.sleep(timeout)
                    pending = _PENDING.get((chat_id,user.id))
                    if not pending:
                        return
                    await _kick_pending(chat_id, user.id, pending["msg"], "timeout")
                asyncio.create_task(_timeout2())
            except Exception as e:
                LOGGER.warning("[captcha] button fail: " + str(e))

@bot.on_callback_query(filters.regex(r"^captcha_"))
async def captcha_verify_cb(_, q):
    if not q.message or not q.message.chat:
        return
    chat_id = q.message.chat.id
    user_id = q.from_user.id if q.from_user else 0
    pend = _PENDING.get((chat_id,user_id))
    if not pend:
        return await q.answer(pe("warn","⚠️") + " " + sc("not for you") + " " + pe("diamond","⬪"), show_alert=True)
    data = q.data or ""
    if data == "captcha_ok":
        _PENDING.pop((chat_id,user_id), None)
        try:
            await q.message.delete()
        except Exception:
            pass
        try:
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        except Exception:
            pass
        await q.answer(pe("check","✅") + " " + sc("verified") + " " + pe("spark","𖦹"))
        try:
            await rich_send(bot, chat_id, _hdr(pe("check","✅") + " " + '<a href="tg://user?id=' + str(user_id) + '">' + rich_esc(q.from_user.first_name or "") + '</a> ' + sc("verified — welcome") + " " + pe("spark","𖦹"),3))
        except Exception:
            pass
        return
    if data.startswith("captcha_fail"):
        _PENDING.pop((chat_id,user_id), None)
        try:
            await q.message.delete()
        except Exception:
            pass
        try:
            await bot.ban_chat_member(chat_id, user_id)
        except Exception:
            pass
        await q.answer(pe("cross","❌") + " " + sc("wrong — kicked") + " " + pe("diamond","⬪"), show_alert=True)
        return
    await q.answer()
