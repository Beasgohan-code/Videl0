# Videl's command plugins. Each plugin owns its commands and watchers.
import importlib
import logging
import pathlib

from videl import LOGGER

logger = logging.getLogger(__name__)
PLUGINS_DIR = pathlib.Path(__file__).parent.parent / "plugins"
WATCHER_PLUGINS = ("afk", "locks", "notes", "welcome", "reminder")
LOADED: list[str] = []
FAILED: list[tuple[str, str]] = []

for slug in WATCHER_PLUGINS:
    if not (PLUGINS_DIR / f"{slug}.py").is_file():
        FAILED.append((slug, "source missing"))
        continue
    try:
        importlib.import_module(f"videl.plugins.{slug}")
        LOADED.append(slug)
    except Exception as exc:
        FAILED.append((slug, str(exc)[:160]))
        logger.exception("Plugin %s failed to load", slug)

LOGGER.info("Command plugins active: %d/%d", len(LOADED), len(WATCHER_PLUGINS))
if FAILED:
    LOGGER.error("Plugin load failures: %s", FAILED)
