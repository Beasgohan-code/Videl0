"""Cross-event-loop single-flight tests for the public downloader API."""

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from videl.utils import youtube


class DownloaderConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_audio_id_shares_one_provider_operation_across_event_loops(self):
        with tempfile.TemporaryDirectory() as directory:
            started = threading.Event()
            release = threading.Event()
            counter_lock = threading.Lock()
            calls = 0
            output = Path(directory) / "dQw4w9WgXcQ.external.mp3"

            async def slow_provider(video_id, *, video=False):
                nonlocal calls
                with counter_lock:
                    calls += 1
                started.set()
                await asyncio.to_thread(release.wait)
                output.write_bytes(video_id.encode() * 256)
                return str(output)

            def invoke_from_own_loop():
                return asyncio.run(youtube.download_song("https://youtu.be/dQw4w9WgXcQ"))

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_via_external_api", side_effect=slow_provider
            ):
                first = asyncio.create_task(asyncio.to_thread(invoke_from_own_loop))
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                second = asyncio.create_task(asyncio.to_thread(invoke_from_own_loop))
                await asyncio.sleep(0.05)
                release.set()
                first_result, second_result = await asyncio.gather(first, second)

            self.assertEqual(calls, 1)
            self.assertEqual(first_result, str(output))
            self.assertEqual(second_result, str(output))
            self.assertEqual(output.read_bytes(), b"dQw4w9WgXcQ" * 256)
            self.assertFalse(youtube._download_flights)

    async def test_same_video_id_shares_one_video_download(self):
        with tempfile.TemporaryDirectory() as directory:
            started = asyncio.Event()
            release = asyncio.Event()
            calls = 0
            output = Path(directory) / "dQw4w9WgXcQ.mp4"

            async def slow_video(_link, video_id):
                nonlocal calls
                calls += 1
                started.set()
                await release.wait()
                output.write_bytes(b"video" * 512)
                return str(output)

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_video_impl", side_effect=slow_video
            ):
                first = asyncio.create_task(youtube.download_video("dQw4w9WgXcQ"))
                await asyncio.wait_for(started.wait(), timeout=2)
                second = asyncio.create_task(youtube.download_video("https://youtu.be/dQw4w9WgXcQ"))
                await asyncio.sleep(0.02)
                release.set()
                first_result, second_result = await asyncio.gather(first, second)

            self.assertEqual(calls, 1)
            self.assertEqual(first_result, str(output))
            self.assertEqual(second_result, str(output))
            self.assertFalse(youtube._download_flights)

    async def test_audio_and_video_downloads_for_one_id_remain_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            started = {"audio": asyncio.Event(), "video": asyncio.Event()}
            release = asyncio.Event()

            async def slow_audio(_link, video_id):
                started["audio"].set()
                await release.wait()
                return str(Path(directory) / f"{video_id}.mp3")

            async def slow_video(_link, video_id):
                started["video"].set()
                await release.wait()
                return str(Path(directory) / f"{video_id}.mp4")

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_song_impl", side_effect=slow_audio
            ), patch.object(youtube, "_download_video_impl", side_effect=slow_video):
                audio = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                video = asyncio.create_task(youtube.download_video("dQw4w9WgXcQ"))
                await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started.values())), timeout=2)
                release.set()
                results = await asyncio.gather(audio, video)

            self.assertTrue(results[0].endswith(".mp3"))
            self.assertTrue(results[1].endswith(".mp4"))

    async def test_cancelled_local_worker_remains_single_flight_until_thread_finishes(self):
        from vendor.eldian_music_api.app import youtube as local_youtube

        with tempfile.TemporaryDirectory() as directory:
            started = threading.Event()
            release = threading.Event()
            calls = 0
            output = Path(directory) / "eldian" / "dQw4w9WgXcQ.mp3"

            def slow_local_download(video_id, output_dir):
                nonlocal calls
                calls += 1
                started.set()
                release.wait()
                output_dir.mkdir(parents=True, exist_ok=True)
                output.write_bytes(video_id.encode() * 256)
                return output

            with (
                patch.object(youtube, "DOWNLOAD_DIR", directory),
                patch.object(youtube, "_find_file", return_value=None),
                patch.object(youtube, "_download_via_external_api", new=AsyncMock(return_value=None)),
                patch.object(youtube, "_download_via_eldian", new=AsyncMock(return_value=None)),
                patch.object(local_youtube, "download_audio", side_effect=slow_local_download),
            ):
                first = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                first.cancel()
                try:
                    await asyncio.sleep(0.02)
                    self.assertFalse(first.done(), "cancellation must wait for the non-cancellable worker thread")

                    second = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                    await asyncio.sleep(0.02)
                    self.assertEqual(calls, 1, "a same-ID retry must wait while the old worker still writes")
                finally:
                    release.set()

                with self.assertRaises(asyncio.CancelledError):
                    await first
                result = await asyncio.wait_for(second, timeout=2)

            self.assertEqual(calls, 2)
            self.assertEqual(result, str(output))
            self.assertFalse(youtube._download_flights)

    async def test_waiter_loop_can_close_before_shared_provider_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            started = threading.Event()
            waiter_attached = threading.Event()
            release = threading.Event()
            output = Path(directory) / "dQw4w9WgXcQ.external.mp3"

            async def slow_provider(_link, video_id):
                started.set()
                await asyncio.to_thread(release.wait)
                output.write_bytes(video_id.encode() * 256)
                return str(output)

            original_wait = youtube._await_download_flight

            async def tracked_wait(flight):
                waiter_attached.set()
                return await original_wait(flight)

            def cancel_waiter_in_own_loop():
                async def run():
                    waiter = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                    self.assertTrue(await asyncio.to_thread(waiter_attached.wait, 2))
                    waiter.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await waiter

                asyncio.run(run())

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_song_impl", side_effect=slow_provider
            ), patch.object(youtube, "_await_download_flight", side_effect=tracked_wait):
                leader = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                await asyncio.to_thread(cancel_waiter_in_own_loop)
                release.set()
                result = await asyncio.wait_for(leader, timeout=2)

            self.assertEqual(result, str(output))
            self.assertFalse(youtube._download_flights)

    async def test_cancelled_waiter_does_not_cancel_shared_provider_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            started = asyncio.Event()
            release = asyncio.Event()
            calls = 0
            output = Path(directory) / "dQw4w9WgXcQ.external.mp3"

            async def slow_provider(_link, video_id):
                nonlocal calls
                calls += 1
                started.set()
                await release.wait()
                output.write_bytes(video_id.encode() * 256)
                return str(output)

            with patch.object(youtube, "_download_song_impl", side_effect=slow_provider):
                leader = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                await asyncio.wait_for(started.wait(), timeout=2)
                waiter = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                await asyncio.sleep(0.02)
                waiter.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await waiter
                release.set()
                result = await asyncio.wait_for(leader, timeout=2)

            self.assertEqual(calls, 1)
            self.assertEqual(result, str(output))
            self.assertFalse(youtube._download_flights)

    async def test_concurrent_failure_is_shared_without_repeating_provider_work(self):
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def failing_provider(_link, _video_id):
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return None

        with patch.object(youtube, "_download_song_impl", side_effect=failing_provider):
            first = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
            await asyncio.wait_for(started.wait(), timeout=2)
            second = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
            await asyncio.sleep(0.02)
            release.set()
            results = await asyncio.gather(first, second)

        self.assertEqual(calls, 1)
        self.assertEqual(results, [None, None])
        self.assertFalse(youtube._download_flights)

    async def test_cancelled_flight_releases_waiter_and_allows_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            entered = asyncio.Event()
            release_first = asyncio.Event()
            calls = 0
            output = Path(directory) / "dQw4w9WgXcQ.external.mp3"

            async def sometimes_slow(_link, video_id):
                nonlocal calls
                calls += 1
                if calls == 1:
                    entered.set()
                    await release_first.wait()
                output.write_bytes(video_id.encode() * 256)
                return str(output)

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_song_impl", side_effect=sometimes_slow
            ):
                first = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                await asyncio.wait_for(entered.wait(), timeout=2)
                second = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                await asyncio.sleep(0.02)
                first.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await first
                result = await asyncio.wait_for(second, timeout=2)

            self.assertEqual(calls, 2)
            self.assertEqual(result, str(output))
            self.assertFalse(youtube._download_flights)

    async def test_distinct_video_ids_do_not_share_a_single_flight(self):
        with tempfile.TemporaryDirectory() as directory:
            started = {"dQw4w9WgXcQ": asyncio.Event(), "9bZkp7q19f0": asyncio.Event()}
            release = asyncio.Event()
            calls = []

            async def slow_provider(video_id, *, video=False):
                calls.append(video_id)
                started[video_id].set()
                await release.wait()
                path = Path(directory) / f"{video_id}.external.mp3"
                path.write_bytes(b"x" * 2048)
                return str(path)

            with patch.object(youtube, "DOWNLOAD_DIR", directory), patch.object(
                youtube, "_download_via_external_api", side_effect=slow_provider
            ):
                first = asyncio.create_task(youtube.download_song("dQw4w9WgXcQ"))
                second = asyncio.create_task(youtube.download_song("9bZkp7q19f0"))
                await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started.values())), timeout=2)
                release.set()
                results = await asyncio.gather(first, second)

            self.assertCountEqual(calls, ["dQw4w9WgXcQ", "9bZkp7q19f0"])
            self.assertTrue(all(results))


if __name__ == "__main__":
    unittest.main()
