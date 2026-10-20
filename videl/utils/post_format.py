"""Telegram HTML counts text after entity parsing, not raw markup length."""
from html.parser import HTMLParser


def post_text_length(value: str, parse_mode: str = "HTML") -> int:
    if parse_mode != "HTML":
        return len(value.encode("utf-16-le")) // 2

    class Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    parser = Text()
    parser.feed(value)
    parser.close()
    return len("".join(parser.parts).encode("utf-16-le")) // 2
