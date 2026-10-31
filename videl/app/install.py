"""Explicit, idempotent registration; construction/import has no Telegram effects."""
from weakref import WeakKeyDictionary
from pyrogram import filters
from pyrogram.handlers import MessageHandler,CallbackQueryHandler
from .routes import router
import config
from .navigation import navigate

_installed=WeakKeyDictionary()


def install(client):
    if client in _installed:return _installed[client]
    # The registry, not import order or several overlapping decorators, owns these names.
    message=MessageHandler(router.dispatch,filters.command(list(router.commands), prefixes=config.COMMAND_PREFIX_LIST))
    callback=CallbackQueryHandler(navigate,filters.regex(r'^(?:v2:setup|v2:section:(?:home|music|manage|protect|tools)|help:(?:home|about|music|manage|tools|owner|start)(?::[0-9]{1,3})?|cmds:(?:all|music|manage|tools|owner):[0-9]{1,4}|pro_plugins_[0-9]+|pro_music_help|pro_group_help)$'))
    handlers=[message,callback]
    try:
        from videl.utils.telegram_features import capabilities
        supported = capabilities(client)
        if supported.guest_mode:
            from pyrogram.handlers import GuestMessageHandler
            from videl.plugins.guest_mode import handle_guest_message
            handlers.append(GuestMessageHandler(handle_guest_message))
        if supported.business_connection_updates:
            from pyrogram.handlers import BusinessConnectionHandler
            from videl.plugins.business_profile import remember_business_connection

            async def handle_business_connection(_client, connection):
                remember_business_connection(connection)

            handlers.append(BusinessConnectionHandler(handle_business_connection))
    except Exception:
        # Guest mode is optional; unknown client signatures fail closed.
        pass
    # Record each successfully registered handler for rollback on partial failure.
    registered=[]
    try:
        for handler in handlers:
            client.add_handler(handler,group=0)
            registered.append(handler)
    except Exception:
        for handler in registered:client.remove_handler(handler,group=0)
        raise
    _installed[client]=(message,callback)
    return _installed[client]
