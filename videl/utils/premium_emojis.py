# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Premium Costume Emoji
#  User-supplied premium emoji IDs — NewsEmoji + tgiosicons + @rijif + SoLo_HaMiD
#  No Premium subscription needed for the bot to SEND them — just IDs via Bot API
#  <tg-emoji emoji-id="..."> fallback uses HTML parse_mode
# --------------------------------------------------------------------------------
from __future__ import annotations
import os
import config

# ── Premium toggle — env USE_PREMIUM_EMOJI=1 (default ON) ─────────────────────
USE_PREMIUM: bool = os.getenv("USE_PREMIUM_EMOJI", "1").strip().lower() not in ("0","false","no","off")

# ── Verified IDs from user (Get Emoji ID Bot) — 4 packs ───────────────────────
# Pack 1: https://t.me/addemoji/NewsEmoji (NewsEmoji)
# Pack 2: https://t.me/addemoji/tgiosicons (Telegram iOS Icons)
# Pack 3: https://t.me/addemoji/Udif7rr7_by_fStikBot (@rijif)
# Pack 4: https://t.me/addemoji/SoLo_HaMiD (@Boseh | @NewEmojis)
PREMIUM_IDS: dict[str, str] = {
    # ── Cyber Dark core (replaces ◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢ ➪) ──
    "orb":       "5042302287087666158",  # 🔮 NewsEmoji: @rijif — crystal orb for ◍
    "diamond":   "5427168083074628963",  # 💎 NewsEmoji — diamond for ⬪
    "line":      "5456140674028019486",  # ⚡️ NewsEmoji — bolt for ⫶
    "small":     "5411225014148014586",  # 🔴 NewsEmoji — red dot for ⬩
    "spark":     "5325547803936572038",  # ✨ NewsEmoji — spark for 𖦹
    "circle":    "5210956306952758910",  # 👀 NewsEmoji — eye for ⦿
    "target":    "5341715473882955310",  # ⚙️ NewsEmoji — gear for ◎
    "hex":       "5251203410396458957",  # 🛡 NewsEmoji — shield for ⬢
    "arrow":     "5416117059207572332",  # ➡️ NewsEmoji — arrow for ➪
    "dash":      "5443038326535759644",  # 💬 NewsEmoji — chat for ─

    # ── Status / moderation ──
    "check":     "5084979757905347540",  # ✅ SoLo — check
    "check2":    "5206607081334906820",  # ✔️ NewsEmoji — alt check
    "cross":     "5210952531676504517",  # ❌ NewsEmoji — cross
    "cross2":    "5040042498634810056",  # ❌ @rijif — alt cross
    "warn":      "5447644880824181073",  # ⚠️ NewsEmoji — warn
    "warn2":     "5420323339723881652",  # ⚠️ NewsEmoji — alt warn
    "ban":       "5260293700088511294",  # ⛔️ NewsEmoji — ban
    "forbid":    "5240241223632954241",  # 🚫 NewsEmoji — forbid
    "exclaim":   "5274099962655816924",  # ❗️ NewsEmoji — exclaim
    "double_ex": "5440660757194744323",  # ‼️ NewsEmoji
    "question":  "5436113877181941026",  # ❓ NewsEmoji
    "quest2":    "5452069934089641166",  # ❓ NewsEmoji alt

    # ── Locks / security ──
    "lock":      "5296369303661067030",  # 🔒 NewsEmoji
    "unlock":    "6037496202990194718",  # 🔓 tgiosicons
    "shield":    "6030445631921721471",  # 🛡 tgiosicons alt
    "key":       "5962952497197748583",  # 🔧 tgiosicons

    # ── Media / music ──
    "music":     "5463107823946717464",  # 🎵 NewsEmoji
    "music2":    "6037364759811068375",  # 🎶 tgiosicons
    "mic":       "5224736245665511429",  # 🎤 NewsEmoji
    "mic2":      "5294339927318739359",  # 🎙 NewsEmoji
    "speaker":   "5388632425314140043",  # 🔈 NewsEmoji
    "pin":       "5397782960512444700",  # 📌 NewsEmoji
    "pin2":      "4917985158784615388",  # 📌 SoLo

    # ── Arrows / nav ──
    "right":     "5416117059207572332",  # ➡️
    "left":      "5960671702059848143",  # ⬅️ tgiosicons
    "up":        "5449683594425410231",  # 🔼
    "down":      "5447183459602669338",  # 🔽
    "up2":       "5963103826075456248",  # ⬆️
    "down2":     "5963087934696459905",  # ⬇️

    # ── Info / utils ──
    "info":      "5334544901428229844",  # ℹ️ NewsEmoji
    "info2":     "5323442290708985472",  # ©
    "globe":     "5447410659077661506",  # 🌐 NewsEmoji
    "stats":     "5231200819986047254",  # 📊
    "link":      "5271604874419647061",  # 🔗 NewsEmoji
    "link2":     "6028171274939797252",  # 🔗 tgiosicons
    "search":    "5231012545799666522",  # 🔍
    "fire":      "5424972470023104089",  # 🔥
    "boom":      "5276032951342088188",  # 💥
    "star":      "5438496463044752972",  # ⭐️
    "sparkle2":  "5172834782823842584",  # ✨ SoLo
    "crown":     "5217822164362739968",  # 👑
    "diamond2":  "5409048419211682843",  # 💵
    "money":     "5402186569006210455",  # 💱

    # ── Fun / costume ──
    "eyes":      "5039623284056917259",  # 👀 @rijif
    "lightning": "5042334757040423886",  # ⚡️ @rijif
    "brain":     "5040030395416969985",  # 🧠 @rijif
    "skull":     "5042209657527993345",  # 💀 @rijif
    "ghost":     "5042097984083330584",  # 👻 @rijif
    "clown":     "5269531045165816230",  # 🤡 NewsEmoji
    "robot":     "6030400221232501136",  # 🤖 tgiosicons

    # ── Numbers (for pagination) ──
    "one":       "5141109049114232089",  # 1️⃣
    "two":       "5140871649091912628",  # 2️⃣
    "three":     "5141399818400170896",  # 3️⃣
}

# Fallback glyphs — cyber dark original
FALLBACK: dict[str, str] = {
    "orb":"◍","diamond":"⬪","line":"⫶","small":"⬩","spark":"𖦹",
    "circle":"⦿","target":"◎","hex":"⬢","arrow":"➪","dash":"─",
    "check":"✅","cross":"❌","warn":"⚠️","ban":"⛔️","lock":"🔒","unlock":"🔓",
    "pin":"📌","music":"🎵","right":"➡️","left":"⬅️","up":"🔼","down":"🔽",
    "info":"ℹ️","globe":"🌐","link":"🔗","fire":"🔥","star":"⭐️","eyes":"👀",
}

def tg_emoji(emoji_id: str | int, fallback: str = "◍") -> str:
    """Return <tg-emoji> HTML if premium enabled, else fallback glyph."""
    if not USE_PREMIUM or not emoji_id:
        return fallback
    # Bot API supports <tg-emoji emoji-id="...">emoji</tg-emoji>
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def pe(key: str, fallback: str | None = None) -> str:
    """Premium emoji by logical key — auto falls back to cyber glyph."""
    if key in {"orb", "diamond", "line", "small", "spark", "circle", "target", "hex", "arrow", "dash"}:
        return ""
    fid = PREMIUM_IDS.get(key, "")
    fb = fallback if fallback is not None else FALLBACK.get(key, "◍")
    return tg_emoji(fid, fb)

# ── Ready-made cyber helpers — drop-in replacements for formatters.CYBER ──
def orb() -> str:     return pe("orb", "◍")
def diamond() -> str: return pe("diamond", "⬪")
def line() -> str:    return pe("line", "⫶")
def small() -> str:   return pe("small", "⬩")
def spark() -> str:   return pe("spark", "𖦹")
def circle() -> str:  return pe("circle", "⦿")
def target() -> str:  return pe("target", "◎")
def hexg() -> str:    return pe("hex", "⬢")
def arrow() -> str:   return pe("arrow", "➪")

# For headers — premium line
def header_emoji() -> str:
    # Use orb + diamond + spark combo
    return f"{orb()} {diamond()}"

# Expose all IDs for /premium debug command
def list_all() -> dict[str, str]:
    return PREMIUM_IDS.copy()
