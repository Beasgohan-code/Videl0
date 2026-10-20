"""Command manifest assembled from the plugin packages.

Each plugin exports its own ``COMMANDS`` tuple; this file only orders them and
adds the voice-chat music controls that live outside the plugin layer.
"""
from .router import Command,Router
from . import music,group_view
from videl.plugins import start,help as help_plugin,tools,moderation,locks,notes,welcome,group,afk,reminder

COMMANDS=(
    *start.COMMANDS,
    *help_plugin.COMMANDS,
    *tools.COMMANDS,
    *group.COMMANDS,
    *moderation.COMMANDS,
    *locks.COMMANDS,
    *notes.COMMANDS,
    *welcome.COMMANDS,
    *afk.COMMANDS,
    *reminder.COMMANDS,
)
COMMANDS += tuple(Command(name,music.control,'Control live playback: '+name,category='music',policy='admin',block_policy='chat')
                  for name in ('pause','resume','loop','shuffle','clear','skip','stop','end','resetplayer','replay'))
COMMANDS += tuple(Command(name,music.view_queue,'Show the current track and upcoming queue',category='music',policy='group',block_policy='chat')
                  for name in ('queue','q'))
COMMANDS += (Command('groupview',group_view.recording,'Check or stop bot-visible group recording',category='manage',policy='admin'),)
COMMANDS += (Command('inbox',group_view.private_recording,'Check or stop recording of your own bot DM',),)
router=Router(COMMANDS)
