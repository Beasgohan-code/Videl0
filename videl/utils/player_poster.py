"""Safe, generated now-playing artwork for Telegram player cards.

The poster is original Videl UI: a blurred cover-derived backdrop, vinyl motif,
track metadata chips and a decorative waveform. Pillow is optional at runtime;
when absent, the player keeps its normal thumbnail/text-card path.
"""
from __future__ import annotations

import asyncio
import colorsys
import hashlib
import io
import logging
import re
from collections import OrderedDict
from urllib.parse import urlsplit

try:
    import aiohttp
except Exception:  # pragma: no cover - requirements normally provide it
    aiohttp = None

log = logging.getLogger(__name__)

try:  # Optional so playback never depends on image rendering.
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
except Exception:  # pragma: no cover - exercised on lean deployments
    Image = ImageDraw = ImageEnhance = ImageFilter = ImageFont = ImageOps = None

WIDTH, HEIGHT = 1280, 720
MAX_COVER_BYTES = 1_500_000
CACHE_LIMIT = 16
_ALLOWED_HOSTS = {
    "i.ytimg.com", "img.youtube.com", "yt3.ggpht.com",
    "lh3.googleusercontent.com", "i.scdn.co", "c.saavncdn.com",
}
_CACHE: OrderedDict[str, bytes] = OrderedDict()


def _usable_pillow() -> bool:
    return Image is not None


def _allowed_cover_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.hostname.lower() in _ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
        )
    except (TypeError, ValueError):
        return False


async def _cover_bytes(url: str) -> bytes | None:
    """Fetch only known artwork CDNs, without redirects or unbounded reads."""
    if aiohttp is None or not _allowed_cover_url(url):
        return None
    timeout = aiohttp.ClientTimeout(total=6, connect=3, sock_read=4)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                allow_redirects=False,
                headers={"Accept": "image/jpeg,image/png,image/webp", "User-Agent": "VidelPlayer/1.0"},
            ) as response:
                if response.status != 200:
                    return None
                mime = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                if mime not in {"image/jpeg", "image/png", "image/webp"}:
                    return None
                if response.content_length and response.content_length > MAX_COVER_BYTES:
                    return None
                data = bytearray()
                async for chunk in response.content.iter_chunked(32 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_COVER_BYTES:
                        return None
                return bytes(data) if data else None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.debug("Now-playing artwork fetch skipped (%s)", type(exc).__name__)
        return None


def _font(size: int, *, bold: bool = False, text: str = ""):
    if any("\u0d00" <= char <= "\u0d7f" for char in text):
        family = "NotoSansMalayalam"
        candidates = (f"/usr/share/fonts/truetype/noto/{family}-{'Bold' if bold else 'Regular'}.ttf",)
    elif any("\u0900" <= char <= "\u097f" for char in text):
        family = "NotoSansDevanagari"
        candidates = (f"/usr/share/fonts/truetype/noto/{family}-{'Bold' if bold else 'Regular'}.ttf",)
    else:
        candidates = ()
    candidates += (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _accent(cover, seed: str) -> tuple[int, int, int]:
    if cover is not None:
        sample = cover.convert("RGB").resize((1, 1))
        r, g, b = sample.getpixel((0, 0))
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        s = max(0.48, min(0.88, s))
        v = max(0.72, min(0.96, v))
        return tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, s, v))
    digest = hashlib.sha256(seed.encode("utf-8", "replace")).digest()
    h = int.from_bytes(digest[:2], "big") / 65535
    return tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, 0.68, 0.92))


def _fallback_cover(seed: str, accent: tuple[int, int, int]):
    """Create abstract album-like art without importing external imagery."""
    digest = hashlib.sha256(seed.encode("utf-8", "replace")).digest()
    base = tuple(int(c * 0.28) for c in accent)
    art = Image.new("RGB", (520, 520), base)
    draw = ImageDraw.Draw(art, "RGBA")
    for i in range(10):
        x = int(digest[i] / 255 * 520)
        y = int(digest[10 + i] / 255 * 520)
        radius = 36 + digest[(20 + i) % len(digest)] % 130
        alpha = 18 + digest[(i + 4) % len(digest)] % 30
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=(*accent, alpha))
    draw.polygon([(0, 400), (520, 100), (520, 260), (0, 520)], fill=(*accent, 50))
    return art


def _open_cover(data: bytes | None):
    if not data:
        return None
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.width < 32 or probe.height < 32 or probe.width * probe.height > 24_000_000:
                return None
            probe.verify()
        with Image.open(io.BytesIO(data)) as source:
            return ImageOps.exif_transpose(source).convert("RGB")
    except Exception as exc:
        log.debug("Now-playing artwork decode skipped (%s)", type(exc).__name__)
        return None


def _wrap(draw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    words = re.sub(r"\s+", " ", str(text or "").strip()).split(" ")
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        if not current and draw.textbbox((0, 0), word, font=font)[2] > max_width:
            clipped = word
            while clipped and draw.textbbox((0, 0), clipped + "…", font=font)[2] > max_width:
                clipped = clipped[:-1]
            return [clipped + "…"] if clipped else ["…"]
        candidate = f"{current} {word}".strip()
        if not current or draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    consumed = " ".join(lines).split()
    if len(consumed) < len(words) and lines:
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines[:max_lines]


def _art_text(value, limit: int, fallback: str) -> str:
    # Keep scripts and punctuation, but omit emoji codepoints unsupported by
    # most server fonts so names never turn into tofu boxes on the poster.
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] or fallback


def _render(song: dict, cover_bytes: bytes | None) -> bytes:
    title = _art_text(song.get("title"), 180, "Untitled track")
    artist = _art_text(song.get("artist") or song.get("uploader") or song.get("channel"), 100, "Videl Music")
    requester = _art_text(song.get("requester"), 64, "Community")
    duration = str(song.get("duration") or "Live").strip()[:20]
    kind = "VIDEO" if song.get("video") else "AUDIO"
    seed = f"{title}|{artist}|{requester}"

    source = _open_cover(cover_bytes)
    accent = _accent(source, seed)
    if source is None:
        source = _fallback_cover(seed, accent)

    # Atmospheric, low-contrast backdrop sampled from the song's own artwork.
    background = ImageOps.fit(source, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(34))
    background = ImageEnhance.Brightness(background).enhance(0.36).convert("RGBA")
    shade = Image.new("RGBA", (WIDTH, HEIGHT), (7, 9, 18, 156))
    canvas = Image.alpha_composite(background, shade)
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((650, -300, 1470, 520), fill=(*accent, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    canvas = Image.alpha_composite(canvas, glow)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Original Videl record-sleeve composition: the record peeks from behind
    # a framed square of the source artwork.
    cover_size, cover_x, cover_y = 394, 94, 177
    disc_x, disc_y, disc_size = 250, cover_y - 10, 360
    draw.ellipse((disc_x, disc_y, disc_x + disc_size, disc_y + disc_size), fill=(5, 6, 12, 245))
    for ring, alpha in ((18, 28), (36, 22), (58, 18), (82, 13), (108, 11)):
        inset = ring
        draw.ellipse((disc_x + inset, disc_y + inset, disc_x + disc_size - inset,
                      disc_y + disc_size - inset), outline=(*accent, alpha), width=2)
    center = disc_size // 2
    draw.ellipse((disc_x + center - 38, disc_y + center - 38,
                  disc_x + center + 38, disc_y + center + 38), fill=(*accent, 220))
    draw.ellipse((disc_x + center - 8, disc_y + center - 8,
                  disc_x + center + 8, disc_y + center + 8), fill=(12, 14, 22, 255))

    cover = ImageOps.fit(source, (cover_size, cover_size), method=Image.Resampling.LANCZOS)
    cover_mask = Image.new("L", (cover_size, cover_size), 0)
    ImageDraw.Draw(cover_mask).rounded_rectangle((0, 0, cover_size - 1, cover_size - 1), radius=24, fill=255)
    shadow = Image.new("RGBA", (cover_size + 30, cover_size + 30), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((14, 14, cover_size + 14, cover_size + 14), radius=28, fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)), (cover_x - 15, cover_y - 10))
    canvas.paste(cover.convert("RGBA"), (cover_x, cover_y), cover_mask)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((cover_x - 2, cover_y - 2, cover_x + cover_size + 2, cover_y + cover_size + 2),
                           radius=25, outline=(255, 255, 255, 56), width=2)

    # Brand and track metadata are carefully fitted instead of cropped.
    draw.rounded_rectangle((78, 66, 95, 83), radius=5, fill=(*accent, 255))
    draw.rounded_rectangle((101, 66, 108, 83), radius=3, fill=(255, 255, 255, 190))
    draw.text((124, 61), "VIDEL  /  NOW PLAYING", font=_font(20, bold=True), fill=(245, 246, 250, 235))
    draw.text((650, 163), "NOW IN THE ROOM", font=_font(16, bold=True), fill=(*accent, 255))

    title_size = 49
    title_font = _font(title_size, bold=True, text=title)
    title_lines = _wrap(draw, title, title_font, 560, 2)
    while max(draw.textbbox((0, 0), line, font=title_font)[2] for line in title_lines) > 560 and title_size > 34:
        title_size -= 2
        title_font = _font(title_size, bold=True, text=title)
        title_lines = _wrap(draw, title, title_font, 560, 2)
    y = 206
    for line in title_lines:
        draw.text((650, y), line, font=title_font, fill=(250, 250, 252, 255), stroke_width=0)
        y += title_size + 13
    y += 10
    draw.text((652, y), artist or "Videl Music", font=_font(25, text=artist), fill=(208, 211, 222, 235))

    def chip(x: int, top: int, label: str, width: int, icon_color=None):
        draw.rounded_rectangle((x, top, x + width, top + 48), radius=17, fill=(12, 15, 25, 225), outline=(255, 255, 255, 55), width=1)
        if icon_color:
            draw.ellipse((x + 15, top + 18, x + 25, top + 28), fill=(*icon_color, 255))
            draw.text((x + 35, top + 10), label, font=_font(16, bold=True), fill=(239, 241, 247, 245))
        else:
            draw.text((x + 17, top + 10), label, font=_font(16, bold=True), fill=(239, 241, 247, 245))

    chip(650, 407, kind, 112, accent)
    chip(776, 407, duration.upper(), min(170, max(100, len(duration) * 12 + 38)), (239, 187, 92))
    draw.text((652, 481), "REQUESTED BY", font=_font(13, bold=True), fill=(155, 160, 176, 255))
    draw.text((652, 505), requester[:42], font=_font(20, bold=True, text=requester), fill=(239, 241, 247, 255))

    # Decorative equalizer waveform: deterministic per track, not audio data.
    digest = hashlib.sha256(seed.encode("utf-8", "replace")).digest()
    wave_x, wave_y, bars = 652, 596, 46
    gap = 5
    bar_width = 7
    for index in range(bars):
        level = 12 + (digest[index % len(digest)] % 54)
        x = wave_x + index * (bar_width + gap)
        draw.rounded_rectangle((x, wave_y - level // 2, x + bar_width, wave_y + level // 2),
                               radius=3, fill=(*accent, 180 if index < bars * 0.42 else 66))
    draw.text((652, 652), "STREAMING THROUGH VIDEL", font=_font(12, bold=True), fill=(152, 159, 177, 220))

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=88, optimize=True, progressive=True)
    return output.getvalue()


async def build(song: dict) -> bytes | None:
    """Return a cached generated poster, or None when Pillow is unavailable."""
    if not _usable_pillow():
        return None
    title = _art_text(song.get("title"), 180, "Untitled track")
    artist = _art_text(song.get("artist") or song.get("uploader") or song.get("channel"), 100, "")
    requester = _art_text(song.get("requester"), 64, "Community")
    cover_url = str(song.get("thumbnail") or "")[:2048]
    duration = str(song.get("duration") or "Live")[:20]
    cache_key = hashlib.sha256(f"{title}|{artist}|{requester}|{duration}|{cover_url}|{bool(song.get('video'))}".encode("utf-8", "replace")).hexdigest()
    cached = _CACHE.get(cache_key)
    if cached is not None:
        _CACHE.move_to_end(cache_key)
        return cached
    cover = await _cover_bytes(cover_url) if cover_url else None
    # Preserve the existing provider thumbnail fallback if a supplied image
    # cannot be safely fetched; only synthesize abstract art when no image exists.
    if cover_url and cover is None:
        return None
    try:
        poster = await asyncio.to_thread(_render, dict(song), cover)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning("Now-playing poster render skipped (%s)", type(exc).__name__)
        return None
    _CACHE[cache_key] = poster
    while len(_CACHE) > CACHE_LIMIT:
        _CACHE.popitem(last=False)
    return poster
