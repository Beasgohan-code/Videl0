import test from "node:test";
import assert from "node:assert/strict";
import { GET } from "../src/app/api/summary/route";
import { GET as health } from "../src/app/api/health/route";
test("guests cannot access legacy bot summary or health diagnostics", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    throw new Error("Must not contact backend");
  };
  try {
    for (const endpoint of [GET, health]) {
      const response = await endpoint(
        new Request("https://studio.example/api/summary"),
      );
      assert.equal(response.status, 401);
      assert.equal(calls, 0);
    }
  } finally {
    globalThis.fetch = original;
  }
});
