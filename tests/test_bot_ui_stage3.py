"""Representative Stage 3 Telegram UI migration contracts."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.plugins import base, group, help as help_plugin, start
from videl.app import music
from videl.modules import downloader
from videl.utils import command_ui


class StartHelpAndNavigationTests(unittest.TestCase):
    def test_start_keyboards_retain_actions_and_owner_gating(self):
        public = start.private_keyboard(False, "Videl0Bot")
        public_callbacks = {
            item.callback_data
            for row in public.inline_keyboard for item in row
            if item.callback_data
        }
        self.assertTrue({"help:music", "help:home", "cmds:all:0", "v2:setup", "help:about"} <= public_callbacks)
        self.assertNotIn("cmds:owner:0", public_callbacks)
        owner = start.private_keyboard(True, "Videl0Bot")
        owner_callbacks = {
            item.callback_data
            for row in owner.inline_keyboard for item in row
            if item.callback_data
        }
        self.assertIn("cmds:owner:0", owner_callbacks)
        self.assertTrue(any(item.web_app for row in owner.inline_keyboard for item in row))

    def test_help_home_is_compact_and_keeps_accessible_and_category_paths(self):
        text, keyboard = help_plugin.render_section("home", owner=False)
        self.assertIsNone(keyboard)
        plain = base.plain(text)
        self.assertIn("Quick starts", plain)
        self.assertIn("/help plain", plain)
        self.assertNotIn("Browse a section", plain)
        _, markup = __import__("vendor.richgram.richgram.rich_ui", fromlist=["_native_buttons"])._native_buttons(text)
        callbacks = {
            item.callback_data
            for row in markup.inline_keyboard for item in row
            if item.callback_data
        }
        self.assertTrue({"help:music", "help:manage", "help:tools", "cmds:all:0", "help:about"} <= callbacks)
        self.assertNotIn("help:owner:0", callbacks)

    def test_command_directory_uses_registered_categories_and_callbacks(self):
        from videl.utils.command_catalog import directory
        text, markup = directory("music", 0, owner=False)
        self.assertIn("Music & playlists", base.plain(text))
        callbacks = {
            item.callback_data
            for row in markup.inline_keyboard for item in row
            if item.callback_data
        }
        self.assertTrue({"cmds:music:0", "cmds:manage:0", "cmds:tools:0", "help:home"} <= callbacks)


class FileAndMusicPanelsTests(unittest.IsolatedAsyncioTestCase):
    async def test_sticker_file_panel_shows_available_metadata_without_fabricating_fields(self):
        sticker = SimpleNamespace(
            file_id="reusable-id", file_unique_id="stable-id", set_name="TestSet",
            emoji="🎵", file_size=1536, width=512, height=512,
            is_animated=True, is_video=False,
        )
        message = SimpleNamespace(reply_to_message=SimpleNamespace(sticker=sticker))
        screen = await group.sticker_id(SimpleNamespace(message=message))
        plain = base.plain(screen.html)
        for value in ("Sticker file details", "File ID", "Unique ID", "TestSet", "🎵", "1.5 KB", "512 × 512 px", "Animated sticker"):
            self.assertIn(value, plain)
        self.assertIn("identification only", plain)

        sparse = SimpleNamespace(file_id="id", file_unique_id="unique", width=0, height=0)
        sparse_screen = await group.sticker_id(
            SimpleNamespace(message=SimpleNamespace(reply_to_message=SimpleNamespace(sticker=sparse)))
        )
        self.assertNotIn("Dimensions", sparse_screen.html)
        self.assertNotIn("File size", sparse_screen.html)

    async def test_music_queue_keyboard_groups_existing_callbacks(self):
        ctx = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-1001)))
        tracks = [
            {"title": "Current track", "duration": "3:20"},
            {"title": "Next track", "duration": "4:05"},
        ]
        with (
            patch.object(music.queue, "get_queue", return_value=tracks),
            patch.object(music.player, "is_paused", return_value=False),
            patch.object(music.player, "get_loop", return_value="off"),
        ):
            screen = await music.view_queue(ctx)
        self.assertIn("Current track", base.plain(screen.html))
        self.assertIn("Next track", base.plain(screen.html))
        callbacks = [
            item.callback_data
            for row in screen.keyboard.inline_keyboard for item in row
            if item.callback_data
        ]
        self.assertTrue({"pause", "skip", "cycle_loop", "shuffle", "clear", "help:home", "cmds:all:0"} <= set(callbacks))
        self.assertLessEqual(max(map(len, screen.keyboard.inline_keyboard)), 2)

    async def test_empty_queue_keeps_play_help_navigation(self):
        ctx = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-1001)))
        with patch.object(music.queue, "get_queue", return_value=[]):
            screen = await music.view_queue(ctx)
        callbacks = [
            item.callback_data
            for row in screen.keyboard.inline_keyboard for item in row
            if item.callback_data
        ]
        self.assertEqual(callbacks, ["help:music", "cmds:all:0"])


class TransferProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_ytdlp_byte_progress_is_reported_without_network_access(self):
        status = object()
        edit = AsyncMock()
        with patch.object(downloader, "rich_edit", edit):
            hook = downloader._yt_dlp_progress_hook(status, "Downloading audio")
            future = hook({"status": "downloading", "downloaded_bytes": 5 * 1024 * 1024,
                           "total_bytes_estimate": 10 * 1024 * 1024})
            self.assertIsNotNone(future)
            await asyncio.wrap_future(future)
            await hook.drain(complete=True)
        self.assertEqual(edit.await_count, 2)
        html = edit.await_args_list[0].args[1]
        self.assertIn("50% ·", html)
        self.assertIn("5.0 MB of 10.0 MB", html)
        self.assertIn("Downloading audio", html)
        self.assertIn("100% ·", edit.await_args_list[1].args[1])
        self.assertIsNone(hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 0}))

    async def test_video_upload_progress_and_resolution_metadata_use_real_transfer_values(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"x" * 2048)
            status = SimpleNamespace(delete=AsyncMock())
            message = SimpleNamespace(
                command=["vsong", "nature"], chat=SimpleNamespace(id=-1001), id=9,
                from_user=SimpleNamespace(id=44), reply_to_message=None,
            )
            with (
                patch.object(downloader, "rich_send", new=AsyncMock(return_value=status)),
                patch.object(downloader, "rich_edit", new=AsyncMock()) as edit,
                patch.object(downloader, "_download_media", new=AsyncMock(return_value=(
                    path, {"title": "Nature", "duration": 12, "width": 1920, "height": 1080}
                ))),
                patch.object(downloader.bot, "send_video", new=AsyncMock()) as send_video,
            ):
                async def send_via_visual_call(function, **kwargs):
                    return await function(**kwargs)

                with patch.object(downloader, "visual_call", new=AsyncMock(side_effect=send_via_visual_call)):
                    await downloader.vsong_cmd(None, message)
                    progress = send_video.await_args.kwargs["progress"]
                    await progress(1_000_000, 2_000_000)
            options = send_video.await_args.kwargs
            self.assertEqual((options["width"], options["height"]), (1920, 1080))
            self.assertIn("Resolution", options["caption"])
            self.assertIn("50% ·", edit.await_args.args[1])
            self.assertIn("Uploading video", edit.await_args.args[1])

    async def test_telegram_upload_progress_uses_shared_builder_and_survives_edit_failure(self):
        updates = []

        async def update(html):
            updates.append(html)

        reporter = command_ui.transfer_progress_callback(update, "Uploading video", interval=0)
        await reporter(1_500_000, 3_000_000)
        self.assertEqual(len(updates), 1)
        self.assertIn("50% ·", updates[0])
        self.assertIn("Uploading video", updates[0])

        async def unavailable(_html):
            raise RuntimeError("status edit unavailable")

        await command_ui.transfer_progress_callback(unavailable, "Uploading audio", interval=0)(10, 20)


if __name__ == "__main__":
    unittest.main()
