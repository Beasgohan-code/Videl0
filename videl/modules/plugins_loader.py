# --------------------------------------------------------------------------------
#  Videl © 2026 | Plugins Loader — Professional 100-Plugin Suite
#  Dynamically loads all 100 plugins from videl/plugins/*.py — categorized pro
#  Categories: Admin, Music, Anime, Tools, Fun, Utilities, AI-Ready
#  Each plugin is self-contained with Richgram UI • MongoDB • Guest-safe
# --------------------------------------------------------------------------------
import importlib
import pathlib
import logging
from videl import LOGGER

logger = logging.getLogger(__name__)

PLUGINS_DIR = pathlib.Path(__file__).parent.parent / "plugins"
LOADED = []
FAILED = []

if PLUGINS_DIR.exists():
    for p in sorted(PLUGINS_DIR.glob("*.py")):
        if p.name.startswith("_"): continue
        mod_name = f"videl.plugins.{p.stem}"
        try:
            importlib.import_module(mod_name)
            LOADED.append(p.stem)
        except Exception as e:
            FAILED.append((p.stem, str(e)[:120]))
            logger.warning(f"Plugin {p.stem} failed: {e}")
    LOGGER.info(f"◍ Plugins Loader: {len(LOADED)} plugins loaded — {', '.join(LOADED[:10])}{'...' if len(LOADED)>10 else ''}")
    if FAILED:
        LOGGER.warning(f"◍ {len(FAILED)} plugins failed: {FAILED[:3]}")
else:
    LOGGER.warning("Plugins directory not found")
