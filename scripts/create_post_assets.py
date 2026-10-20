"""Rebuild the original, locally bundled editorial PNG cover library (Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "webapp/public/post-assets"
ASSETS = [
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
]

def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 66)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    for i, (slug, title, subtitle, bg, ink, accent) in enumerate(ASSETS):
        image = Image.new("RGB", (1200, 675), bg)
        d = ImageDraw.Draw(image)
        d.rectangle((32, 32, 1168, 643), outline=accent, width=1)
        # Original geometric artwork; each cover is an individual image.
        if i % 3 == 0:
            for offset in range(6):
                d.arc((800-offset*35, 50+offset*30, 1320-offset*35, 570+offset*30), 0, 360, fill=accent, width=2)
            d.ellipse((920, 260, 1040, 380), fill=accent)
        elif i % 3 == 1:
            d.rounded_rectangle((900, 70, 1100, 520), radius=100, fill=accent)
            d.ellipse((805, 355, 1035, 585), fill=ink)
            d.line((830, 100, 830, 550), fill=accent, width=2)
        else:
            for offset in range(8):
                x = 810 + offset * 30
                d.line((x, 105, x-90, 540), fill=accent, width=3)
            d.ellipse((935, 100, 1110, 275), outline=ink, width=3)
        d.text((76, 82), "THE COMMUNITY COLLECTION", fill=ink, font=small)
        d.line((76, 235, 145, 235), fill=ink, width=3)
        d.text((72, 280), title, fill=ink, font=heading)
        d.text((78, 385), subtitle, fill=ink, font=small)
        d.text((78, 580), "STORIES WORTH SHARING", fill=ink, font=small)
        d.text((1060, 580), f"{i+1:02}", fill=ink, font=small)
        image.save(ROOT / f"{slug}.png", optimize=True)

if __name__ == "__main__":
    build()
