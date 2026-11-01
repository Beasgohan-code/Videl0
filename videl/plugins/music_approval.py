# Videl © 2026 | Beasgohan-code
"""Admin controls for opt-in group track request approval."""
from __future__ import annotations
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading, table
from videl.core import queue
from videl.core import request_approval


async def requests(ctx) -> Screen:
    args = ctx.command.arguments.strip().split(maxsplit=1)
    chat_id = int(ctx.message.chat.id)
    if not args:
        items = request_approval.list_pending(chat_id)
        if not items:
            return Screen(heading("Pending track requests", 3) + body("No requests are awaiting approval."))
        rows = [(item["id"], f"{str(item['song'].get('title', 'Untitled'))[:80]} · from {str(item['song'].get('requester', 'member'))[:40]}") for item in items]
        return Screen(heading("Pending track requests", 3) + table(rows)
                      + body("Approve or reject with <code>/requests approve CODE</code> or <code>/requests reject CODE</code>. Approved tracks are added to the queue; start playback with <code>/play</code> if it is idle."))
    if len(args) != 2 or args[0] not in {"approve", "reject"}:
        raise CommandError("Use <code>/requests</code>, <code>/requests approve CODE</code>, or <code>/requests reject CODE</code>.")
    song = request_approval.take(chat_id, args[1])
    if song is None:
        raise CommandError("That request is no longer pending. Refresh with <code>/requests</code>.")
    if args[0] == "reject":
        return Screen(heading("Request rejected", 3) + body("The track was discarded and was not added to the queue."))
    # Approval always appends; it cannot displace the current track.
    queue_chat_id = int(song.pop("_queue_chat_id", chat_id))
    settings_chat_id = int(song.get("settings_chat_id", chat_id))
    if base.get_setting(settings_chat_id, "music_shuffle_enabled", False):
        import random
        tracks = queue.get_queue(queue_chat_id)
        position = random.randint(1, len(tracks)) if len(tracks) > 1 else len(tracks)
        tracks.insert(position, song)
    else:
        queue.add_to_queue(queue_chat_id, song)
    return Screen(heading("Request approved", 3) + body("The track was added to the queue. If playback is idle, start it with <code>/play</code> or the queue controls."))


COMMANDS = (
    Command("requests", requests, "Review pending group track requests", category="music", policy="admin", block_policy="chat"),
)
