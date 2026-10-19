"""
Videl0 • Rich UI — aiogram 3.31 Port of Badmunda05/richgram
Bot API 10.3 Rich Messages (tables, details, buttons, headings) for aiogram.

Richgram was built for Pyrogram/Kurigram. aiogram 3.31 ships native
InputRichMessage + Bot.send_rich_message() etc. This module ports the
exact same builder API (rich_heading, rich_kv_table, rich_button_row …)
to aiogram while keeping a plaintext fallback for old clients.

Usage:
  from bot.rich_ui import rich_heading, rich_kv_table, rich_esc, rich_send, rich_reply

  text = rich_heading("Now Playing", level=3) + rich_kv_table([...])
  await rich_send(bot, chat_id, text)

Credits: original richgram by BadmundaXd • ported for aiogram by Videl0
"""
from __future__ import annotations
import html as _html
import logging
import re
from typing import Optional

logger = logging.getLogger("videl.rich")

# ── Detect aiogram rich support ─────────────────────────────────────────────
try:
    from aiogram.types import InputRichMessage  # aiogram 3.31
    from aiogram import Bot
    RICH_AVAILABLE = True
except ImportError:
    InputRichMessage = None  # type: ignore
    Bot = None  # type: ignore
    RICH_AVAILABLE = False

__all__ = [
    "RICH_AVAILABLE",
    "rich_esc", "sanitize_display_name",
    "rich_heading", "rich_note", "rich_table", "rich_kv_table",
    "rich_details", "rich_code", "rich_pre", "rich_list", "rich_hr",
    "rich_footer", "rich_pull_quote", "rich_math", "rich_anchor",
    "rich_thinking", "rich_img",
    "rich_button", "rich_button_row",
    "rich_to_plain", "rich_caption",
    "rich_send", "rich_send_blocks", "rich_reply", "rich_edit", "rich_edit_inline", "rich_answer",
    "ephemeral_edit", "ephemeral_delete", "RichDraft",
]

# ── Helpers ────────────────────────────────────────────────────────────────
BUTTON_STYLES = ("primary","success","danger","link","default")

def rich_esc(value) -> str:
    if value is None: return ""
    return _html.escape(str(value), quote=False)

def _attr(v) -> str: return _html.escape(str(v), quote=True)

_INVISIBLE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00ad]")
_COMBINING_RE = re.compile("[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]")

def sanitize_display_name(value, max_len=64) -> str:
    if not value: return "User"
    text = _INVISIBLE_RE.sub("", str(value))
    out, run=[],0
    for ch in text:
        if _COMBINING_RE.match(ch):
            run+=1
            if run>2: continue
        else: run=0
        out.append(ch)
    cleaned="".join(out).strip()
    return cleaned[:max_len] or "User"

# ── Rich builders (same names as richgram) ─────────────────────────────────
def rich_img(src: str) -> str:
    return f'<img src="{_attr(src)}" />' if src else ""

def rich_heading(text: str, level: int = 1) -> str:
    level=max(1,min(6,int(level)))
    return f"<h{level}>{text}</h{level}>"

def rich_note(text: str, expandable: bool=False) -> str:
    attr=" expandable" if expandable else ""
    return f"<blockquote{attr}>{text}</blockquote>"

def rich_code(v) -> str: return f"<code>{rich_esc(v)}</code>"
def rich_pre(v, language: str=None) -> str:
    body=rich_esc(v)
    if language: return f'<pre><code class="language-{_attr(language)}">{body}</code></pre>'
    return f"<pre>{body}</pre>"
def rich_list(items, ordered: bool=False) -> str:
    tag="ol" if ordered else "ul"
    body="".join(f"<li>{'' if i is None else i}</li>" for i in (items or ()))
    return f"<{tag}>{body}</{tag}>"
def rich_hr() -> str: return "<hr/>"
def rich_footer(t: str) -> str: return f"<footer>{t}</footer>"
def rich_pull_quote(t: str) -> str: return f"<aside>{t}</aside>"
def rich_math(expr: str) -> str: return f'<tg-math-block>{rich_esc(expr)}</tg-math-block>'
def rich_anchor(text: str, url: str) -> str: return f'<a href="{_attr(url)}">{text}</a>'
def rich_thinking(text: str) -> str: return f"<tg-thinking>{text}</tg-thinking>"

def rich_table(headers: list[str], rows: list[list[str]]) -> str:
    th="".join(f"<th>{h}</th>" for h in headers)
    tr="".join("<tr>"+"".join(f"<td>{c}</td>" for c in r)+"</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

def rich_kv_table(pairs: list[tuple[str,str]]) -> str:
    th="<th>Field</th><th>Value</th>"
    tr="".join(f"<tr><td>{rich_esc(k)}</td><td>{v}</td></tr>" for k,v in pairs)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

def rich_details(summary: str, content: str, open: bool=False) -> str:
    o=" open" if open else ""
    return f"<details{o}><summary>{summary}</summary>{content}</details>"

# ── Buttons (Bot API 10.3) ─────────────────────────────────────────────────
def rich_button(text: str, url: str=None, callback_data: str=None, style: str=None) -> str:
    style_attr=f' style="{_attr(style)}"' if style else ""
    if url:
        return f'<tg-button type="url"{style_attr} url="{_attr(url)}">{rich_esc(text)}</tg-button>'
    if callback_data:
        return f'<tg-button type="callback_data"{style_attr} data="{_attr(callback_data)}">{rich_esc(text)}</tg-button>'
    return f'<tg-button{style_attr}>{rich_esc(text)}</tg-button>'

def rich_button_row(*buttons: str) -> str:
    return "<tg-button-row>" + "".join(buttons) + "</tg-button-row>"

# ── Plain fallback ─────────────────────────────────────────────────────────
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_BUTTON_RE = re.compile(r"<tg-button[^>]*>(.*?)</tg-button>", re.I|re.S)
def rich_to_plain(html_text: str) -> str:
    if not html_text: return ""
    t = _BUTTON_RE.sub(r"[\1]", html_text)
    t = _ANY_TAG_RE.sub("", t)
    t = _html.unescape(t)
    return t.strip()
def rich_caption(html_text: str) -> str:
    return rich_to_plain(html_text)

# ── Send / Edit — aiogram native ─────────────────────────────────────────
def _has_rich_tags(html_text: str) -> bool:
    if not html_text: return False
    return bool(re.search(r"</?(?:h[1-6]|table|thead|tbody|tr|th|td|details|summary|mark|sub|sup|ul|ol|li|hr|aside|footer|tg-button-row|tg-button|tg-math-block|tg-collage|tg-slideshow|tg-map|tg-document|tg-thinking|button|img)(?=[\s/>])", html_text, re.I))

def _input_rich(html_text: str, **kwargs):
    if InputRichMessage is None: return None
    # aiogram's InputRichMessage accepts blocks or html; we pass html via InputRichMessage(text=...)
    # aiogram 3.31: InputRichMessage(html_text=..., markdown=...)
    try:
        return InputRichMessage(html_text=html_text, **kwargs)
    except TypeError:
        # fallback older signature
        try: return InputRichMessage(text=html_text)
        except: return None

async def rich_send(bot, chat_id: int, html_text: str, **kwargs) -> Optional[object]:
    """Send rich message via aiogram; fallback to plain HTML if needed."""
    if not html_text: return None
    # extra kwargs that richgram supports — drop unknown for send_message fallback
    reply_markup = kwargs.pop("reply_markup", None) or kwargs.pop("markup", None)
    # try rich first
    if RICH_AVAILABLE and _has_rich_tags(html_text):
        try:
            rm = _input_rich(html_text)
            if rm:
                return await bot.send_rich_message(chat_id=chat_id, rich_message=rm, reply_markup=reply_markup, **kwargs)
        except Exception as e:
            logger.debug(f"[rich_send] rich failed, fallback: {e}")

    # plain HTML fallback
    try:
        from aiogram.enums import ParseMode
        return await bot.send_message(chat_id=chat_id, text=rich_to_plain(html_text) if _has_rich_tags(html_text) else html_text,
                                      parse_mode=ParseMode.HTML, reply_markup=reply_markup, **{k:v for k,v in kwargs.items() if k in ("message_thread_id","disable_notification","protect_content","reply_parameters","business_connection_id","message_effect_id")})
    except Exception as e:
        logger.warning(f"[rich_send] plain send failed: {e}")
        return None

async def rich_send_blocks(bot, chat_id: int, blocks: list, **kwargs):
    html_text = "".join(str(b) for b in (blocks or []))
    return await rich_send(bot, chat_id, html_text, **kwargs)

async def rich_reply(message, html_text: str, reply_markup=None, **kwargs):
    if not message or not html_text: return None
    bot = kwargs.pop("client", None) or getattr(message, "bot", None) or getattr(message, "_bot", None)
    if not bot: return None
    chat_id = message.chat.id
    # reply parameters
    try:
        from aiogram.types import ReplyParameters
        kwargs.setdefault("reply_parameters", ReplyParameters(message_id=message.message_id))
    except: pass
    return await rich_send(bot, chat_id, html_text, reply_markup=reply_markup, **kwargs)

async def rich_edit(target, html_text: str, reply_markup=None, **kwargs) -> Optional[object]:
    """Edit message — target can be Message or CallbackQuery or (bot, chat_id, message_id)."""
    if not html_text: return None
    # CallbackQuery → its message
    if hasattr(target, "message") and hasattr(target, "data"):
        target = target.message  # unwrap
    # Message object
    if hasattr(target, "chat") and hasattr(target, "message_id"):
        bot = kwargs.pop("client", None) or getattr(target, "bot", None)
        if not bot: return None
        chat_id = target.chat.id
        msg_id = target.message_id
    elif isinstance(target, tuple) and len(target)==3:
        bot, chat_id, msg_id = target
    else:
        # direct bot call
        bot = kwargs.pop("client", None) or target
        chat_id = kwargs.pop("chat_id", None)
        msg_id = kwargs.pop("message_id", None)
        if not chat_id or not msg_id: return None

    wants_rich = _has_rich_tags(html_text)
    if RICH_AVAILABLE and wants_rich:
        try:
            rm = _input_rich(html_text)
            return await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, rich_message=rm, reply_markup=reply_markup)
        except Exception as e:
            logger.debug(f"[rich_edit] rich edit failed: {e}")

    try:
        from aiogram.enums import ParseMode
        return await bot.edit_message_text(chat_id=chat_id, message_id=msg_id,
                                           text=rich_to_plain(html_text) if wants_rich else html_text,
                                           parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception as e:
        logger.debug(f"[rich_edit] plain edit failed: {e}")
        return None

async def rich_edit_inline(client, inline_message_id: str, html_text: str, **kwargs):
    if not inline_message_id or not html_text: return None
    try:
        from aiogram.enums import ParseMode
        return await client.edit_message_text(inline_message_id=inline_message_id,
                                              text=rich_to_plain(html_text) if _has_rich_tags(html_text) else html_text,
                                              parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.debug(f"[rich_edit_inline] {e}")
        return None

async def rich_answer(callback_query, html_text: str, **kwargs):
    if not callback_query or not html_text: return None
    bot = kwargs.pop("client", None) or getattr(callback_query, "bot", None)
    if not bot: return None
    # answer via rich_send to chat (ephemeral if group)
    chat = getattr(getattr(callback_query,"message",None),"chat",None)
    if not chat: return None
    return await rich_send(bot, chat.id, html_text, **kwargs)

# ephemeral stubs (aiogram doesn't have ephemeral exactly — map to normal)
async def ephemeral_edit(message, html_text: str, **kwargs): return await rich_edit(message, html_text, **kwargs)
async def ephemeral_delete(message, **kwargs) -> bool:
    try:
        await message.delete(); return True
    except: return False

class RichDraft:
    """Streaming draft — mimics richgram RichDraft using edits."""
    def __init__(self, bot, chat_id: int, message_thread_id=None, draft_id=None, can_stop=None, keep_on_stop=None):
        self.bot=bot; self.chat_id=chat_id; self.message_thread_id=message_thread_id
        self.draft_id=draft_id; self.can_stop=can_stop; self.keep_on_stop=keep_on_stop
        self._last_html=None; self._finished=False; self._result=None
        self._msg=None
    async def update(self, html_text: str) -> bool:
        if not html_text: return False
        self._last_html=html_text
        try:
            if self._msg is None:
                self._msg = await rich_send(self.bot, self.chat_id, html_text, message_thread_id=self.message_thread_id)
            else:
                await rich_edit(self._msg, html_text)
            return True
        except Exception as e:
            logger.debug(f"[RichDraft] update failed: {e}")
            return False
    async def finish(self, html_text: str=None, reply_markup=None, **kwargs):
        self._finished=True
        final=html_text or self._last_html
        if not final: return self._result
        if self._msg:
            self._result = await rich_edit(self._msg, final, reply_markup=reply_markup)
        else:
            self._result = await rich_send(self.bot, self.chat_id, final, reply_markup=reply_markup, message_thread_id=self.message_thread_id, **kwargs)
        return self._result
    @property
    def result(self): return self._result
    def discard(self): self._finished=True; self._last_html=None
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb):
        if not self._finished and exc_type is None: await self.finish()
        return False
