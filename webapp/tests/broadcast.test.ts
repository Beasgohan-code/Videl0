import test from "node:test";
import assert from "node:assert/strict";
import { normalizeBroadcastButtons } from "../src/lib/broadcast";

test("broadcast inline buttons normalize labels and keep only secure HTTPS destinations", () => {
  assert.deepEqual(normalizeBroadcastButtons([{ text: "  Visit  ", url: "https://example.com/path" }]), [
    { text: "Visit", url: "https://example.com/path" },
  ]);
});

test("broadcast inline buttons reject unsafe URLs, credentials, oversized labels and excess buttons", () => {
  for (const buttons of [
    [{ text: "Bad", url: "javascript:alert(1)" }],
    [{ text: "Bad", url: "https://user:pass@example.com" }],
    [{ text: "x".repeat(65), url: "https://example.com" }],
    Array.from({ length: 9 }, (_, i) => ({ text: `Link ${i}`, url: `https://example.com/${i}` })),
  ]) assert.equal(normalizeBroadcastButtons(buttons), null);
});
