import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.plugins import notes


class FilterWatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_longest_matching_phrase_wins_independent_of_storage_order(self):
        documents = [
            {"keyword": "hello there", "reply": "specific"},
            {"keyword": "hello", "reply": "generic"},
        ]
        message = NS(
            text="Well, hello there friend",
            from_user=NS(id=1, is_bot=False),
            chat=NS(id=-95001),
            reply_text=AsyncMock(),
        )
        store = NS(find=lambda _query: _Cursor(documents))
        with patch.object(notes, "_filters", return_value=store):
            await notes.filter_watcher(None, message)
        message.reply_text.assert_awaited_once_with("specific", parse_mode=None)

    async def test_filters_do_not_reply_to_commands_or_bot_messages(self):
        documents = [{"keyword": "ban", "reply": "triggered"}]
        store = NS(find=lambda _query: _Cursor(documents))
        for text, user in (("/ban @person", NS(id=2, is_bot=False)), ("ban", NS(id=3, is_bot=True))):
            message = NS(text=text, from_user=user, chat=NS(id=-95002), reply_text=AsyncMock())
            with patch.object(notes, "_filters", return_value=store):
                await notes.filter_watcher(None, message)
            message.reply_text.assert_not_awaited()


class _Cursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def limit(self, count):
        return self.documents[:count]

    def __iter__(self):
        return iter(self.documents)


if __name__ == "__main__":
    unittest.main()
