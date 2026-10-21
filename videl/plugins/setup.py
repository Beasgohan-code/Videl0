"""Read-only group setup checks exposed as the ordinary /setup command."""
from __future__ import annotations

from videl.app.router import Command, Screen


async def setup(ctx) -> Screen:
    """Check Telegram bot rights without changing group settings."""
    from videl.app.readiness import inspect_setup

    return await inspect_setup(ctx.client, ctx.message)


COMMANDS = (
    Command(
        "setup",
        setup,
        "Check the bot's group permissions and setup readiness",
        category="manage",
        policy="group",
    ),
)
