import test from "node:test";
import assert from "node:assert/strict";
import { hasFormatting, markdownToTelegram } from "../src/lib/markdown-telegram";

test("inline markdown becomes Telegram HTML", () => {
  assert.equal(
    markdownToTelegram("**Bold** and *italic* and ~~gone~~ and `code`"),
    "<b>Bold</b> and <i>italic</i> and <s>gone</s> and <code>code</code>",
  );
  assert.equal(markdownToTelegram("__Also bold__ with _also italic_"), "<b>Also bold</b> with <i>also italic</i>");
  assert.equal(markdownToTelegram("||secret||"), "<tg-spoiler>secret</tg-spoiler>");
});

test("headings, bullets and quotes are readable in Telegram", () => {
  assert.equal(markdownToTelegram("## A heading"), "<b>A heading</b>");
  assert.equal(markdownToTelegram("- one\n- two"), "• one\n• two");
  assert.equal(
    markdownToTelegram("> first line\n> second line\n\nafter"),
    "<blockquote>first line\nsecond line</blockquote>\n\nafter",
  );
});

test("code fences stay literal and are escaped", () => {
  const html = markdownToTelegram("```\n<b>not bold</b>\n**not bold**\n```");
  assert.equal(html, "<pre>&lt;b&gt;not bold&lt;/b&gt;\n**not bold**</pre>");
});

test("html in the input is escaped before formatting", () => {
  assert.equal(
    markdownToTelegram('<script>alert("x")</script> **safe**'),
    '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; <b>safe</b>',
  );
});

test("only http, https and tg links are converted", () => {
  assert.equal(
    markdownToTelegram("[site](https://example.com/a?b=1&c=2)"),
    '<a href="https://example.com/a?b=1&amp;c=2">site</a>',
  );
  const unsafe = markdownToTelegram("[click](javascript:alert(1))");
  assert.ok(!unsafe.includes("<a"));
  assert.match(unsafe, /click/);
});

test("formatting detection reflects the output", () => {
  assert.equal(hasFormatting(markdownToTelegram("plain text")), false);
  assert.equal(hasFormatting(markdownToTelegram("**bold**")), true);
});
