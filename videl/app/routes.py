"""Command manifest assembled from the plugin packages.

Each plugin exports its own ``COMMANDS`` tuple; this file only orders them and
adds the voice-chat music controls that live outside the plugin layer.
"""
from .router import Command,Router
from . import music,group_view
from videl.plugins import start,help as help_plugin,tools,moderation,locks,notes,welcome,group,afk,reminder,stickers,connections,reports,appeals,sudo,privacy,preferences,retention,faq,settings

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
    *stickers.COMMANDS,
    *connections.COMMANDS,
    *reports.COMMANDS,
    *appeals.COMMANDS,
    *sudo.COMMANDS,
    *privacy.COMMANDS,
    *preferences.COMMANDS,
    *retention.COMMANDS,
    *faq.COMMANDS,
    *settings.COMMANDS,
)
COMMANDS += tuple(Command(name,music.control,'Control live playback: '+name,category='music',policy='admin',block_policy='chat')
                  for name in ('pause','resume','loop','shuffle','clear','skip','stop','end','resetplayer','replay'))
COMMANDS += tuple(Command(name,music.view_queue,'Show the current track and upcoming queue',category='music',policy='group',block_policy='chat')
                  for name in ('queue','q'))
COMMANDS += tuple(Command(name,music.manage_queue,summary,category='music',policy='admin',block_policy='chat')
                  for name,summary in (('remove','Remove an upcoming queue track'),('move','Reorder upcoming queue tracks'),('jump','Play a selected upcoming track')))
COMMANDS += (Command('clearqueue',music.control,'Clear upcoming tracks while preserving current playback',category='music',policy='admin',block_policy='chat'),)
COMMANDS += (Command('groupview',group_view.recording,'Check or stop bot-visible group recording',category='manage',policy='admin'),)
COMMANDS += (Command('inbox',group_view.private_recording,'Check or stop recording of your own bot DM',),)
router=Router(COMMANDS)
