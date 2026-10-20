# Videl's curated professional command plugins.
# Only commands with a verified implementation are enabled; entertainment,
# abandoned/demo commands, duplicated core routes, and all AI commands are out.
import importlib
import logging
import pathlib

from videl import LOGGER

logger = logging.getLogger(__name__)
PLUGINS_DIR = pathlib.Path(__file__).parent.parent / "plugins"
PROFESSIONAL_PLUGINS = (
    "afk", "barcode", "channel", "clean", "currency", "define", "ebook",
    "filters_pro", "font", "google", "helper_pro", "idpro", "invite",
    "language", "lastfm", "lyricspro", "musichelp", "notes_pro",
    "paste", "pollpro", "reminder", "rules_pro", "scheduler", "sticker_tools",
    "tagall", "telegraph2", "telegraph_pro", "timer", "trace", "translate",
    "unshort", "userinfo", "ytsearch", "tts",
)
LOADED: list[str] = []
FAILED: list[tuple[str, str]] = []

for slug in PROFESSIONAL_PLUGINS:
    if not (PLUGINS_DIR / f"{slug}.py").is_file():
        FAILED.append((slug, "source missing"))
        continue
    try:
        importlib.import_module(f"videl.plugins.{slug}")
        LOADED.append(slug)
    except Exception as exc:
        FAILED.append((slug, str(exc)[:160]))
        logger.exception("Professional plugin %s failed to load", slug)

LOGGER.info("Professional utility plugins loaded: %d/%d", len(LOADED), len(PROFESSIONAL_PLUGINS))
if FAILED:
    LOGGER.error("Professional plugin load failures: %s", FAILED)
