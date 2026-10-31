"""Validated, plain-text per-group command replies; never executes user code."""
from __future__ import annotations

import re
import threading
import time

NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
ALLOWED = {"name", "mention", "id", "chat", "username", "args"}
MAX_REPLY = 3500
COOLDOWNS = {0, 5, 10, 30, 60, 120}
_USE_LOCK = threading.Lock()
_LAST_USE: dict[tuple[int, str, int], float] = {}


class CustomCommandError(ValueError):
    pass


def is_native(name: str) -> bool:
    # The source catalog is the authority for native names and aliases. This
    # check is also applied at dispatch so a future bot release cannot make an
    # old saved response shadow a newly-added built-in command.
    from videl.utils.command_catalog import commands
    return str(name or "").lower() in {item["name"] for item in commands()}


def validate_name(value: str) -> str:
    name = str(value or "").strip().lower().lstrip("/")
    if not NAME.fullmatch(name):
        raise CustomCommandError("Command names use 2–32 lowercase letters, numbers or underscores, and start with a letter.")
    if is_native(name):
        raise CustomCommandError(f"/{name} is already a Videl command.")
    if name in {"help", "start", "settings", "commands", "cmds"}:
        raise CustomCommandError(f"/{name} is reserved by Videl.")
    return name


def validate_reply(value: str) -> str:
    if not isinstance(value, str):
        raise CustomCommandError("Enter a text response.")
    text = value.strip()
    try:
        units = len(text.encode("utf-16-le")) // 2
    except UnicodeEncodeError:
        raise CustomCommandError("Response contains malformed Unicode text.") from None
    if not text or units > MAX_REPLY:
        raise CustomCommandError(f"Response must contain 1–{MAX_REPLY} Telegram text units.")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise CustomCommandError("Response contains unsupported control characters.")
    tokens = re.findall(r"\{([^{}]*)\}", text)
    unknown = sorted({token for token in tokens if token not in ALLOWED})
    if unknown:
        raise CustomCommandError("Unknown placeholder(s): " + ", ".join("{" + key + "}" for key in unknown))
    # A bare brace could be mistaken for a variable in future versions; make
    # the supported syntax explicit now rather than evaluating format strings.
    stripped = re.sub(r"\{[^{}]*\}", "", text)
    if "{" in stripped or "}" in stripped:
        raise CustomCommandError("Use only the listed placeholders in braces.")
    return text


def render(text: str, values: dict) -> str:
    return PLACEHOLDER.sub(lambda match: str(values.get(match.group(1), "")), text)


def list_for(db, chat_id: int) -> list[dict]:
    return [{"name": str(row.get("name") or ""), "response": str(row.get("response") or ""),
             "cooldown_seconds": int(row.get("cooldown_seconds") or 0)}
            for row in db["mgmt_custom_commands"].find(
                {"chat_id": int(chat_id)}, {"_id": 0, "name": 1, "response": 1, "cooldown_seconds": 1}
            ).sort("name", 1).limit(100)]


def save(db, chat_id: int, name: str, response: str, cooldown_seconds=0) -> str:
    if db is None:
        raise CustomCommandError("MongoDB is not connected; the command was not saved.")
    clean_name = validate_name(name)
    clean_response = validate_reply(response)
    try:
        cooldown_seconds = int(cooldown_seconds)
    except (TypeError, ValueError):
        raise CustomCommandError("Choose a supported cooldown.") from None
    if cooldown_seconds not in COOLDOWNS:
        raise CustomCommandError("Cooldown must be 0, 5, 10, 30, 60 or 120 seconds.")
    collection = db["mgmt_custom_commands"]
    query = {"chat_id": int(chat_id), "name": clean_name}
    if collection.find_one(query, {"_id": 1}) is None and collection.count_documents({"chat_id": int(chat_id)}) >= 100:
        raise CustomCommandError("A group can save up to 100 custom commands.")
    collection.update_one(
        query,
        {"$set": {"chat_id": int(chat_id), "name": clean_name, "response": clean_response,
                  "cooldown_seconds": cooldown_seconds}},
        upsert=True,
    )
    return clean_name


def allow_use(chat_id: int, name: str, user_id: int, cooldown_seconds=0, *, now=None):
    """Enforce a bounded per-user cooldown; returns (allowed, retry_seconds)."""
    seconds = max(0, min(int(cooldown_seconds or 0), 120))
    if not seconds:
        return True, 0
    moment = time.monotonic() if now is None else float(now)
    key = (int(chat_id), str(name).lower(), int(user_id))
    with _USE_LOCK:
        previous = _LAST_USE.get(key)
        if previous is not None and moment - previous < seconds:
            return False, max(1, int(seconds - (moment - previous) + 0.999))
        _LAST_USE[key] = moment
        if len(_LAST_USE) > 20000:
            cutoff = moment - 600
            for old_key, stamp in list(_LAST_USE.items()):
                if stamp < cutoff:
                    _LAST_USE.pop(old_key, None)
            while len(_LAST_USE) > 15000:
                _LAST_USE.pop(next(iter(_LAST_USE)))
    return True, 0


def delete(db, chat_id: int, name: str) -> str:
    clean_name = str(name or "").strip().lower().lstrip("/")
    if not NAME.fullmatch(clean_name):
        raise CustomCommandError("Choose a valid custom command to remove.")
    if db is None:
        raise CustomCommandError("MongoDB is not connected.")
    db["mgmt_custom_commands"].delete_one({"chat_id": int(chat_id), "name": clean_name})
    return clean_name
