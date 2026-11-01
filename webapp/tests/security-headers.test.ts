import test from "node:test";
import assert from "node:assert/strict";
import config from "../next.config.js";

test("global web security headers constrain content framing and browser capabilities", async () => {
  const groups = await config.headers?.();
  assert.ok(groups);
  const headers = new Map(groups.flatMap((group) => group.headers.map(({ key, value }) => [key.toLowerCase(), value])));
  assert.equal(headers.get("x-content-type-options"), "nosniff");
  assert.equal(headers.get("referrer-policy"), "strict-origin-when-cross-origin");
  assert.match(headers.get("content-security-policy") || "", /frame-ancestors 'self' https:\/\/web\.telegram\.org https:\/\/\*\.telegram\.org/);
  assert.match(headers.get("permissions-policy") || "", /microphone=\(self "https:\/\/web\.telegram\.org"\)/);
  assert.match(headers.get("permissions-policy") || "", /camera=\(\)/);
  assert.equal(headers.get("x-permitted-cross-domain-policies"), "none");
});
