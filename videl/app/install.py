"""Explicit, idempotent registration; construction/import has no Telegram effects."""
from weakref import WeakKeyDictionary
from pyrogram import filters
from pyrogram.handlers import MessageHandler,CallbackQueryHandler
from .routes import router
from .navigation import navigate

_installed=WeakKeyDictionary()


def install(client):
    if client in _installed:return _installed[client]
    # The registry, not import order or several overlapping decorators, owns these names.
    message=MessageHandler(router.dispatch,filters.command(list(router.commands)))
    callback=CallbackQueryHandler(navigate,filters.regex(r'^(?:v2:setup|v2:section:(?:home|music|manage|protect|tools)|guide:(?:home|music|manage|protect|tools)|cmds:(?:all|music|manage|tools|owner):[0-9]{1,4}|pro_plugins_[0-9]+|pro_music_help|pro_group_help)$'))
    # Record each successfully registered handler for rollback on partial failure.
    registered=[]
    try:
        for handler in (message,callback):
            client.add_handler(handler,group=0)
            registered.append(handler)
    except Exception:
        for handler in registered:client.remove_handler(handler,group=0)
        raise
    _installed[client]=(message,callback)
    return _installed[client]
