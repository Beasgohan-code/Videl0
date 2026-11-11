import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videl.utils import youtube


class _Content:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, _size):
        for chunk in self.chunks:
            yield chunk


class _CancelableContent:
    def __init__(self, started):
        self.started = started

    async def iter_chunked(self, _size):
        yield b"x" * 1024
        self.started.set()
        await asyncio.Event().wait()


class _Response:
    status = 200
    headers = {"Content-Type": "audio/mpeg"}

    def __init__(self, chunks, content_length=None):
        self.content = _Content(chunks)
        self.content_length = content_length

    async def text(self):
        return ""


class EldianResponseSizeTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_declared_oversize_without_creating_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            partial = str(Path(directory) / "track.part")
            target = str(Path(directory) / "track")
            with patch.object(youtube, "MAX_DOWNLOAD_BYTES", 5):
                result = await youtube._save_eldian_response(
                    _Response([b"small"], content_length=6), partial, target, video=False
                )
            self.assertIsNone(result)
            self.assertFalse(Path(partial).exists())
            self.assertFalse(list(Path(directory).glob("track.*")))

    async def test_rejects_stream_that_crosses_cap_and_cleans_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            partial = str(Path(directory) / "track.part")
            target = str(Path(directory) / "track")
            with patch.object(youtube, "MAX_DOWNLOAD_BYTES", 5):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    await youtube._save_eldian_response(
                        _Response([b"1234", b"56"]), partial, target, video=False
                    )
            self.assertFalse(Path(partial).exists())
            self.assertFalse(list(Path(directory).glob("track.*")))

    async def test_cancellation_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            partial = str(Path(directory) / "track.part")
            target = str(Path(directory) / "track")
            started = asyncio.Event()
            response = _Response([])
            response.content = _CancelableContent(started)
            task = asyncio.create_task(youtube._save_eldian_response(response, partial, target, video=False))
            await asyncio.wait_for(started.wait(), timeout=2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(Path(partial).exists())
            self.assertFalse(list(Path(directory).glob("track.*")))

    async def test_accepts_bounded_stream_and_atomically_publishes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            partial = str(Path(directory) / "track.part")
            target = str(Path(directory) / "track")
            body = b"x" * 2048
            with patch.object(youtube, "MAX_DOWNLOAD_BYTES", len(body)):
                result = await youtube._save_eldian_response(
                    _Response([body[:1024], body[1024:]], content_length=len(body)), partial, target, video=False
                )
            self.assertEqual(Path(result).name, "track.mp3")
            self.assertEqual(Path(result).read_bytes(), body)
            self.assertFalse(Path(partial).exists())


if __name__ == "__main__":
    unittest.main()
