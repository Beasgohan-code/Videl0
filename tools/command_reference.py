"""Regenerate the command reference from registered source: python -m tools.command_reference."""
from pathlib import Path
from videl.utils.command_catalog import commands,LABELS

def reference():
    entries=commands()
    lines=['# Registered command reference','',
           "Generated from the bot's registered command manifest and installed handlers.",
           'This documents navigation and source coverage, not verified live Telegram behavior.',
           'Aliases are listed separately; permissions remain enforced by the referenced handler.',
           'Owner operations are hidden from public `/commands` results.','',
           f'{len(entries)} distinct command names.','']
    for category in ('music','manage','tools','owner'):
        lines += ['## '+LABELS[category],'','| Command | Context | Handler |','|---|---|---|']
        for entry in entries:
            if entry['category']==category:
                lines.append(f"| `/{entry['name']}` | {entry['context']} | `{entry['source']}::{entry['handler']}` |")
        lines.append('')
    from videl.app.connections import CONNECTED_COMMANDS
    remote = [entry['name'] for entry in entries if entry['name'] in CONNECTED_COMMANDS]
    lines += ['## Private-chat connected group commands', '',
              'Run `/connect` in a group as a current Telegram administrator. From private chat, only these registered commands are routed to that saved group:',
              '', ', '.join(f'`/{name}`' for name in remote), '',
              'Every routed request uses the server-stored group ID, preserves the actual Telegram user, rechecks current group-admin status, and removes private reply targets. Use a username or numeric Telegram ID instead of replying to a private message.', '']
    lines += ['## UI and transport exceptions','',
              'Authored command feedback uses the vendored Badmunda05 Richgram helpers and native Kurigram keyboards.',
              'Telegram polls, media/file delivery, forwards/copies, user-authored saved notes, filters and welcome templates',
              'retain their native Telegram transport. They are not wrapped into decorative rich cards or rewritten.',
              'Callback answers remain native short notifications. This is intentional, not an unimplemented rich UI path.',
              'No automatic resend is allowed when a send times out or its outcome is unknown.','']
    return '\n'.join(lines)

if __name__=='__main__':
    path=Path('docs/COMMAND_REFERENCE.md');path.write_text(reference());print(path)
