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
OWNER_NAMES={'apiinfo','emojiinfo','watchdog','dbcleanup','sysinfo','active'}


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
                        pattern=ast.literal_eval(call.args[0])
                        if not isinstance(pattern,str) or not pattern.startswith('^/'):continue
                        if '(?P<cmd>v?play)' in pattern:names=['play','vplay']
                        elif '(?P<cmd>c(?:v)?play)' in pattern:names=['cplay','cvplay']
                        else:
                            match=re.match(r'^\^/([a-z_]+)',pattern)
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
                        entries.append({'name':name,'category':category,'context':context,'owner':owner,
                            'source':str(path.relative_to(ROOT)),'handler':node.name,
                            'summary':(ast.get_docstring(node) or node.name.replace('_cmd','').replace('_command','').replace('_',' ').capitalize()).splitlines()[0][:120]})
    from videl.app.routes import COMMANDS
    for command in COMMANDS:
        entries.append({'name':command.name,'category':command.category,
            'context':'private' if command.policy=='owner' else 'group' if command.policy in {'group','admin'} else 'chat',
            'owner':command.policy=='owner','source':'videl/app/'+command.handler.__module__.rsplit('.',1)[-1]+'.py',
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


def directory(category='all',page=0,*,owner=False,query=''):
    from pyrogram.types import InlineKeyboardMarkup
    from videl.utils.bot_ui import button
    from videl.utils.rich_ui import rich_heading,rich_note,rich_esc,rich_kv_table
    if category not in LABELS or category=='owner' and not owner:category='all'
    entries=visible_commands(owner,category,query)
    size=10;pages=max(1,(len(entries)+size-1)//size);page=max(0,min(int(page),pages-1))
    text=rich_heading('Command directory',level=2)+rich_note(f'{LABELS[category]} · {len(entries)} commands · Page {page+1}/{pages}')
    if query:text+=rich_note(f'Search: <code>{rich_esc(query)}</code>')
    if entries:
        text+=rich_kv_table([
            (f"<code>/{entry['name']}</code>", f"{rich_esc(entry['summary'])} · {entry['context']}")
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
