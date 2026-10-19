from aiogram import Router

def setup_all() -> Router:
    from bot.handlers import start, admin, owner, music, ai, utility, group, callbacks, fun

    router = Router()
    # order matters: callbacks last? Actually include all
    for mod in (start, admin, owner, music, ai, utility, group, callbacks, fun):
        if hasattr(mod, "router"):
            router.include_router(mod.router)

    return router
