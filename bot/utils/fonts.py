"""
◍ Vɪᴅᴇʟ — Fonts & Aesthetic • Cyber Dark Perfected
   Small caps + Sans Bold + Cyber dark ◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢
   Single source — bot/utils/fonts + videl/utils/formatters share same map.
"""
from videl.utils.formatters import sc, sb, deco, header, header2, bullet, kv, divider, cyber_bar, progress_bar, CYBER

# Alias map for legacy imports
SMALL_CAPS = {}
SANS_BOLD = {}
DARK_EMOJIS = ["◍","⬪","⫶","⬩","𖦹","⦿","◎","⬢","⬣","╱","╳","⫷","⫸"]

def to_small_caps(t: str) -> str: return sc(t)
def to_sans_bold(t: str) -> str: return sb(t)
small = sc; sans = sb; bold = sb

def footer_note(text: str) -> str: return f"◍ {sc(text.lower())} ◍"
def arrow_label(text: str) -> str: return f"➪ {sc(text.lower())}"
def header2_compat(title: str) -> str: return header2(title)

PH = {
    "id_info": sc("id info"), "assistant": sc("assistant"), "join_failed": sc("join failed"),
    "playing": sc("now playing"), "queue": sc("queue"), "banned": sc("banned"),
    "muted": sc("muted"), "warned": sc("warned"), "owner": sc("owner only"),
    "admin": sc("admin only"), "sudo": sc("sudo only"), "success": sc("success"),
    "failed": sc("failed"), "processing": sc("processing"), "searching": sc("searching"),
}
