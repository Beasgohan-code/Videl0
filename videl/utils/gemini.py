"""Small, bounded Gemini text-generation client for opt-in bot features."""
from __future__ import annotations

import json
import re

import httpx

import config

MAX_PROMPT_CHARS = 1200
MAX_OUTPUT_CHARS = 1800
_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class GeminiUnavailable(RuntimeError):
    """Gemini is not configured or did not return a usable response."""


def configured() -> bool:
    return bool(str(getattr(config, "GEMINI_API_KEY", "") or "").strip())


async def generate_text_stream(prompt: str, *, system_instruction: str = ""):
    """Yield bounded text deltas from Gemini SSE; cancellation closes the HTTP stream."""
    api_key = str(getattr(config, "GEMINI_API_KEY", "") or "").strip()
    model = str(getattr(config, "GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
    if not api_key or not _MODEL_RE.fullmatch(model):
        raise GeminiUnavailable("Gemini is not configured")
    prompt = str(prompt or "").strip()[:MAX_PROMPT_CHARS]
    system_instruction = str(system_instruction or "").strip()[:500]
    if not prompt:
        raise GeminiUnavailable("No prompt was provided")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.6},
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
    total = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=4.0)) as client:
            async with client.stream("POST", endpoint, headers={"x-goog-api-key": api_key}, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        data = json.loads(raw)
                        candidates = data.get("candidates") if isinstance(data, dict) else None
                        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                        delta = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
                    except Exception:
                        continue
                    if not delta:
                        continue
                    delta = delta[:MAX_OUTPUT_CHARS - total]
                    if delta:
                        total += len(delta)
                        yield delta
                    if total >= MAX_OUTPUT_CHARS:
                        break
        if total == 0:
            raise GeminiUnavailable("Gemini returned no text")
    except GeneratorExit:
        raise
    except GeminiUnavailable:
        raise
    except Exception as exc:
        raise GeminiUnavailable(f"Gemini stream failed ({type(exc).__name__})") from None


async def generate_text(prompt: str, *, system_instruction: str = "") -> str:
    """Generate one short response; never expose provider errors or credentials."""
    api_key = str(getattr(config, "GEMINI_API_KEY", "") or "").strip()
    model = str(getattr(config, "GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
    if not api_key or not _MODEL_RE.fullmatch(model):
        raise GeminiUnavailable("Gemini is not configured")
    prompt = str(prompt or "").strip()[:MAX_PROMPT_CHARS]
    system_instruction = str(system_instruction or "").strip()[:500]
    if not prompt:
        raise GeminiUnavailable("No prompt was provided")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.6},
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
            response = await client.post(endpoint, headers={"x-goog-api-key": api_key}, json=payload)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") if isinstance(data, dict) else None
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise GeminiUnavailable("Gemini returned no text")
        return text[:MAX_OUTPUT_CHARS]
    except GeminiUnavailable:
        raise
    except Exception as exc:
        # Do not chain provider exceptions: some HTTP clients include request URLs.
        raise GeminiUnavailable(f"Gemini request failed ({type(exc).__name__})") from None
