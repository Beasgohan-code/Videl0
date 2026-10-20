"""Read-only navigation. Callback text never grants owner permissions."""
from videl.utils.command_ui import rich_edit
from videl.utils.help_catalog import guide
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
    else:
        section=data.split(':')[-1] if data.startswith(('v2:section:','guide:')) else {'pro_music_help':'music','pro_group_help':'manage'}.get(data,'home')
        if section not in {'home','music','manage','protect','tools'}:section='home'
        text,keyboard=guide(section)
    await query.answer()
    await rich_edit(query,text,reply_markup=keyboard,client=client)
