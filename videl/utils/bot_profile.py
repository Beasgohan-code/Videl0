"""Helpers for publishing the bundled Videl bot profile image."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOT_PFP = ROOT / "webapp" / "public" / "videl-bot-pfp.png"
UPLOAD_NAME = "profile_photo"


def profile_photo_upload(path: str | Path | None = None):
    """Prepare the bundled PNG as Telegram's required static JPEG upload.

    Returns the Bot API ``photo`` object and the multipart file mapping. The
    image is center-cropped to a square, flattened on Videl's dark background,
    and bounded to 640×640 so transparent logos and oversized files are safe.
    """
    source = Path(path) if path is not None else DEFAULT_BOT_PFP
    if not source.is_file():
        raise FileNotFoundError("The bundled Videl bot profile image is missing")

    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            foreground = image.convert("RGBA")
            background = Image.new("RGBA", foreground.size, (8, 11, 26, 255))
            background.alpha_composite(foreground)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")
        image = ImageOps.fit(
            image,
            (640, 640),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True, progressive=True)

    photo_bytes = output.getvalue()
    if not photo_bytes:
        raise ValueError("The bundled Videl bot profile image could not be encoded")
    payload = {"photo": {"type": "static", "photo": f"attach://{UPLOAD_NAME}"}}
    files = {UPLOAD_NAME: ("videl-bot-pfp.jpg", photo_bytes, "image/jpeg")}
    return payload, files
