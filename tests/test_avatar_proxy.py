"""Profile photos come from Telegram, not arbitrary image URLs."""
import unittest
from unittest.mock import Mock, patch

from videl.utils import avatars


class AvatarSafetyTests(unittest.TestCase):
    def test_only_telegram_https_hosts_are_followed(self):
        for url in (
            "https://t.me/i/userpic/320/abc.jpg",
            "https://cdn.telegram.org/avatar.jpg",
            "https://api.telegram.org/file/bot123/photos/1.jpg",
        ):
            self.assertTrue(avatars._allowed(url), url)
        for url in (
            "http://t.me/avatar.jpg",
            "https://evil.example/t.me/avatar.jpg",
            "https://telegram.org.evil.example/photo.jpg",
            "file:///etc/passwd",
        ):
            self.assertFalse(avatars._allowed(url), url)

    @patch("videl.utils.avatars.requests.get")
    def test_download_is_bounded_and_image_typed(self, get):
        response = Mock(status_code=200)
        response.headers = {"Content-Type": "image/png; charset=binary"}
        response.iter_content.return_value = [b"png"]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        get.return_value = response
        mime, payload = avatars._download("https://t.me/i/userpic/1.png")
        self.assertEqual(mime, "image/png")
        self.assertEqual(payload, b"png")
        self.assertEqual(get.call_args.kwargs["timeout"], (4, 10))

    def test_oversized_avatar_refuses_the_download(self):
        chunks = [b"x" * 16384] * (avatars.MAX_BYTES // 16384 + 1)
        response = Mock(status_code=200)
        response.headers = {"Content-Type": "image/jpeg"}
        response.iter_content.return_value = chunks
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("videl.utils.avatars.requests.get", return_value=response):
            with self.assertRaises(avatars.AvatarError) as caught:
                avatars._download("https://t.me/i/userpic/large.jpg")
        self.assertEqual(caught.exception.status, 413)
