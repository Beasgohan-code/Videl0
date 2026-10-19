# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Perfected
#  Cyber Dark • Small caps + Sans bold + ◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢
# --------------------------------------------------------------------------------
from __future__ import annotations
import math
import isodate

# ── Time ──────────────────────────────────────────────────────────────────────
def fmt_time(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def parse_dur(s: str) -> int:
    try:
        return int(isodate.parse_duration(s).total_seconds())
    except Exception:
        pass
    if ":" in s:
        try:
            parts = [int(x) for x in s.split(":")]
            if len(parts) == 2: return parts[0]*60 + parts[1]
            if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        except: pass
    return 0

def iso_to_sec(iso: str) -> int:
    try: return int(isodate.parse_duration(iso).total_seconds())
    except: return 0

def iso_to_human(iso: str) -> str:
    try:
        t = int(isodate.parse_duration(iso).total_seconds())
        h, r = divmod(t, 3600); m, s = divmod(r, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
    except: return "?"

def sec_to_iso(sec: int) -> str:
    m, s = divmod(int(sec), 60); h, m = divmod(m, 60)
    return f"PT{h}H{m}M{s}S" if h else f"PT{m}M{s}S"

def short(title: str, n: int = 28) -> str:
    return title if len(title) <= n else title[:n-1] + "…"

# ── Cyber Dark Map ────────────────────────────────────────────────────────────
# Small caps — elegant dark style: ɪᴅ ɪɴғᴏ ᴀssɪsᴛᴀɴᴛ ᴊᴏɪɴ ғᴀɪʟᴇᴅ
_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)
# Sans bold — 𝗩𝗶𝗱𝗲𝗹 title style
_SB = str.maketrans(
    {**{chr(ord('a')+i): chr(0x1D5EE+i) for i in range(26)},
     **{chr(ord('A')+i): chr(0x1D5D4+i) for i in range(26)},
     **{chr(ord('0')+i): chr(0x1D7EC+i) for i in range(10)}},
)
# ── Try premium emoji wrappers — fallback to text glyph if not configured ──
try:
    from videl.utils.premium_emojis import pe as _pe, USE_PREMIUM as _USE_PREM
    _HAS_PREM=True
except Exception:
    _HAS_PREM=False
    def _pe(k, fb): return fb
    _USE_PREM=False

def _cyber(glyph: str, key: str) -> str:
    # If premium enabled, pe() returns <tg-emoji> tag; else plain glyph
    if _HAS_PREM and _USE_PREM:
        return _pe(key, glyph)
    return glyph

CYBER = {
    "dot":     _cyber("◍","orb"),
    "diamond": _cyber("⬪","diamond"),
    "line":    _cyber("⫶","line"),
    "small":   _cyber("⬩","small"),
    "spark":   _cyber("𖦹","spark"),
    "circle":  _cyber("⦿","circle"),
    "target":  _cyber("◎","target"),
    "hex":     _cyber("⬢","hex"),
    "arrow":   _cyber("➪","arrow"),
    "dash":    _cyber("─","dash"),
}
# Also expose premium helpers for modules that want explicit premium:
PREM = {"orb":"orb","diamond":"diamond","line":"line","small":"small","spark":"spark","circle":"circle","target":"target","hex":"hex","arrow":"arrow"}

def sc(text: str) -> str:
    if not text: return text
    return str(text).translate(_SC)

def sb(text: str) -> str:
    if not text: return text
    return str(text).translate(_SB)

def deco(text: str, left: str="◍", right: str="◍") -> str:
    return f"{left} {sc(text.lower())} {right}"

def header(title: str) -> str:  return f"⬪ {sc(title.lower())} ⬪"
def header2(title: str) -> str: return f"⫶ {sc(title.lower())} ⫶"
def bullet(label: str) -> str:  return f"⫶ {sc(label.lower())}"
def kv(label: str) -> str:       return sc(label.lower())
def divider() -> str:            return "─" * 16
def cyber_bar() -> str:          return "⬪ ⫶ ◍ ⫶ ⬪"

# Progress dot — cyber dark travelling ◍ (replaces old ♡)
def progress_bar(elapsed: float, total: float) -> str:
    if total <= 0: return "◍ ───────── ◍"
    played, dur = fmt_time(elapsed), fmt_time(total)
    pct = (int(elapsed)/int(total))*100 if total else 0
    umm = math.floor(pct)
    if umm <= 10: bar="◍─────────"
    elif umm <= 20: bar="─◍────────"
    elif umm <= 30: bar="──◍───────"
    elif umm <= 40: bar="───◍──────"
    elif umm <= 50: bar="────◍─────"
    elif umm <= 60: bar="─────◍────"
    elif umm <= 70: bar="──────◍───"
    elif umm <= 80: bar="───────◍──"
    elif umm <= 95: bar="────────◍─"
    else: bar="─────────◍"
    return f"{played} ⬪ {bar} ⬪ {dur}"

# Classic bot dot: 0:00 ———◍——— 3:27  (used in now-playing caption)
def dot_progress(elapsed: float, total: float) -> str:
    if total <= 0: return f"0:00  ───◍───  0:00"
    left, right = fmt_time(elapsed), fmt_time(total)
    slots, pos = 10, int((elapsed/total)*10) if total else 0
    pos = max(0, min(9, pos))
    bar = "─"*pos + "◍" + "─"*(9-pos)
    return f"{left}  {bar}  {right}"
