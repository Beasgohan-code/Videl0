"""Poster rendering is optional and never fetches arbitrary user-supplied URLs."""
import asyncio
import io
import unittest

from videl.utils import player_poster


class PlayerPosterTests(unittest.TestCase):
    def test_cover_fetch_is_https_and_cdn_allowlisted(self):
        self.assertTrue(player_poster._allowed_cover_url("https://i.ytimg.com/vi/example/hqdefault.jpg"))
        self.assertTrue(player_poster._allowed_cover_url("https://i.scdn.co/image/example"))
        for url in (
            "http://i.ytimg.com/image.jpg",
            "https://127.0.0.1/image.jpg",
            "https://i.ytimg.com.attacker.example/image.jpg",
            "https://user@i.ytimg.com/image.jpg",
            "https://i.ytimg.com:444/image.jpg",
        ):
            with self.subTest(url=url):
                self.assertFalse(player_poster._allowed_cover_url(url))

    def test_poster_is_optional_when_pillow_is_not_installed(self):
        if player_poster._usable_pillow():
            self.skipTest("Pillow is installed; the rendering path is tested below")
        self.assertIsNone(asyncio.run(player_poster.build({"title": "No image dependency"})))

    @unittest.skipUnless(player_poster._usable_pillow(), "Pillow is an optional runtime dependency")
    def test_original_poster_renders_without_external_artwork(self):
        data = player_poster._render({
            "title": "ഹൃദയം പാടുന്നു — Malayalam song title",
            "artist": "Videl artists",
            "requester": "Listener",
            "duration": "3:45",
        }, None)
        self.assertTrue(data.startswith(b"\xff\xd8"))
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1280, 720))
            self.assertEqual(image.format, "JPEG")
