import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.modules import downloader


class DownloaderCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_download_pill_is_acknowledged_without_editing_message(self):
        query = NS(data="dl:unknown", message=NS(), answer=AsyncMock())
        with patch.object(downloader, "rich_edit", new=AsyncMock()) as edit:
            await downloader.dl_cbs(downloader.bot, query)

        query.answer.assert_awaited_once()
        edit.assert_not_awaited()

    async def test_download_pill_with_extra_payload_is_not_treated_as_valid(self):
        query = NS(data="dl:song:unexpected", message=NS(), answer=AsyncMock())
        with patch.object(downloader, "rich_edit", new=AsyncMock()) as edit:
            await downloader.dl_cbs(downloader.bot, query)

        query.answer.assert_awaited_once()
        edit.assert_not_awaited()

    async def test_known_download_help_callback_answers_and_edits(self):
        query = NS(data="dl:song", message=NS(), answer=AsyncMock())
        with patch.object(downloader, "rich_edit", new=AsyncMock()) as edit:
            await downloader.dl_cbs(downloader.bot, query)

        query.answer.assert_awaited_once_with("Use /song followed by a title or link")
        edit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
