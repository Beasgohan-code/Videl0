"""Pure message classification shared by lock enforcement and regression tests."""
import re

LOCK_TYPES = ("links", "media", "stickers", "forward", "polls", "photos", "videos", "audio", "voice", "documents", "animations", "contacts", "locations", "games", "inline", "mentions", "bots")
URL_RE = re.compile(r"(?:https?://|www\.|\bt\.me/|\btelegram\.me/)\S+", re.I)
FIELDS = {"stickers": ("sticker",), "polls": ("poll",), "photos": ("photo",), "videos": ("video", "video_note"), "audio": ("audio",), "voice": ("voice",), "documents": ("document",), "animations": ("animation",), "contacts": ("contact",), "locations": ("location", "venue"), "games": ("game",), "inline": ("via_bot",)}


def locked_message_reason(message, enabled):
    entities = list(getattr(message, "entities", None) or []) + list(getattr(message, "caption_entities", None) or [])
    kinds = {getattr(getattr(e, "type", None), "value", str(getattr(e, "type", ""))).lower() for e in entities}
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    if enabled("links") and (kinds & {"url", "text_link"} or URL_RE.search(text)):
        return "links"
    if enabled("mentions") and kinds & {"mention", "text_mention"}:
        return "mentions"
    if enabled("forward") and any(getattr(message, field, None) for field in ("forward_date", "forward_from", "forward_from_chat", "forward_origin")):
        return "forward"
    for category, fields in FIELDS.items():
        if enabled(category) and any(getattr(message, field, None) for field in fields):
            return category
    if enabled("media") and any(getattr(message, field, None) for field in ("photo", "video", "audio", "voice", "document", "animation", "video_note")):
        return "media"
    if enabled("bots") and getattr(getattr(message, "from_user", None), "is_bot", False):
        return "bots"
    return None
