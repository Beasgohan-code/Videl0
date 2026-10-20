"""Regenerate the command reference from registered source: python -m tools.command_reference."""
from pathlib import Path
from videl.utils.command_catalog import commands,LABELS

def reference():
    entries=commands()
    lines=['# Registered command reference','',
           'Generated from registered command and regex handlers plus the two enabled plugins.',
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
    lines += ['## UI and transport exceptions','',
              'Authored command feedback uses the vendored Badmunda05 Richgram helpers and native Kurigram keyboards.',
              'Telegram polls, media/file delivery, forwards/copies, user-authored saved notes, filters and welcome templates',
              'retain their native Telegram transport. They are not wrapped into decorative rich cards or rewritten.',
              'Callback answers remain native short notifications. This is intentional, not an unimplemented rich UI path.',
              'No automatic resend is allowed when a send times out or its outcome is unknown.','']
    return '\n'.join(lines)

if __name__=='__main__':
    path=Path('docs/COMMAND_REFERENCE.md');path.write_text(reference());print(path)
