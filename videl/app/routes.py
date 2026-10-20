"""Explicit replacement command manifest. No decorators or import-time registration."""
from .router import Command,Router
from . import general,moderation,music,group_view

COMMANDS=(
    Command('start',general.start,'Open the public Studio or private owner workspace'),
    Command('help',general.help_command,'Choose music, moderation, protection or Telegram tools'),
    Command('commands',general.directory_command,'Search the installed command directory'),
    Command('ping',general.ping,'Check an acknowledged Telegram round trip'),
    Command('id',general.identifiers,'Inspect chat, message, reply or user identifiers',block_policy='user'),
    Command('repo',general.source,'Read source code and third-party licenses',block_policy='user'),
)
COMMANDS += tuple(Command(name,moderation.moderate,'Validated member '+name+' action',category='manage',policy='admin',
                           rights=('can_restrict_members','can_delete_messages') if name in {'dban','dkick'} else ('can_restrict_members',))
                  for name in ('ban','tban','dban','unban','kick','dkick','mute','tmute','unmute'))
COMMANDS += tuple(Command(name,music.control,'Control live playback: '+name,category='music',policy='admin',block_policy='chat')
                  for name in ('pause','resume','loop','shuffle','clear','skip','stop','end','resetplayer','replay'))
COMMANDS += tuple(Command(name,music.view_queue,'Show the current track and upcoming queue',category='music',policy='group',block_policy='chat')
                  for name in ('queue','q'))
COMMANDS += (Command('groupview',group_view.recording,'Check or stop bot-visible group recording',category='manage',policy='admin'),)
COMMANDS += (Command('inbox',group_view.private_recording,'Check or stop recording of your own bot DM'),)
router=Router(COMMANDS)
