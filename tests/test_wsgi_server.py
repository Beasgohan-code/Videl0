import unittest
from unittest.mock import patch

from videl import __main__ as backend


class ProductionServerTests(unittest.TestCase):
    def test_render_api_uses_waitress_instead_of_flasks_development_server(self):
        with patch("waitress.serve") as serve, patch.object(backend, "_log_all_urls_console"):
            backend._run_flask()
        serve.assert_called_once_with(
            backend._flask,
            host="0.0.0.0",
            port=backend.BACKEND_PORT,
            threads=8,
            channel_timeout=30,
            ident="Videl",
        )
