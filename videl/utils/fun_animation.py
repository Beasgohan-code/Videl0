"""Nekos.best SFW reaction GIF client with original local loops as an offline fallback."""
from __future__ import annotations

import hashlib
import io
import math
import time
from dataclasses import dataclass
from urllib.parse import urlparse

try:
    import aiohttp
except Exception:  # The locally drawn fallback remains usable without networking.
    aiohttp = None

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # Pillow is optional; commands retain their text response.
    Image = ImageDraw = ImageFont = None

SIZE = 512
_ACTIONS = {"hug", "kiss", "like", "wave", "highfive", "dance"}
_API_ENDPOINTS = {
    "hug": "hug", "kiss": "kiss", "like": "thumbsup",
    "wave": "wave", "highfive": "highfive", "dance": "dance",
}
_API_ROOT = "https://nekos.best/api/v2/"
_MAX_REMOTE_GIF = 8 * 1024 * 1024
_REMOTE_CACHE: dict[str, tuple[float, "ReactionAsset"]] = {}


@dataclass(frozen=True)
class ReactionAsset:
    data: bytes
    anime_name: str = ""
    artist_name: str = ""
    artist_href: str = ""
    source_url: str = ""


def _safe_source_url(value) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return value


async def fetch_reaction(action: str) -> ReactionAsset | None:
    """Fetch a SFW GIF from Nekos.best; never send identities or user text upstream."""
    if action not in _API_ENDPOINTS or aiohttp is None:
        return None
    cached = _REMOTE_CACHE.get(action)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    timeout = aiohttp.ClientTimeout(total=8, connect=3)
    headers = {"User-Agent": "Videl (https://github.com/Beasgohan-code/Videl0)"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(_API_ROOT + _API_ENDPOINTS[action], allow_redirects=False) as response:
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
            rows = payload.get("results") if isinstance(payload, dict) else None
            metadata = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
            url = metadata.get("url")
            parsed = urlparse(url) if isinstance(url, str) else None
            if (
                not parsed or parsed.scheme != "https" or parsed.hostname != "nekos.best"
                or parsed.port or parsed.username or not parsed.path.startswith("/api/v2/")
                or not parsed.path.endswith(".gif")
            ):
                return None
            async with session.get(url, allow_redirects=False) as response:
                if response.status != 200:
                    return None
                length = response.content_length
                if length is not None and length > _MAX_REMOTE_GIF:
                    return None
                data = await response.content.read(_MAX_REMOTE_GIF + 1)
                if len(data) > _MAX_REMOTE_GIF or not data.startswith((b"GIF87a", b"GIF89a")):
                    return None
        def label(name):
            return name.strip()[:160] if isinstance(name, str) else ""

        asset = ReactionAsset(
            data=data,
            anime_name=label(metadata.get("anime_name")),
            artist_name=label(metadata.get("artist_name")),
            artist_href=_safe_source_url(metadata.get("artist_href")),
            source_url=_safe_source_url(metadata.get("source_url")),
        )
        _REMOTE_CACHE[action] = (time.monotonic() + 45, asset)
        return asset
    except Exception:
        # The interaction remains available via the original local renderer.
        return None


def available() -> bool:
    return Image is not None


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _heart(draw, x: float, y: float, size: int, color):
    r = size * 0.28
    draw.ellipse((x - r * 1.5, y - r, x + r * 0.2, y + r * 0.7), fill=color)
    draw.ellipse((x - r * 0.2, y - r, x + r * 1.5, y + r * 0.7), fill=color)
    draw.polygon([(x - r * 1.5, y - r * 0.1), (x + r * 1.5, y - r * 0.1), (x, y + size * 0.72)], fill=color)


def _character(draw, cx: int, bob: int, hair, clothes, *, wink=False, arm="down"):
    # Feet and rounded body
    draw.ellipse((cx - 49, 410 + bob, cx + 49, 431 + bob), fill=(70, 58, 93, 65))
    draw.rounded_rectangle((cx - 42, 302 + bob, cx + 42, 395 + bob), radius=28, fill=clothes, outline=(255, 255, 255), width=3)
    draw.rounded_rectangle((cx - 35, 382 + bob, cx - 7, 426 + bob), radius=13, fill=(250, 216, 194), outline=(90, 70, 86), width=2)
    draw.rounded_rectangle((cx + 7, 382 + bob, cx + 35, 426 + bob), radius=13, fill=(250, 216, 194), outline=(90, 70, 86), width=2)
    draw.ellipse((cx - 42, 416 + bob, cx - 2, 436 + bob), fill=(255, 255, 255), outline=(90, 70, 86), width=2)
    draw.ellipse((cx + 2, 416 + bob, cx + 42, 436 + bob), fill=(255, 255, 255), outline=(90, 70, 86), width=2)

    # Neck, face and hair silhouette
    draw.rounded_rectangle((cx - 13, 272 + bob, cx + 13, 314 + bob), radius=10, fill=(255, 220, 198))
    draw.ellipse((cx - 55, 174 + bob, cx + 55, 292 + bob), fill=(255, 225, 205), outline=(85, 62, 88), width=3)
    draw.pieslice((cx - 61, 154 + bob, cx + 61, 281 + bob), start=180, end=360, fill=hair, outline=(68, 49, 83), width=3)
    draw.polygon([(cx - 58, 220 + bob), (cx - 47, 176 + bob), (cx - 27, 220 + bob),
                  (cx - 4, 166 + bob), (cx + 11, 220 + bob), (cx + 39, 176 + bob),
                  (cx + 58, 222 + bob), (cx + 49, 261 + bob), (cx - 50, 259 + bob)],
                 fill=hair, outline=(68, 49, 83))

    # Oversized anime-inspired eyes, highlights and blush
    eye_y = 237 + bob
    if wink:
        draw.arc((cx - 36, eye_y - 8, cx - 10, eye_y + 9), 195, 345, fill=(54, 44, 72), width=4)
    else:
        draw.ellipse((cx - 35, eye_y - 12, cx - 15, eye_y + 13), fill=(61, 75, 130))
        draw.ellipse((cx - 29, eye_y - 9, cx - 22, eye_y + 4), fill=(255, 255, 255))
    draw.ellipse((cx + 15, eye_y - 12, cx + 35, eye_y + 13), fill=(61, 75, 130))
    draw.ellipse((cx + 21, eye_y - 9, cx + 28, eye_y + 4), fill=(255, 255, 255))
    draw.line((cx - 4, 264 + bob, cx + 4, 264 + bob), fill=(142, 84, 101), width=3)
    draw.ellipse((cx - 46, 256 + bob, cx - 31, 263 + bob), fill=(245, 145, 153, 150))
    draw.ellipse((cx + 31, 256 + bob, cx + 46, 263 + bob), fill=(245, 145, 153, 150))

    # Arms; callers add interaction gestures after both characters are drawn.
    arm_color = (255, 220, 198)
    if arm == "wave":
        draw.line((cx + 31, 322 + bob, cx + 57, 282 + bob, cx + 66, 226 + bob), fill=arm_color, width=17, joint="curve")
        draw.line((cx - 32, 324 + bob, cx - 54, 363 + bob), fill=arm_color, width=17)
    elif arm == "up":
        draw.line((cx - 31, 323 + bob, cx - 59, 282 + bob, cx - 55, 229 + bob), fill=arm_color, width=17, joint="curve")
        draw.line((cx + 31, 323 + bob, cx + 59, 282 + bob, cx + 55, 229 + bob), fill=arm_color, width=17, joint="curve")
    else:
        draw.line((cx - 32, 323 + bob, cx - 53, 367 + bob), fill=arm_color, width=17)
        draw.line((cx + 32, 323 + bob, cx + 53, 367 + bob), fill=arm_color, width=17)
    if arm == "wave":
        draw.ellipse((cx + 56, 210 + bob, cx + 78, 234 + bob), fill=arm_color, outline=(85, 62, 88), width=2)
        draw.ellipse((cx - 61, 357 + bob, cx - 42, 378 + bob), fill=arm_color)
    elif arm == "up":
        draw.ellipse((cx - 67, 217 + bob, cx - 47, 239 + bob), fill=arm_color, outline=(85, 62, 88), width=2)
        draw.ellipse((cx + 47, 217 + bob, cx + 67, 239 + bob), fill=arm_color, outline=(85, 62, 88), width=2)
    else:
        draw.ellipse((cx - 61, 357 + bob, cx - 42, 378 + bob), fill=arm_color)
        draw.ellipse((cx + 42, 357 + bob, cx + 61, 378 + bob), fill=arm_color)


def render(action: str, seed: str = "videl") -> bytes | None:
    """Build a small looping GIF from original vector-drawn artwork."""
    if Image is None or action not in _ACTIONS:
        return None
    digest = hashlib.sha256(f"{action}:{seed}".encode("utf-8", "replace")).digest()
    palettes = [
        ((147, 91, 205), (74, 169, 194), (255, 224, 239)),
        ((238, 117, 145), (107, 115, 211), (255, 234, 208)),
        ((61, 170, 139), (238, 165, 74), (230, 238, 255)),
    ]
    palette = palettes[digest[0] % len(palettes)]
    frames = []
    count = 10
    for frame in range(count):
        phase = 2 * math.pi * frame / count
        bob_a = round(math.sin(phase) * 6)
        bob_b = round(math.sin(phase + math.pi) * 6)
        background = Image.new("RGB", (SIZE, SIZE), (249, 242, 252))
        draw = ImageDraw.Draw(background, "RGBA")
        draw.ellipse((-100, 250, 280, 640), fill=(*palette[2], 150))
        draw.ellipse((300, -170, 650, 190), fill=(224, 226, 255, 130))
        # Tiny starbursts are drawn from primitives, never imported artwork.
        for i in range(18):
            x = 24 + digest[i] % 464
            y = 54 + digest[(i + 9) % len(digest)] % 395
            r = 3 + digest[(i + 16) % len(digest)] % 5
            color = (255, 255, 255, 210) if i % 2 else (*palette[0], 120)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

        if action in {"hug", "kiss"}:
            left_x, right_x = (207, 305) if action == "hug" else (218, 294)
        elif action == "like":
            left_x, right_x = 205, 307
        elif action == "highfive":
            left_x, right_x = 176, 336
        elif action == "dance":
            sway = round(math.sin(phase) * 12)
            left_x, right_x = 176 - sway, 336 + sway
        else:
            left_x, right_x = 188, 324

        arm_left = "up" if action in {"highfive", "dance", "like"} else "wave" if action == "wave" else "down"
        arm_right = "up" if action in {"highfive", "dance"} else "down"
        _character(draw, left_x, bob_a, palette[0], (255, 204, 220), wink=frame % 5 == 0, arm=arm_left)
        _character(draw, right_x, bob_b, palette[1], (195, 201, 255), wink=frame % 6 == 0, arm=arm_right)

        if action == "hug":
            draw.arc((left_x - 5, 302 + bob_a, right_x + 35, 395 + max(bob_a, bob_b)), 190, 350,
                     fill=(255, 220, 198), width=18)
            _heart(draw, 256 + round(math.sin(phase) * 5), 136 - round(abs(math.sin(phase)) * 10), 34,
                   (246, 106, 153, 240))
            _heart(draw, 159, 201 + round(math.sin(phase) * 5), 18, (246, 106, 153, 220))
        elif action == "kiss":
            _heart(draw, 256, 180 - round(abs(math.sin(phase)) * 16), 36, (246, 106, 153, 245))
            draw.ellipse((left_x + 40, 267 + bob_a, left_x + 52, 279 + bob_a), fill=(245, 104, 138))
        elif action == "like":
            pulse = round(math.sin(phase) * 4)
            # A hand-drawn thumbs-up and floating hearts make the action legible
            # without relying on emoji font support inside the GIF itself.
            draw.polygon(
                [(248, 167 + pulse), (250, 143 + pulse), (262, 126 + pulse),
                 (270, 119 + pulse), (278, 124 + pulse), (276, 143 + pulse),
                 (296, 143 + pulse), (302, 149 + pulse), (298, 170 + pulse),
                 (293, 180 + pulse), (263, 180 + pulse), (252, 174 + pulse)],
                fill=(255, 220, 198), outline=(85, 62, 88),
            )
            _heart(draw, 334, 176 - round(abs(math.sin(phase)) * 8), 23, (246, 106, 153, 240))
            _heart(draw, 173, 181 + round(math.sin(phase) * 7), 16, (246, 106, 153, 210))
        elif action == "highfive":
            draw.line((left_x + 55, 228 + bob_a, 256, 166 + round(math.sin(phase) * 5), right_x - 55, 228 + bob_b),
                      fill=(255, 220, 198), width=16, joint="curve")
            for angle in range(0, 360, 45):
                radians = math.radians(angle)
                x, y = 256 + math.cos(radians) * 32, 157 + math.sin(radians) * 32
                draw.line((x, y, x + math.cos(radians) * 12, y + math.sin(radians) * 12), fill=(255, 186, 92), width=5)
        elif action == "wave":
            for offset in (-14, 0, 14):
                draw.arc((left_x + 39 + offset, 194, left_x + 79 + offset, 238), 220, 325, fill=(255, 188, 104), width=4)
        elif action == "dance":
            _heart(draw, left_x, 161 + round(math.sin(phase) * 8), 19, (246, 106, 153, 225))
            _heart(draw, right_x, 145 - round(math.sin(phase) * 8), 15, (246, 106, 153, 225))

        # A friendly, high-contrast footer anchors the animation on Telegram.
        draw.rounded_rectangle((145, 447, 367, 484), radius=18, fill=(255, 255, 255, 220), outline=(220, 211, 235, 255), width=2)
        label = {"hug": "A LITTLE HUG", "kiss": "KINDNESS!", "like": "YOU'RE LIKED!", "wave": "HELLO!", "highfive": "HIGH FIVE!", "dance": "DANCE BREAK!"}[action]
        font = _font(16)
        box = draw.textbbox((0, 0), label, font=font)
        draw.text(((SIZE - (box[2] - box[0])) // 2, 456), label, font=font, fill=(65, 55, 91, 255))
        frames.append(background.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))

    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=105,
                   loop=0, optimize=True, disposal=2)
    return output.getvalue()
