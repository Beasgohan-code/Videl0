"""How long to wait before trying to start the bot again.

Startup used to be all-or-nothing: one failed ``bot.start()`` parked the
process in ``sleep(3600)`` forever, so a two-second network blip meant the bot
stayed offline until a human pressed Restart in Render. Retrying is safe — a
failed start delivered nothing — but *how* we retry matters:

* a **transient** failure (network, Telegram 5xx, a database that is still
  connecting) deserves a fast retry, backing off so we do not hammer;
* a **conflict** (``AUTH_KEY_DUPLICATED``) means another instance is polling
  with the same session. Retrying immediately cannot help, but the other
  instance usually drains in a minute, so keep trying slowly;
* a **fatal** error (revoked token, wrong API id, deleted user) will not fix
  itself. Keep retrying, very slowly, because the environment can be corrected
  in the dashboard without a restart — but never pretend it is a blip.

After the fast phase every kind settles into a slow periodic retry, so nothing
requires a manual restart to recover.
"""
from __future__ import annotations

# Errors that no amount of retrying will fix on its own.
FATAL_MARKERS = (
    "AUTH_KEY_UNREGISTERED",
    "AUTH_KEY_INVALID",
    "USER_DEACTIVATED",
    "USER_DEACTIVATED_BAN",
    "API_ID_INVALID",
    "API_ID_PUBLISHED_FLOOD",
    "BOT_TOKEN_INVALID",
    "BOT_TOKEN_EXPIRED",
    "TOKEN_INVALID",
    # Pyrogram's bare Unauthorized (401). A conflict is matched first, so a
    # duplicated session never lands here.
    "UNAUTHORIZED",
)
CONFLICT_MARKERS = ("AUTH_KEY_DUPLICATED", "SESSION_REVOKED", "CONFLICT")

# Seconds between attempts inside the fast phase, per kind.
FAST_DELAYS = {
    "transient": (15, 30, 60, 120, 240),
    "conflict": (60, 120, 240, 480),
    "fatal": (1800,),
}
SLOW_DELAY = {"transient": 900, "conflict": 900, "fatal": 1800}


def classify(error) -> str:
    """Which kind of failure this is: ``transient``, ``conflict`` or ``fatal``.

    Telegram reports the code in the message text, so match on text rather
    than type: the same ``Unauthorized`` class covers both "wait a moment" and
    "this token is dead", and only the code tells them apart.
    """
    text = str(error or "").upper()
    if any(marker in text for marker in CONFLICT_MARKERS):
        return "conflict"
    if any(marker in text for marker in FATAL_MARKERS):
        return "fatal"
    return "transient"


def retry_delay(attempt: int, kind: str = "transient") -> int:
    """Seconds to wait before attempt ``attempt + 1``.

    ``attempt`` is 1-based. Inside the fast phase the delay doubles from the
    first entry of the kind's schedule; afterwards it settles to the slow
    cadence and stays there for as long as it takes.
    """
    try:
        attempt = max(1, int(attempt))
    except (TypeError, ValueError):
        attempt = 1
    schedule = FAST_DELAYS.get(kind) or FAST_DELAYS["transient"]
    if attempt <= len(schedule):
        return schedule[attempt - 1]
    return SLOW_DELAY.get(kind) or SLOW_DELAY["transient"]


def should_alert(attempt: int, kind: str, previous_kind: str | None) -> bool:
    """Say something once, then only when the nature of the failure changes.

    A retry loop that logs every 15 seconds trains people to ignore it.
    """
    if attempt == 1:
        return True
    return kind != previous_kind


def describe(kind: str) -> str:
    return {
        "transient": "a temporary connection problem — retrying",
        "conflict": "another instance is polling this bot session, so it is retried slowly",
        "fatal": "the bot credentials were rejected — fix them in Render; retrying every 30 minutes",
    }.get(kind, "retrying")
