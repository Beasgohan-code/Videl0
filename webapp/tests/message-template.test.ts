import assert from "node:assert/strict";
import test from "node:test";
import { previewGroupMessage } from "../src/lib/message-template";

test("welcome placeholders preview as harmless sample text", () => {
  assert.deepEqual(previewGroupMessage("Welcome {mention} ({id}) to {title}!", "Night Owls"), {
    text: "Welcome @Mira (123456789) to Night Owls!",
    unknown: [],
  });
});

test("unknown template variables stay visible and are listed once", () => {
  assert.deepEqual(previewGroupMessage("Hi {name}, see {badge} and {badge}", ""), {
    text: "Hi Mira, see {badge} and {badge}",
    unknown: ["{badge}"],
  });
});
