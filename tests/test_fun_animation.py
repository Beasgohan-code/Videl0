"""Validate API-backed reaction GIFs and the locally drawn offline fallback."""
import asyncio
import io
import unittest
from unittest.mock import patch

from videl.utils import fun_animation


class OriginalFunAnimationTests(unittest.TestCase):
    @unittest.skipUnless(fun_animation.available(), "Pillow is an optional runtime dependency")
    def test_each_reaction_has_a_small_looping_original_gif_fallback(self):
        from PIL import Image
        for action in ("hug", "kiss", "like", "wave", "highfive", "dance"):
            with self.subTest(action=action):
                data = fun_animation.render(action, "actor:target")
                self.assertTrue(data.startswith((b"GIF87a", b"GIF89a")))
                with Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.size, (512, 512))
                    self.assertGreater(image.n_frames, 1)
                    self.assertEqual(image.info.get("loop"), 0)

    def test_unknown_animation_names_fail_closed(self):
        self.assertIsNone(fun_animation.render("unknown"))

    def test_like_uses_the_documented_thumbsup_endpoint_and_validates_media(self):
        gif = b"GIF89a" + b"test"
        remote = "https://nekos.best/api/v2/thumbsup/example.gif"

        class Response:
            status = 200
            content_length = len(gif)

            def __init__(self, payload=None):
                self.payload = payload
                self.content = self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def json(self, **_kwargs):
                return self.payload

            async def read(self, _limit):
                return gif

        class Session:
            def __init__(self):
                self.urls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            def get(self, url, **_kwargs):
                self.urls.append(url)
                if url == fun_animation._API_ROOT + "thumbsup":
                    return Response({"results": [{"url": remote}]})
                return Response()

        session = Session()
        with patch.object(fun_animation, "_REMOTE_CACHE", {}), \
             patch.object(fun_animation.aiohttp, "ClientSession", return_value=session):
            result = asyncio.run(fun_animation.fetch_reaction("like"))

        self.assertEqual(result.data, gif)
        self.assertEqual(session.urls, [fun_animation._API_ROOT + "thumbsup", remote])
