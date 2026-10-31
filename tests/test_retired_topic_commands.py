import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
RETIRED = {"topicopen", "topicrename", "topicnew", "topicclose"}


class RetiredTopicCommandTests(unittest.TestCase):
    def test_no_topic_slash_command_handler_remains(self):
        source = (ROOT / "videl/modules/api_tools.py").read_text()
        self.assertNotIn('filters.command(["topicnew", "topicrename", "topicclose", "topicopen"]', source)
        self.assertNotIn("async def topic_command(", source)

    def test_command_reference_and_web_guide_hide_retired_commands(self):
        reference = (ROOT / "docs/COMMAND_REFERENCE.md").read_text()
        self.assertFalse(any(f"`/{name}`" in reference for name in RETIRED))
        source = (ROOT / "webapp/src/lib/commands.ts").read_text()
        marker = "export const BOT_COMMANDS: BotCommand[] = "
        start = source.index(marker) + len(marker)
        depth = 0
        quoted = escaped = False
        end = None
        for index, char in enumerate(source[start:], start):
            if quoted:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == '"': quoted = False
                continue
            if char == '"': quoted = True
            elif char == "[": depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        rows = json.loads(source[start:end])
        self.assertFalse(RETIRED & {row["name"] for row in rows})
        self.assertEqual(len(rows), len({row["name"] for row in rows}))
