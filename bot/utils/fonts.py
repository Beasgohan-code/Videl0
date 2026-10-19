"""
Videl0 • Fonts & Aesthetic — Cyber Dark Perfected
v2: Small caps + Sans Bold + Cyber Dark emojis (◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢)

Styles:
  small caps → ɪᴅ ɪɴғᴏ (classic)
  sans bold  → 𝗩𝗶𝗱𝗲𝗹 (mathematical sans-bold)
  cyber dark → ⬪ ⫶ ◍ ⬩ 𖦹 ⦿ ⬢ ◎

All handlers import from here so bot feels 100% perfect.
"""

# ── Small Caps map ───────────────────────────────────────────────────────────
SMALL_CAPS = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ',
    'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ',
    'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ',
    'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
}

# ── Sans Bold (Mathematical Sans-Serif Bold) ─────────────────────────────────
SANS_BOLD = {chr(ord('A')+i): chr(0x1D5D4+i) for i in range(26)}
SANS_BOLD.update({chr(ord('a')+i): chr(0x1D5EE+i) for i in range(26)})
SANS_BOLD.update({chr(ord('0')+i): chr(0x1D7EC+i) for i in range(10)})

# ── Cyber Dark Glyph Set (user picked: ⬪ ⬩ ◍ ⦿ 𖦹 ⫶) ───────────────────────
CYBER = {
    "dot": "◍",
    "diamond": "⬪",
    "small_diamond": "⬩",
    "circle": "⦿",
    "target": "◎",
    "hex": "⬢",
    "spark": "𖦹",
    "line": "⫶",
    "dash": "─",
    "arrow": "➪",
    "arrow2": "⫷",
    "arrow3": "⫸",
    "slash": "╱",
    "cross": "╳",
    "thin": "─",
    "double": "═",
    "mid": "•",
    "star": "✦",  # kept minimal
}

DARK_EMOJIS = ["◍","⬪","⫶","⬩","𖦹","⦿","◎","⬢","⬣","╱","╲","╳","⬔","⬕","⬖","⬗","⫷","⫸","⧉","⧛","⧚"]

def to_small_caps(text: str) -> str:
    return "".join(SMALL_CAPS.get(ch, ch) for ch in text)

def to_sans_bold(text: str) -> str:
    return "".join(SANS_BOLD.get(ch, ch) for ch in text)

# aliases
small = to_small_caps
sans = to_sans_bold
bold  = to_sans_bold

def sc(text: str) -> str: return to_small_caps(text)
def sb(text: str) -> str: return to_sans_bold(text)

# ── Decor helpers — Cyber Dark ───────────────────────────────────────────────
def deco(title: str, left: str = "◍", right: str = "◍") -> str:
    """◍  ᴛɪᴛʟᴇ  ◍"""
    return f"{left} {sc(title.lower())} {right}"

def header(title: str, style: str = "sc") -> str:
    """Perfect header: ⬪  ᴠɪᴅᴇʟ  ⬪ """
    txt = sc(title.lower()) if style == "sc" else sb(title)
    return f"⬪ {txt} ⬪"

def header2(title: str) -> str:
    return f"⫶ {sc(title.lower())} ⫶"

def divider() -> str:
    return "─" * 14

def bullet(label: str) -> str:
    return f"⫶ {sc(label.lower())}"

def kv(k: str) -> str:
    return sc(k.lower())

def arrow_label(text: str) -> str:
    return f"➪ {sc(text.lower())}"

def cyber_bar() -> str:
    return "⬪ ⫶ ◍ ⫶ ⬪"

def footer_note(text: str) -> str:
    return f"◍ {sc(text.lower())} ◍"

# Common phrases pre-styled
PH = {
    "id_info": sc("id info"),
    "assistant": sc("assistant"),
    "join_failed": sc("join failed"),
    "playing": sc("now playing"),
    "queue": sc("queue"),
    "banned": sc("banned"),
    "muted": sc("muted"),
    "warned": sc("warned"),
    "owner": sc("owner only"),
    "admin": sc("admin only"),
    "sudo": sc("sudo only"),
    "success": sc("success"),
    "failed": sc("failed"),
    "processing": sc("processing"),
    "searching": sc("searching"),
}
