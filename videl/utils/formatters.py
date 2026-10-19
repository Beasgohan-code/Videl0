# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import isodate
import math


def fmt_time(seconds: float) -> str:
    """Convert seconds → H:MM:SS or M:SS string."""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_dur(s: str) -> int:
    """Parse ISO 8601 duration or MM:SS / H:MM:SS string → seconds."""
    try:
        return int(isodate.parse_duration(s).total_seconds())
    except Exception:
        pass
    if ":" in s:
        try:
            parts = [int(x) for x in s.split(":")]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            pass
    return 0


def iso_to_sec(iso: str) -> int:
    """ISO 8601 duration → seconds."""
    try:
        return int(isodate.parse_duration(iso).total_seconds())
    except Exception:
        return 0


def iso_to_human(iso: str) -> str:
    """ISO 8601 duration → human-readable H:MM:SS string."""
    try:
        t = int(isodate.parse_duration(iso).total_seconds())
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
    except Exception:
        return "?"


def sec_to_iso(sec: int) -> str:
    """Seconds → ISO 8601 duration string."""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"PT{h}H{m}M{s}S" if h else f"PT{m}M{s}S"


def short(title: str, n: int = 22) -> str:
    """Truncate title to n characters."""
    return title if len(title) <= n else title[: n - 1] + "…"


# ── Cyber Dark Perfect Aesthetics (Videl0 upgrade) ─────────────────────────────
# Unicode small-caps map for UI labels (production perfection)
_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)

# Sans-bold for premium labels (𝗩𝗶𝗱𝗲𝗹 style)
_SB_LOWER = {chr(ord('a')+i): chr(0x1D5EE+i) for i in range(26)}
_SB_UPPER = {chr(ord('A')+i): chr(0x1D5D4+i) for i in range(26)}
_SB = str.maketrans({**_SB_LOWER, **_SB_UPPER})

# Cyber dark glyphs: ◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢ — user picked
CYBER = {"dot":"◍","diamond":"⬪","line":"⫶","small":"⬩","spark":"𖦹","circle":"⦿","target":"◎","hex":"⬢"}

def sc(text: str) -> str:
    """Convert Latin letters to small-caps — ɪᴅ ɪɴғᴏ style."""
    if not text:
        return text
    return str(text).translate(_SC)

def sb(text: str) -> str:
    """Sans-bold — 𝗩𝗶𝗱𝗲𝗹 style (mathematical sans-serif bold)."""
    if not text:
        return text
    return str(text).translate(_SB)

def deco(text: str, left: str="◍", right: str="◍") -> str:
    """◍ sᴛʏʟᴇ ◍"""
    return f"{left} {sc(text.lower())} {right}"
def header(title: str) -> str:
    return f"⬪ {sc(title.lower())} ⬪"
def bullet(label: str) -> str:
    return f"⫶ {sc(label.lower())}"


def progress_bar(elapsed: float, total: float) -> str:
    """Cyber Dark progress bar — ◍ ⬪ ⫶ perfected (was ♡)."""
    if total <= 0:
        return "◍ ───────── ◍"
    played = fmt_time(elapsed)
    dur = fmt_time(total)
    pct = (int(elapsed) / int(total)) * 100 if total else 0
    umm = math.floor(pct)
    # cyber dark bar with moving ◍
    if umm <= 10:
        bar = "◍─────────"
    elif umm <= 20:
        bar = "─◍────────"
    elif umm <= 30:
        bar = "──◍───────"
    elif umm <= 40:
        bar = "───◍──────"
    elif umm <= 50:
        bar = "────◍─────"
    elif umm <= 60:
        bar = "─────◍────"
    elif umm <= 70:
        bar = "──────◍───"
    elif umm <= 80:
        bar = "───────◍──"
    elif umm <= 95:
        bar = "────────◍─"
    else:
        bar = "─────────◍"
    # cyber wrapper
    return f"{played} ⬪ {bar} ⬪ {dur}"
