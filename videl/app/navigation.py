"""Read-only navigation. Callback text never grants owner permissions."""
from videl.utils.command_ui import rich_edit
from .router import private_owner


async def navigate(client,query):
    if not query.message:
        return await query.answer('Open /help in a chat.',show_alert=True)
    data=query.data or ''
    owner=private_owner(query.message,query.from_user)
    if data=='v2:setup':
        from .readiness import inspect_setup
        await query.answer()
        screen=await inspect_setup(client,query.message)
        return await rich_edit(query,screen.html,reply_markup=screen.keyboard,client=client)
    if data.startswith('cmds:'):
        _,category,page=data.split(':')
        if category=='owner' and not owner:
            return await query.answer('Owner commands are private.',show_alert=True)
        from videl.utils.command_catalog import directory
        text,keyboard=directory(category,int(page),owner=owner)
    elif data.startswith('help:'):
        from videl.plugins.help import render_section
        section='home'
        page=0
        parts=data.split(':')
        if len(parts)>1 and parts[1]:
            section=parts[1]
        if len(parts)>2 and parts[2].isdigit():
            page=int(parts[2])
        if section=='owner' and not owner:
            return await query.answer('Owner pages are private.',show_alert=True)
        text,keyboard=render_section(section,page,owner=owner)
    else:
        section={'pro_music_help':'music','pro_group_help':'manage'}.get(data,'home')
        text,keyboard=__import__('videl.plugins.help',fromlist=['render_section']).render_section(section,owner=owner)
    await query.answer()
    await rich_edit(query,text,reply_markup=keyboard,client=client)
