import test from "node:test";
import assert from "node:assert/strict";
import { parseDraft, parseDrafts } from "../src/lib/post-drafts";
const draft = {
  id: "one",
  chatId: "@community",
  text: "<b>Update</b>",
  parseMode: "HTML",
  mediaUrl: "https://example.com/post.jpg",
  buttons: [[{ text: "Visit", url: "https://example.com" }]],
  savedAt: "2026-10-20T07:00:00Z",
};
test("draft recovery preserves editable formatted text and valid links", () =>
  assert.deepEqual(parseDraft(draft), draft));
test("corrupt browser storage cannot crash the workspace", () => {
  for (const json of ["broken", "null", "{}", "[null,{},42]"])
    assert.deepEqual(parseDrafts(json), []);
  assert.equal(parseDraft({ ...draft, savedAt: "invalid" }), null);
  assert.equal(parseDraft({ ...draft, text: "x".repeat(65537) }), null);
});
test("recovery strips stale session images and unsafe keyboard links", () => {
  const parsed = parseDraft({
    ...draft,
    mediaUrl: "blob:old-session",
    buttons: [
      [{ text: "Bad", url: "javascript:alert(1)" }],
      [{ text: "Good", url: "https://example.com" }],
      null,
    ],
  });
  assert.equal(parsed?.mediaUrl, "");
  assert.deepEqual(parsed?.buttons, [
    [{ text: "Good", url: "https://example.com" }],
  ]);
});
test("draft lists are bounded and malformed entries are ignored", () => {
  const parsed = parseDrafts(
    JSON.stringify([
      null,
      ...Array.from({ length: 30 }, (_, i) => ({ ...draft, id: String(i) })),
    ]),
  );
  assert.equal(parsed.length, 20);
});
