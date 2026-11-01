"""Reusable, volatile conversation state for staged group-settings edits.

Drafts deliberately remain process-local: no setting changes until a preview is
explicitly confirmed. A restart therefore discards drafts rather than replaying
an untrusted or stale mutation. Callers own Telegram transport, live permission
checks, and an atomic/revision-aware persistence operation.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Sequence
from urllib.parse import urlsplit


_ALLOWED_MEDIA = frozenset({"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"})
_DURATION = re.compile(r"^\s*(\d{1,7})\s*(s|sec|m|min|h|d|w)\s*$", re.IGNORECASE)
_DURATION_MULTIPLIER = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "d": 86400, "w": 604800}


class InputError(ValueError):
    """User input failed the declared step's validation."""


@dataclass(frozen=True)
class Step:
    key: str
    prompt: str
    kind: str = "text"
    required: bool = True
    max_length: int = 4096
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] = ()
    allowed_callbacks: tuple[str, ...] = ()

    def validate(self, value: Any) -> Any:
        if self.kind == "text":
            if not isinstance(value, str):
                raise InputError("Send text for this step.")
            value = value.strip()
            if not value and self.required:
                raise InputError("This value cannot be empty.")
            if len(value) > self.max_length:
                raise InputError(f"Keep this value to {self.max_length} characters or fewer.")
            return value
        if self.kind == "media":
            if value is None and not self.required:
                return None
            if not isinstance(value, Mapping) or value.get("type") not in _ALLOWED_MEDIA or not isinstance(value.get("file_id"), str) or not value["file_id"] or len(value["file_id"]) > 512 or any(char.isspace() for char in value["file_id"]):
                raise InputError("Send a supported Telegram photo, video, animation, document, audio, voice, video note, or sticker.")
            return {"type": value["type"], "file_id": value["file_id"]}
        if self.kind == "url":
            if not isinstance(value, str) or len(value.strip()) > self.max_length:
                raise InputError("Send one valid HTTPS URL.")
            value = value.strip()
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise InputError("Use an HTTPS URL with a hostname and no embedded credentials.")
            return value
        if self.kind == "number":
            if isinstance(value, bool):
                raise InputError("Send a whole number.")
            try:
                parsed = int(str(value).strip())
            except (TypeError, ValueError):
                raise InputError("Send a whole number.") from None
            if self.minimum is not None and parsed < self.minimum or self.maximum is not None and parsed > self.maximum:
                raise InputError("That number is outside the allowed range.")
            return parsed
        if self.kind == "duration":
            if not isinstance(value, str):
                raise InputError("Send a duration such as 30m, 2h, or 1d.")
            match = _DURATION.fullmatch(value)
            if not match:
                raise InputError("Use a duration such as 30m, 2h, or 1d.")
            number, unit = int(match.group(1)), match.group(2).casefold()
            seconds = number * _DURATION_MULTIPLIER[unit]
            if self.minimum is not None and seconds < self.minimum or self.maximum is not None and seconds > self.maximum:
                raise InputError("That duration is outside the allowed range.")
            return seconds
        if self.kind == "selection":
            if not isinstance(value, str) or value not in self.choices:
                raise InputError("Choose one of the offered options.")
            return value
        if self.kind == "buttons":
            if not isinstance(value, str):
                raise InputError("Send one button per line as Label | https://example.com.")
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            if len(lines) > 8:
                raise InputError("Configure no more than 8 buttons.")
            result = []
            for line in lines:
                if "|" not in line:
                    raise InputError("Use one button per line as Label | https://example.com.")
                label, target = (part.strip() for part in line.split("|", 1))
                if not label or len(label) > 32:
                    raise InputError("Button labels must be 1–32 characters.")
                if target.startswith("callback:"):
                    callback = target[len("callback:"):]
                    if callback not in self.allowed_callbacks:
                        raise InputError("That button action is not enabled for this workflow.")
                else:
                    parsed = urlsplit(target)
                    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                        raise InputError("Button links must be HTTPS URLs with no embedded credentials.")
                result.append({"label": label, "target": target})
            return result
        raise ValueError(f"Unsupported interaction step kind: {self.kind}")


@dataclass
class Session:
    token: str
    chat_id: int
    actor_id: int
    target_chat_id: int
    workflow: str
    steps: tuple[Step, ...]
    timeout_seconds: int
    created_at: float
    expires_at: float
    revision: int | None = None
    index: int = 0
    phase: str = "input"
    expected_message_id: int | None = None
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def current_step(self) -> Step | None:
        return self.steps[self.index] if self.phase == "input" and self.index < len(self.steps) else None


@dataclass(frozen=True)
class CaptureResult:
    status: str  # accepted, invalid, preview, expired, unauthorized, stale
    session: Session | None = None
    error: str | None = None


class InteractionEngine:
    """Concurrency-safe in-memory sessions, isolated by chat, actor and target."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._sessions: dict[str, Session] = {}
        self._owners: dict[tuple[int, int, int], str] = {}
        self._lock = asyncio.Lock()

    def _remove(self, session: Session) -> None:
        self._sessions.pop(session.token, None)
        self._owners.pop((session.chat_id, session.actor_id, session.target_chat_id), None)

    def _expire(self, now: float) -> list[Session]:
        expired = [session for session in self._sessions.values() if session.phase != "committing" and session.expires_at <= now]
        for session in expired:
            self._remove(session)
        return expired

    async def begin(self, *, chat_id: int, actor_id: int, target_chat_id: int, workflow: str,
                    steps: Sequence[Step], revision: int | None = None, timeout_seconds: int = 600) -> Session:
        if not steps or timeout_seconds < 1:
            raise ValueError("A session needs at least one step and a positive timeout.")
        now = self._clock()
        owner_key = (int(chat_id), int(actor_id), int(target_chat_id))
        async with self._lock:
            self._expire(now)
            if owner_key in self._owners:
                raise RuntimeError("This admin already has an active settings interaction for that group.")
            token = secrets.token_urlsafe(9)
            session = Session(token, *owner_key, str(workflow), tuple(steps), int(timeout_seconds), now,
                              now + int(timeout_seconds), revision=revision)
            self._sessions[token] = session
            self._owners[owner_key] = token
            return session

    async def get(self, token: str, *, chat_id: int, actor_id: int, target_chat_id: int | None = None) -> Session | None:
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None or session.chat_id != int(chat_id) or session.actor_id != int(actor_id):
                return None
            if target_chat_id is not None and session.target_chat_id != int(target_chat_id):
                return None
            return session

    async def for_owner(self, *, chat_id: int, actor_id: int, target_chat_id: int | None = None) -> Session | None:
        """Return an active session only when the owner/scope tuple is unambiguous."""
        async with self._lock:
            self._expire(self._clock())
            matches = [session for session in self._sessions.values()
                       if session.chat_id == int(chat_id) and session.actor_id == int(actor_id)
                       and (target_chat_id is None or session.target_chat_id == int(target_chat_id))]
            return matches[0] if len(matches) == 1 else None

    async def for_prompt(self, *, chat_id: int, actor_id: int, message_id: int) -> Session | None:
        """Resolve a reply against its exact ForceReply prompt across targets."""
        async with self._lock:
            self._expire(self._clock())
            return next((session for session in self._sessions.values()
                         if session.chat_id == int(chat_id) and session.actor_id == int(actor_id)
                         and session.expected_message_id == int(message_id)), None)

    async def bind_prompt(self, token: str, *, chat_id: int, actor_id: int, message_id: int) -> bool:
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None or session.chat_id != int(chat_id) or session.actor_id != int(actor_id) or session.phase not in {"input", "preview"}:
                return False
            session.expected_message_id = int(message_id)
            session.expires_at = self._clock() + session.timeout_seconds
            return True

    async def capture(self, token: str, *, chat_id: int, actor_id: int, target_chat_id: int,
                      reply_to_message_id: int | None, value: Any) -> CaptureResult:
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None:
                return CaptureResult("expired")
            if (session.chat_id, session.actor_id, session.target_chat_id) != (int(chat_id), int(actor_id), int(target_chat_id)):
                return CaptureResult("unauthorized")
            if session.phase != "input" or session.expected_message_id is None or session.expected_message_id != reply_to_message_id:
                return CaptureResult("stale", session)
            step = session.current_step
            if step is None:
                return CaptureResult("stale", session)
            try:
                parsed = step.validate(value)
            except InputError as exc:
                return CaptureResult("invalid", session, str(exc))
            session.values[step.key] = parsed
            session.index += 1
            session.expected_message_id = None
            session.expires_at = self._clock() + session.timeout_seconds
            if session.index == len(session.steps):
                session.phase = "preview"
                return CaptureResult("preview", session)
            return CaptureResult("accepted", session)

    async def cancel(self, token: str, *, chat_id: int, actor_id: int) -> bool:
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None or session.chat_id != int(chat_id) or session.actor_id != int(actor_id):
                return False
            self._remove(session)
            return True

    async def cancel_owner(self, *, chat_id: int, actor_id: int, target_chat_id: int | None = None) -> bool:
        async with self._lock:
            self._expire(self._clock())
            keys = [key for key in self._owners if key[0] == int(chat_id) and key[1] == int(actor_id)
                    and (target_chat_id is None or key[2] == int(target_chat_id))]
            if len(keys) != 1:
                return False
            session = self._sessions.get(self._owners[keys[0]])
            if session is None:
                return False
            self._remove(session)
            return True

    async def edit_again(self, token: str, *, chat_id: int, actor_id: int, message_id: int) -> Session | None:
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None or session.chat_id != int(chat_id) or session.actor_id != int(actor_id):
                return None
            if session.phase != "preview" or session.expected_message_id != int(message_id):
                return None
            session.phase, session.index, session.values, session.expected_message_id = "input", 0, {}, None
            session.expires_at = self._clock() + session.timeout_seconds
            return session

    async def commit(self, token: str, *, chat_id: int, actor_id: int, target_chat_id: int, message_id: int,
                     authorize: Callable[[int, int], Awaitable[bool]],
                     save: Callable[[Session], Awaitable[bool]]) -> tuple[str, Session | None]:
        """Claim confirmation once, recheck live authorization, then call an atomic saver.

        A failed authorization/save returns the session to preview; only a successful
        saver removes it. The saver must use a revision-aware/transactional write.
        """
        async with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(token)
            if session is None:
                return "expired", None
            if (session.chat_id, session.actor_id, session.target_chat_id) != (int(chat_id), int(actor_id), int(target_chat_id)):
                return "unauthorized", None
            if session.phase != "preview" or session.expected_message_id != int(message_id):
                return "stale", session
            session.phase = "committing"
            snapshot = Session(**{**session.__dict__, "values": dict(session.values)})
        try:
            authorized = await authorize(snapshot.target_chat_id, snapshot.actor_id)
        except Exception:
            authorized = False
        if not authorized:
            outcome = "permission_denied"
        else:
            try:
                saved = await save(snapshot)
            except Exception:
                saved = False
            outcome = "saved" if saved else "save_failed"
        async with self._lock:
            current = self._sessions.get(token)
            if current is not session:
                return "expired", None
            if outcome == "saved":
                self._remove(session)
                return outcome, None
            session.phase = "preview"
            session.expires_at = self._clock() + session.timeout_seconds
            return outcome, session


engine = InteractionEngine()
