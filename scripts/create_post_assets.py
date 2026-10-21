"""Build the original, locally bundled image library for Videl Post Studio.

Three collections, all drawn from scratch with Pillow (no stock photos, no
network access):

* editorial covers  1200 × 675  (16:9)  — attach to posts or download
* story cards       1080 × 1350 (4:5)   — events, launches, save-the-date
* quote cards       1080 × 1080 (1:1)   — shareable statements

Running this script also rewrites ``webapp/src/lib/post-assets.ts`` so the UI
never keeps a second, stale copy of the catalogue.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "webapp/public/post-assets"
MANIFEST = Path(__file__).resolve().parents[1] / "webapp/src/lib/post-assets.ts"
FONTS = Path("/usr/share/fonts/truetype/dejavu")

SERIF = FONTS / "DejaVuSerif.ttf"
SERIF_BOLD = FONTS / "DejaVuSerif-Bold.ttf"
SANS = FONTS / "DejaVuSans.ttf"
SANS_BOLD = FONTS / "DejaVuSans-Bold.ttf"
MONO = FONTS / "DejaVuSansMono.ttf"

# slug, title, eyebrow, background, ink, accent
COVERS = [
    ("community", "Community notes", "A PLACE TO BELONG", "#e9e4d8", "#244a40", "#a6b8a4"),
    ("announcement", "Something new.", "THE LATEST UPDATE", "#202b29", "#f2ebdf", "#7d9a86"),
    ("event", "Save the date.", "LET'S GET TOGETHER", "#e7d6c4", "#533b35", "#b77f65"),
    ("welcome", "You belong here.", "WELCOME TO THE COMMUNITY", "#e1e8de", "#354b3b", "#9bad94"),
    ("launch", "A new chapter.", "MADE FOR WHAT'S NEXT", "#292c37", "#f3e9d5", "#a6997b"),
    ("weekly", "The weekly edit.", "IDEAS / PEOPLE / PROGRESS", "#f0e9da", "#55463b", "#c5b294"),
    ("ocean", "Room to breathe.", "TAKE A FRESH PERSPECTIVE", "#d9e5e8", "#274751", "#91adb4"),
    ("milestone", "Look how far.", "A MOMENT WORTH SHARING", "#e9d8cd", "#624335", "#bd967d"),
    ("workshop", "Learn together.", "GOOD IDEAS START HERE", "#dddccf", "#414635", "#a2a68c"),
    ("spotlight", "In the spotlight.", "MEET YOUR COMMUNITY", "#323b42", "#ede6d8", "#82969d"),
    ("minimal", "Less, but better.", "A LITTLE CLARITY", "#eeeae3", "#383b3a", "#bcbbb4"),
    ("thankyou", "Better, together.", "THANK YOU FOR BEING HERE", "#dfdfd2", "#4b513e", "#a1a78a"),
    ("ship", "Ship something real.", "FROM THE PRODUCT TEAM", "#141b21", "#f4f1e7", "#6ea8a0"),
    ("behind", "Behind the build.", "NOTES FROM THE MAKERS", "#dfe3d8", "#26332c", "#8ea184"),
    ("release", "Release notes.", "WHAT CHANGED THIS WEEK", "#1f2438", "#eef0fb", "#8f9bd4"),
    ("roadmap", "What comes next.", "A LOOK AHEAD", "#efe7d6", "#463c31", "#b9a179"),
    ("study", "Study with us.", "A LEARNING COMMUNITY", "#e4e9e2", "#2f4438", "#93a98f"),
    ("read", "Read something good.", "THE READING LIST", "#2b2620", "#f2e8d5", "#b69769"),
    ("questions", "Ask better questions.", "CURIOSITY, PRACTISED", "#dfe6e7", "#243b42", "#8aa9ae"),
    ("notes", "Notes from the field.", "OBSERVATIONS & LESSONS", "#e8ddcf", "#4a3d33", "#b39172"),
    ("radio", "Live from the studio.", "ON AIR / EPISODE 01", "#1c2230", "#f2f0ea", "#9aa6d8"),
    ("gallery", "A space for makers.", "OPEN STUDIO", "#e6e0d6", "#3a3a35", "#a9a293"),
    ("open", "Built in the open.", "HOW WE WORK", "#22302b", "#eaf0e6", "#89a89a"),
    ("people", "People first.", "CULTURE, NOT DECOR", "#eee3d6", "#4c3b32", "#c09a7d"),
    ("promo", "A little offer.", "FOR YOUR COMMUNITY", "#1b2430", "#f3efe4", "#c2a878"),
    ("invite", "Bring someone.", "GROW THE ROOM", "#e6e2d6", "#2f4038", "#9fb2a0"),
    ("choices", "You decide.", "ASK YOUR PEOPLE", "#2a3140", "#eff2f8", "#98a8d4"),
    ("recap", "The week, wrapped.", "WHAT HAPPENED", "#e9dfd2", "#44382d", "#b99a76"),
    ("manifesto", "Why we build.", "OUR POINT OF VIEW", "#20261f", "#eef0e6", "#9aa886"),
    ("casefile", "How it worked.", "A SHORT CASE STUDY", "#dfe4e6", "#26353c", "#8fa7ae"),
    ("letter", "Straight to you.", "THE MONTHLY LETTER", "#f0e8da", "#4a3d31", "#c0a67e"),
    ("studio", "Inside the studio.", "HOW IT COMES TOGETHER", "#171c22", "#f1ece2", "#8da2a8"),
    ("glow", "Turn the lights up.", "A NIGHT TO REMEMBER", "#241c33", "#f5efff", "#b6a2e4"),
    ("quiet", "Say it simply.", "LESS, AND BETTER", "#ece8e0", "#383a36", "#b0aea4"),
]

STORIES = [
    ("story-date", "Save the date", "Thursday · 7 PM", "#17313f", "#ecf6f7", "#8bc0cd", "EVENT"),
    ("story-live", "We're live", "Join the room", "#2b2340", "#f6f0ff", "#b7a6e6", "LIVE"),
    ("story-drop", "New drop", "Out now", "#3a2019", "#fff1e8", "#e0a184", "RELEASE"),
    ("story-join", "Join us", "Doors are open", "#1d3130", "#eef7f2", "#8fc4ac", "COMMUNITY"),
    ("story-week", "This week", "Three things worth your time", "#efe6d7", "#3f3a2f", "#b3a183", "EDIT"),
    ("story-ask", "Say hello", "We read everything", "#232a3d", "#eef2ff", "#9aabdf", "INBOX"),
    ("story-poll", "Cast a vote", "One tap · two options", "#1e2a33", "#eef6f8", "#8fb6c0", "POLL"),
    ("story-recap", "The week", "Three highlights, one minute", "#efe7d8", "#3f392e", "#b4a082", "RECAP"),
    ("story-invite", "Bring a friend", "Doors open at six", "#222d3c", "#f0f4ff", "#9cabdd", "INVITE"),
    ("story-quiet", "Quiet hours", "Take the evening off", "#26262c", "#f4f2ee", "#a9a8b4", "PAUSE"),
]

QUOTES = [
    ("quote-small", "Small steps, real progress.", "ON SHOWING UP", "#e9e4d8", "#2b3d34", "#a7b7a2"),
    ("quote-room", "Make room for ideas.", "ON CURIOSITY", "#1f2a31", "#f1ede3", "#8fb1bd"),
    ("quote-public", "Build in public.", "ON WORKING OPENLY", "#e4ded2", "#3b352c", "#b0a184"),
    ("quote-human", "Keep it human.", "ON COMMUNITY", "#31252b", "#f6ece8", "#c39a9f"),
    ("quote-start", "Start before you're ready.", "ON BEGINNINGS", "#222f2a", "#eaf1e8", "#93ad9d"),
    ("quote-work", "Show your work.", "ON CRAFT", "#eae2d4", "#40372c", "#b59d7a"),
    ("quote-focus", "Protect your focus.", "ON ATTENTION", "#1e2a2b", "#edf3f0", "#93b3aa"),
    ("quote-patience", "Patience is a strategy.", "ON THE LONG GAME", "#e8e0d3", "#3c362d", "#b19875"),
    ("quote-kind", "Be kind in public.", "ON MANNERS", "#2c2530", "#f7edf2", "#c29cad"),
    ("quote-edit", "Cut the noise.", "ON EDITING", "#232a26", "#eef1ea", "#9bab9d"),
]


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit_text(draw: ImageDraw.ImageDraw, text: str, path: Path, size: int, width: int, minimum: int = 22):
    """Shrink a font until the line fits, so long titles never overflow."""
    while size > minimum:
        candidate = font(path, size)
        if draw.textlength(text, font=candidate) <= width:
            return candidate
        size -= 2
    return font(path, minimum)


def gradient(size: tuple[int, int], top: str, bottom: str, diagonal: bool = False) -> Image.Image:
    width, height = size
    top_rgb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            mix = (x / width * 0.45 + y / height * 0.55) if diagonal else (y / height)
            pixels[x, y] = tuple(round(top_rgb[c] + (bottom_rgb[c] - top_rgb[c]) * mix) for c in range(3))
    return image


def soften(base: Image.Image, amount: int = 10) -> Image.Image:
    return base.filter(ImageFilter.GaussianBlur(amount))


def grain(image: Image.Image, seed: int, strength: int = 9) -> None:
    """Deterministic film grain so every asset is reproducible."""
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    for _ in range(width * height // 90):
        x, y = rng.randrange(width), rng.randrange(height)
        value = 255 if rng.random() > 0.5 else 0
        draw.point((x, y), fill=(value, value, value, strength))


def artwork_cover(image: Image.Image, index: int, ink: str, accent: str) -> None:
    """Five original geometric compositions, cycled across the catalogue."""
    draw = ImageDraw.Draw(image, "RGBA")
    ink_rgba = tuple(int(ink[i : i + 2], 16) for i in (1, 3, 5)) + (60,)
    accent_rgba = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5)) + (190,)
    kind = index % 5
    if index >= 24:
        # Compositions 5 and 6 belong to the second collection so the original
        # twenty-four files stay byte-identical when the script is re-run.
        kind = 5 + (index % 2)
    if kind == 0:
        for offset in range(7):
            draw.arc((760 - offset * 34, 60 + offset * 26, 1320 - offset * 34, 620 + offset * 26), 0, 360, fill=accent_rgba, width=2)
        draw.ellipse((930, 250, 1060, 380), fill=ink_rgba)
    elif kind == 1:
        draw.rounded_rectangle((880, 70, 1090, 560), radius=105, fill=accent_rgba)
        draw.ellipse((790, 340, 1020, 590), fill=ink_rgba)
    elif kind == 2:
        for offset in range(9):
            x = 800 + offset * 32
            draw.line((x, 95, x - 110, 555), fill=accent_rgba, width=3)
        draw.ellipse((930, 90, 1110, 270), outline=ink_rgba, width=3)
    elif kind == 3:
        for row in range(6):
            for column in range(6):
                radius = 3 + ((row + column) % 4) * 2
                draw.ellipse((820 + column * 46 - radius, 110 + row * 62 - radius, 820 + column * 46 + radius, 110 + row * 62 + radius), fill=accent_rgba)
        draw.line((820, 500, 1120, 500), fill=ink_rgba, width=2)
    elif kind == 4:
        for band in range(5):
            x0 = 810 + band * 54
            draw.polygon([(x0, 90), (x0 + 42, 90), (x0 + 130, 560), (x0 + 88, 560)], fill=accent_rgba if band % 2 else ink_rgba)
        draw.ellipse((965, 230, 1065, 330), fill=(255, 255, 255, 40))
    elif kind == 5:
        # Concentric arcs opening to the right.
        for step in range(9):
            draw.arc((700 - step * 24, 40 + step * 26, 1360 - step * 24, 700 + step * 26), 200, 340, fill=accent_rgba, width=2)
        draw.rounded_rectangle((930, 300, 1080, 380), radius=40, fill=ink_rgba)
    else:
        # Offset squares with one solid anchor.
        for step in range(7):
            origin = 790 + step * 34
            draw.rectangle((origin, 70 + step * 18, origin + 150, 220 + step * 18), outline=accent_rgba, width=2)
        draw.rectangle((990, 330, 1130, 470), fill=ink_rgba)


def build_covers():
    for index, (slug, title, eyebrow, bg, ink, accent) in enumerate(COVERS):
        image = gradient((1200, 675), bg, bg, diagonal=True) if index % 4 == 0 else Image.new("RGB", (1200, 675), bg)
        artwork_cover(image, index, ink, accent)
        grain(image, seed=index + 1)
        draw = ImageDraw.Draw(image)
        draw.rectangle((32, 32, 1168, 643), outline=accent, width=1)
        title_font = fit_text(draw, title, SERIF, 66, 700, minimum=40)
        small = font(SANS, 17)
        draw.text((76, 82), eyebrow, fill=ink, font=small)
        draw.line((76, 235, 145, 235), fill=ink, width=3)
        draw.text((72, 268 - (title_font.size - 66) // 2), title, fill=ink, font=title_font)
        draw.text((78, 385), "STORIES WORTH SHARING", fill=ink, font=small)
        draw.text((78, 580), "VIDEL POST STUDIO", fill=ink, font=small)
        draw.text((1060, 580), f"{index + 1:02}", fill=ink, font=small)
        image.save(ROOT / f"{slug}.png", optimize=True)


def build_stories():
    for index, (slug, title, subtitle, bg, ink, accent, eyebrow) in enumerate(STORIES):
        image = gradient((1080, 1350), bg, "#0d141a" if index % 2 else bg, diagonal=True)
        draw = ImageDraw.Draw(image, "RGBA")
        accent_rgba = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5)) + (150,)
        for ring in range(10):
            radius = 90 + ring * 62
            draw.ellipse((540 - radius, 610 - radius, 540 + radius, 610 + radius), outline=accent_rgba, width=2)
        draw.ellipse((742, 812, 962, 1032), fill=accent_rgba)
        grain(image, seed=100 + index)
        draw = ImageDraw.Draw(image)
        small = font(SANS_BOLD, 20)
        draw.text((84, 92), eyebrow, fill=accent, font=small)
        draw.line((84, 150, 200, 150), fill=accent, width=3)
        title_font = fit_text(draw, title, SERIF_BOLD, 96, 900, minimum=54)
        draw.text((80, 830), title, fill=ink, font=title_font)
        draw.text((84, 830 + title_font.size + 28), subtitle, fill=ink, font=font(SANS, 28))
        draw.text((84, 1260), "VIDEL STUDIO", fill=ink, font=font(SANS, 18))
        draw.text((940, 1260), f"{index + 1:02}", fill=ink, font=font(SANS, 18))
        image.save(ROOT / f"{slug}.png", optimize=True)


def build_quotes():
    for index, (slug, quote, eyebrow, bg, ink, accent) in enumerate(QUOTES):
        image = gradient((1080, 1080), bg, bg, diagonal=True) if index % 3 == 0 else Image.new("RGB", (1080, 1080), bg)
        draw = ImageDraw.Draw(image, "RGBA")
        accent_rgba = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5)) + (170,)
        if index % 2:
            draw.ellipse((-180, 620, 620, 1420), fill=accent_rgba)
            draw.ellipse((760, -220, 1340, 360), outline=accent_rgba, width=3)
        else:
            for step in range(5):
                draw.arc((640 - step * 40, 120 + step * 40, 1300 - step * 40, 780 + step * 40), 180, 360, fill=accent_rgba, width=3)
        grain(image, seed=200 + index)
        draw = ImageDraw.Draw(image)
        draw.rectangle((46, 46, 1034, 1034), outline=accent, width=1)
        draw.text((92, 104), eyebrow, fill=accent, font=font(SANS_BOLD, 19))
        quote_font = fit_text(draw, quote, SERIF_BOLD, 86, 860, minimum=46)
        lines, line = [], ""
        for word in quote.split():
            proposed = f"{line} {word}".strip()
            if draw.textlength(proposed, font=quote_font) <= 860:
                line = proposed
            else:
                lines.append(line)
                line = word
        lines.append(line)
        top = 1040 - len(lines) * (quote_font.size + 18) - 120
        for offset, text in enumerate(lines):
            draw.text((90, top + offset * (quote_font.size + 18)), text, fill=ink, font=quote_font)
        draw.text((92, 966), "VIDEL STUDIO · EDITORIAL", fill=ink, font=font(SANS, 18))
        image.save(ROOT / f"{slug}.png", optimize=True)


def write_manifest():
    entries = []
    for slug, title, _eyebrow, *_rest in COVERS:
        entries.append({"id": slug, "title": title, "file": f"/post-assets/{slug}.png", "aspect": "16:9", "category": "Editorial"})
    for slug, title, subtitle, *_rest in STORIES:
        entries.append({"id": slug, "title": f"{title} · {subtitle}", "file": f"/post-assets/{slug}.png", "aspect": "4:5", "category": "Stories"})
    for slug, quote, eyebrow, *_rest in QUOTES:
        entries.append({"id": slug, "title": quote, "file": f"/post-assets/{slug}.png", "aspect": "1:1", "category": "Quote cards"})
    # The first twelve covers keep the categories the Post Studio already used.
    legacy = {
        "community": "Community", "welcome": "Community", "spotlight": "Community", "thankyou": "Community",
        "announcement": "Announcements", "launch": "Announcements", "milestone": "Announcements",
        "event": "Events", "workshop": "Events",
        "weekly": "Editorial", "ocean": "Editorial", "minimal": "Editorial",
        "promo": "Promotions", "glow": "Promotions", "invite": "Community", "choices": "Community",
        "recap": "Editorial", "manifesto": "Studio", "casefile": "Studio",
        "letter": "Studio", "studio": "Studio", "quiet": "Editorial",
    }
    for entry in entries:
        entry["category"] = legacy.get(entry["id"], entry["category"])
    body = ",\n".join("  " + json.dumps(entry, ensure_ascii=False) for entry in entries)
    MANIFEST.write_text(
        "// Generated by scripts/create_post_assets.py — do not edit by hand.\n"
        "export type PostAsset = { id: string; title: string; file: string; aspect: \"16:9\" | \"4:5\" | \"1:1\"; category: string };\n"
        f"export const POST_ASSETS: PostAsset[] = [\n{body}\n];\n"
        "export const POST_ASSET_CATEGORIES = Array.from(new Set(POST_ASSETS.map((asset) => asset.category)));\n",
        encoding="utf-8",
    )


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    build_covers()
    build_stories()
    build_quotes()
    write_manifest()
    print(f"Wrote {len(COVERS)} covers, {len(STORIES)} stories, {len(QUOTES)} quote cards to {ROOT}")


if __name__ == "__main__":
    build()
