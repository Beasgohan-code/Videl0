import test from "node:test";
import assert from "node:assert/strict";
import { parseDraft, parseDrafts, copyDraft, type PostDraft } from "../src/lib/post-drafts";
const draft: PostDraft = {
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

test("a duplicate is a new draft that starts out saying the same thing", () => {
  const now = new Date("2026-10-21T06:00:00Z");
  const copy = copyDraft(draft, now);
  assert.notEqual(copy.id, draft.id, "a copy is its own draft, not an alias");
  assert.equal(copy.savedAt, now.toISOString());
  assert.equal(copy.text, draft.text);
  assert.equal(copy.chatId, draft.chatId);
  assert.deepEqual(copy.buttons, draft.buttons);
  // Editing the copy must not reach back into the original: button rows are
  // shared objects in memory, and a duplicate that silently edits its source
  // is worse than no duplicate at all.
  copy.buttons[0][0].text = "Changed";
  assert.equal(draft.buttons[0][0].text, "Visit");
});
