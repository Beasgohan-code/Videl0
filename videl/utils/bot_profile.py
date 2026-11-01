"""Helpers for publishing the bundled Videl bot profile image."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
import requests

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOT_PFP = ROOT / "webapp" / "public" / "videl-bot-pfp.png"
UPLOAD_NAME = "profile_photo"
MAX_SOURCE_BYTES = 8 * 1024 * 1024


def download_profile_image(url: str) -> bytes:
    """Fetch a bounded public HTTPS image URL without following redirects."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use a direct HTTPS link to an image.")
    host = parsed.hostname.rstrip(".").casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("That image link is not a public address.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("That image link is not a public address.")
    try:
        response = requests.get(url, timeout=(5, 15), stream=True, allow_redirects=False)
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").split(";", 1)[0].lower().startswith("image/"):
            raise ValueError("The link must point directly to an image file.")
        chunks = []
        size = 0
        for chunk in response.iter_content(64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_SOURCE_BYTES:
                raise ValueError("The image link is too large (maximum 8 MB).")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise ValueError("The image link returned an empty file.")
        return data
    except requests.RequestException as error:
        raise ValueError("Could not download that image. Use a direct, public HTTPS image link.") from error
    finally:
        if "response" in locals():
            response.close()


def profile_photo_upload(source: str | Path | bytes | None = None):
    """Prepare an image as Telegram's required static JPEG multipart upload.

    Accepts the bundled default image, a local path, or image bytes. The image
    is center-cropped to a square, flattened on Videl's dark background, and
    bounded to 640×640 so transparent logos and oversized files are safe.
    """
    image_source = source if source is not None else DEFAULT_BOT_PFP
    if isinstance(image_source, bytes):
        input_image = BytesIO(image_source)
    else:
        input_image = Path(image_source)
        if not input_image.is_file():
            raise FileNotFoundError("The bundled Videl bot profile image is missing")

    with Image.open(input_image) as original:
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
