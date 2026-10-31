#  Videl © 2026 | Beasgohan-code
"""Videl's command plugins.

Each module owns a domain: ``start``, ``help``, ``afk``, ``reminder``,
``moderation``, ``locks``, ``notes``, ``welcome``, ``group``, ``tools``,
``privacy``, ``preferences``, ``retention`` and ``stickers``.
Modules export a ``COMMANDS`` tuple; :mod:`videl.app.routes` assembles the
router manifest from them and :mod:`videl.modules.plugins_loader` imports them
so their message watchers register with the bot.
"""

WATCHER_PLUGINS = ("afk", "locks", "notes", "welcome", "reminder")
COMMAND_PLUGINS = ("start", "help", "tools", "moderation", "locks", "notes", "welcome", "group", "afk", "reminder", "stickers", "appeals", "sudo", "privacy", "preferences", "retention", "faq", "settings")
