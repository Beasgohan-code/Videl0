import re, html, time, textwrap
from datetime import datetime, timedelta

def mention_html(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
def escape_html(t: str) -> str: return html.escape(t)
def format_duration(s: int) -> str:
    if not s: return "0:00"
    m, s = divmod(int(s),60); h, m = divmod(m,60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
def parse_time(v: str) -> int|None:
    if not v: return None
    m=re.match(r"(\d+)\s*([smhdw])", v.lower().strip())
    if not m: return None
    n,u=int(m.group(1)),m.group(2)
    return n*{"s":1,"m":60,"h":3600,"d":86400,"w":604800}[u]
def until_text(s: int) -> str:
    if s<60: return f"{s}s"
    if s<3600: return f"{s//60}m"
    if s<86400: return f"{s//3600}h"
    return f"{s//86400}d"
def split_text(t: str, limit=4000): return textwrap.wrap(t, limit, break_long_words=False, replace_whitespace=False)
def extract_user_id(t: str) -> int|None:
    t=(t or "").strip()
    if t.lstrip("-").isdigit(): return int(t)
    return None
def time_now() -> str: return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
def progress_bar(cur: int, total: int, length=12) -> str:
    if not total: return "─"*length
    f=int(length*cur/total)
    return "█"*f+"░"*(length-f)
def clean_query(q: str) -> str: return re.sub(r"\s+"," ",q).strip()
def is_url(t: str) -> bool: return bool(re.match(r"https?://", (t or "").strip()))
def safe_filename(n: str) -> str: return re.sub(r'[\\/*?:"<>|]', "_", n)[:80]
def time_to_sec(t) -> int:
    s=str(t)
    return sum(int(x)*60**i for i,x in enumerate(reversed(s.split(":"))))

# Bot API 10.3 helpers
def mention_user(uid:int, name:str): return f'<a href="tg://user?id={uid}">{html.escape(name or "User")}</a>'
def chat_link(chat_id:int): return f"https://t.me/c/{str(chat_id).replace('-100','')}/"
