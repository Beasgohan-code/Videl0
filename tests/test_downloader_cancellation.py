"""Cancellation cleanup tests for the public media downloader path."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videl.utils import youtube


class _CancelableContent:
    def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
        self.started = started
        self.release = release

    async def iter_chunked(self, _chunk_size):
        yield b"x" * 2048
        self.started.set()
        await self.release.wait()
        yield b"y" * 2048


class _Response:
    status = 200
    headers = {"Content-Type": "audio/mpeg"}
    content_length = 4096

    def __init__(self, content):
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get(self, *_args, **_kwargs):
        return self.response


class DownloaderCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_public_song_download_removes_external_provider_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            started = asyncio.Event()
            release = asyncio.Event()
            response = _Response(_CancelableContent(started, release))
            session = _Session(response)
            with (
                patch.object(youtube, "DOWNLOAD_DIR", directory),
                patch.object(youtube, "_find_file", return_value=None),
                patch.object(youtube, "YT_API_URL", "https://media.example"),
                patch.object(youtube, "YT_API_KEY", "test-primary-key"),
                patch.object(youtube, "YT_API_KEY_FALLBACK", ""),
                patch.object(youtube.aiohttp, "ClientSession", return_value=session),
            ):
                task = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                await asyncio.wait_for(started.wait(), timeout=2)
                partial = Path(directory) / "dQw4w9WgXcQ.external.mp3.part"
                self.assertTrue(partial.exists(), "the cancellation boundary follows a written partial chunk")
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertFalse(partial.exists())
                self.assertFalse((Path(directory) / "dQw4w9WgXcQ.external.mp3").exists())
