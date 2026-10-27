"""Discover legacy decorators plus the explicit replacement command manifest.

This is documentation/navigation, not an authorization or dispatch layer.
Handlers and manifest policies remain authoritative for permissions and effects.
"""
import ast
import re
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CATEGORIES={
    'music':{'play','cplay','autoplay','smartqueue','playlist','effects','seek','music_controls','pause','resume','skip','stop','lyrics','downloader'},
    'manage':{'federation','blocklist','approve','group_manager','moderation','locks','notes','welcome'},
    'owner':{'owner_utils','broadcast'},
}
LABELS={'music':'Music & playlists','manage':'Groups & protection','tools':'Telegram tools','owner':'Owner operations','all':'All commands'}
OWNER_NAMES={'apiinfo','emojiinfo','watchdog','dbcleanup','sysinfo','active','addsudo','delsudo','rmsudo','sudolist','gblock','gunblock','ublock','uunblock','blocklist'}


def source_paths():
    from videl.modules import ALL_MODULES
    return [ROOT/'videl'/'modules'/f'{name}.py' for name in ALL_MODULES]


@lru_cache(maxsize=1)
def commands():
    entries=[]
    for path in source_paths():
        source=path.read_text();tree=ast.parse(source)
        for node in tree.body:
            if not isinstance(node,(ast.AsyncFunctionDef,ast.FunctionDef)):continue
            for decorator in node.decorator_list:
                for call in ast.walk(decorator):
                    if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or not call.args:continue
                    if call.func.attr=='command':
                        value=ast.literal_eval(call.args[0])
                        names=[value] if isinstance(value,str) else list(value)
                    elif call.func.attr=='regex':
                        expression=call.args[0]
                        if isinstance(expression,ast.JoinedStr):
                            # Runtime-configured prefixes are f-strings; retain
                            # their literal regex fragments for command discovery.
                            pattern=''.join(part.value for part in expression.values
                                if isinstance(part,ast.Constant) and isinstance(part.value,str))
                        else:
                            pattern=ast.literal_eval(expression)
                        if not isinstance(pattern,str):continue
                        dynamic_prefix=(isinstance(expression,ast.JoinedStr) and any(
                            isinstance(part,ast.FormattedValue) and 'COMMAND_PREFIX_PATTERN' in ast.unparse(part.value)
                            for part in expression.values))
                        if not (pattern.startswith('^/') or dynamic_prefix):continue
                        if '(?P<cmd>v?play|playnext)' in pattern:names=['play','vplay','playnext']
                        elif '(?P<cmd>v?play)' in pattern:names=['play','vplay']
                        elif '(?P<cmd>c(?:v)?play)' in pattern:names=['cplay','cvplay']
                        else:
                            match=re.match(r'^\^/?([a-z_]+)',pattern)
                            if not match:raise ValueError(f'Uncatalogued command regex: {pattern}')
                            names=[match[1]]
                    else:continue
                    guard=ast.get_source_segment(source,decorator) or ''
                    for name in names:
                        if not isinstance(name,str) or not name or not all(char.islower() or char.isdigit() or char=='_' for char in name):
                            raise ValueError(f'Invalid command in {path.name}: {name!r}')
                        owner=name in OWNER_NAMES or 'filters.user(config.OWNER_ID)' in guard or 'filters.user(6265999542)' in guard or path.stem in CATEGORIES['owner']
                        category='owner' if owner else next((key for key,modules in CATEGORIES.items() if path.stem in modules),'tools')
                        context='group' if 'filters.group' in guard else 'private' if 'filters.private' in guard or path.stem=='owner_utils' else 'chat'
                        summaries = {
                            'playnext': 'Queue a track to play immediately after the current track',
                            'addsudo': 'Grant limited bot-blocklist operator access to a trusted user',
                            'delsudo': 'Revoke a bot sudo operator',
                            'rmsudo': 'Revoke a bot sudo operator',
                            'sudolist': 'List bot sudo operators and remove access inline',
                            'sudohelp': 'Show the limited bot sudo command scope',
                        }
                        summary = summaries.get(name) or (ast.get_docstring(node) or node.name.replace('_cmd','').replace('_command','').replace('_',' ').capitalize()).splitlines()[0][:120]
                        entries.append({'name':name,'category':category,'context':context,'owner':owner,
                            'source':str(path.relative_to(ROOT)),'handler':node.name,'summary':summary})
    from videl.app.routes import COMMANDS
    for command in COMMANDS:
        module = command.handler.__module__
        if module.startswith('videl.plugins.'):
            source = 'videl/plugins/' + module.rsplit('.', 1)[-1] + '.py'
        elif module.startswith('videl.app.'):
            source = 'videl/app/' + module.rsplit('.', 1)[-1] + '.py'
        else:
            source = module.replace('.', '/') + '.py'
        entries.append({'name':command.name,'category':command.category,
            'context':'private' if command.policy=='owner' else 'group' if command.policy in {'group','admin'} else 'chat',
            'owner':command.policy=='owner','source':source,
            'handler':command.handler.__name__,'summary':command.summary})
    unique={}
    for entry in entries:
        previous=unique.get(entry['name'])
        if previous:
            # /seek has separate valid-argument and usage handlers in one module.
            if not (entry['name']=='seek' and previous['source']==entry['source'] and {previous['handler'],entry['handler']}=={'seek_cmd','seek_usage'}):
                raise ValueError(f"Duplicate command across modules: {entry['name']}")
            continue
        unique[entry['name']]=entry
    return tuple(sorted(unique.values(),key=lambda entry:entry['name']))



def visible_commands(owner=False,category='all',query=''):
    query=query.lstrip('/').casefold()[:64]
    return [entry for entry in commands() if (owner or not entry['owner'])
            and (category=='all' or entry['category']==category)
            and (not query or query in entry['name'] or query in entry['summary'].casefold())]


def _command_icon(entry):
    """Pick a relevant, non-interactive Premium badge for every directory row."""
    name = entry['name']
    # High-signal actions first: /banlist and federation ban tools should not
    # inherit the generic group badge, while unban/unmute remain success actions.
    if name.startswith('un') and any(part in name for part in ('ban', 'mute', 'approve', 'warn', 'pin', 'lock')):
        return 'unlock' if name in {'unban', 'unmute', 'unlock', 'unpin'} else 'check'
    if 'ban' in name or 'kick' in name:
        return 'rijif_forbid'
    if 'mute' in name:
        return 'boseh_speaker_mute'
    if 'warn' in name:
        return 'rijif_warning'
    if name in {'hug', 'kiss'}:
        return 'vector_102' if name == 'kiss' else 'vector_101'
    if name == 'like':
        return 'rijif_heart_fire'
    if name == 'wave':
        return 'rijif_speech'
    if name == 'highfive':
        return 'rijif_thumbs_up'
    if name == 'dance':
        return 'rijif_disco'
    if name in {'tagall', 'gcast', 'broadcast'}:
        return 'rijif_megaphone'
    if name in {'afk', 'afklist', 'back', 'remind', 'reminders'}:
        return 'boseh_clock'
    if name == 'apiinfo':
        return 'ios_info'
    if name == 'emojiinfo':
        return 'ios_symbols'
    if name == 'topicnew':
        return 'ios_add'
    if name == 'topicrename':
        return 'ios_edit'
    if name == 'topicclose':
        return 'ios_close'
    if name == 'topicopen':
        return 'ios_check'
    if name == 'pollstop':
        return 'ios_close'
    if name == 'copy':
        return 'ios_paperclip'
    if name in {'stats', 'sysinfo', 'watchdog', 'active'}:
        return 'stats'
    if name in {'about', 'repo', 'help', 'commands', 'id', 'whois'}:
        return 'ios_info'
    if name in {'cleanup', 'purge', 'dbcleanup', 'forget', 'delnote', 'delblacklist', 'delblsticker', 'delphoto', 'deleteplaylist'}:
        return 'ios_trash'
    if name == 'settitle':
        return 'ios_tag'
    if name == 'setdescription':
        return 'ios_newspaper'
    if name in {'approve', 'approved', 'approval', 'saveplaylist', 'save'}:
        return 'check'
    if name in {'welcome', 'greetings', 'goodbye', 'setwelcome', 'setgoodbye'}:
        return 'spark'
    if name in {'download', 'song', 'vsong'}:
        return 'ios_file'
    if entry['category'] == 'music' or any(part in name for part in ('play', 'queue', 'lyric', 'seek', 'speed', 'bass', 'effect')):
        return 'music'
    if any(part in name for part in ('sticker', 'photo', 'avatar', 'image', 'kang')):
        return 'ios_image'
    if any(part in name for part in ('note', 'filter', 'get', 'copy', 'font', 'rule')):
        return 'ios_memo'
    if any(part in name for part in ('poll', 'quiz', 'react', 'topic')):
        return 'ios_symbols'
    if any(part in name for part in ('fed', 'invite', 'link')):
        return 'globe'
    if entry['category'] == 'owner' or entry['owner']:
        return 'crown'
    if entry['category'] == 'manage' or any(part in name for part in ('admin', 'lock', 'approve', 'report', 'group', 'block')):
        return 'shield'
    return 'ios_controls'


def _command_scope(entry, pe):
    if entry['owner']:
        return pe('crown') + ' Owner · private chat'
    if entry['context'] == 'group':
        return pe('shield') + ' Group'
    if entry['context'] == 'private':
        return pe('boseh_person') + ' Private chat'
    return pe('globe') + ' Any chat'


def directory(category='all',page=0,*,owner=False,query=''):
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.utils.premium_emojis import pe
    from videl.utils.rich_ui import rich_heading,rich_note,rich_esc,rich_kv_table
    if category not in LABELS or category=='owner' and not owner:category='all'
    entries=visible_commands(owner,category,query)
    size=10;pages=max(1,(len(entries)+size-1)//size);page=max(0,min(int(page),pages-1))
    title_icon = {'music': 'music', 'manage': 'shield', 'tools': 'ios_controls', 'owner': 'crown', 'all': 'ios_symbols'}[category]
    text=rich_heading(pe(title_icon) + ' ' + LABELS[category] + ' · Command directory',level=2)+rich_note(f'{len(entries)} commands · Page {page+1}/{pages}')
    if query:text+=rich_note(pe('ios_search') + f' Search: <code>{rich_esc(query)}</code>')
    if entries:
        text+=rich_kv_table([
            (f"{pe(_command_icon(entry))} <code>/{entry['name']}</code>", f"{rich_esc(entry['summary'])} · {_command_scope(entry, pe)}")
            for entry in entries[page*size:(page+1)*size]
        ])
    if not entries:text+=rich_note('No matching command. Try /commands music or /commands ban.')
    text+=rich_note('Search with /commands keyword. Permissions are checked when you run an action; this directory never grants access.')
    rows=[]
    # Search results are deliberately not paged through callbacks: arbitrary
    # query text must not be embedded in Telegram's 64-byte callback field.
    if not query:
        nav=[]
        if page:nav.append(button('Previous',callback_data=f'cmds:{category}:{page-1}'))
        if page+1<pages:nav.append(button('Next',callback_data=f'cmds:{category}:{page+1}'))
        if nav:rows.append(nav)
    else:
        # Render every matching result in a bounded command-name list below.
        if len(entries)>size:text+=rich_note('Other matches: '+ ' · '.join('/'+entry['name'] for entry in entries[size:size+20]))
        if len(entries)>size+20:text+=rich_note('Refine the search or browse a category for additional matches.')
    rows.extend([[button('Music',callback_data='cmds:music:0'),button('Groups',callback_data='cmds:manage:0')],
                 [button('Telegram tools',callback_data='cmds:tools:0'),button('Help center',callback_data='help:home')]])
    if owner:rows.append([button('Owner operations',callback_data='cmds:owner:0',style='primary')])
    return text,InlineKeyboardMarkup(rows)
