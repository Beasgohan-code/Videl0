import test from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server";
import { GET as musicStatus } from "../src/app/api/music/status/route";
import { ownerMarker } from "../src/lib/auth";

test("music download status is owner-only and rejects malformed task IDs", async () => {
  const previousSecret = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "music-center-test-secret";
  const originalFetch = globalThis.fetch;
  let backendCalls = 0;
  globalThis.fetch = async () => {
    backendCalls += 1;
    return Response.json({ ok: true, task: { status: "unknown" } });
  };
  try {
    const guest = await musicStatus(new NextRequest("https://studio.example/api/music/status?task_id=0123456789abcdef"));
    assert.equal(guest.status, 401);
    const token = ownerMarker();
    assert.ok(token);
    const malformed = await musicStatus(new NextRequest("https://studio.example/api/music/status?task_id=bad", {
      headers: { cookie: `videl_owner=${token}` },
    }));
    assert.equal(malformed.status, 400);
    assert.equal(backendCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    if (previousSecret === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = previousSecret;
  }
});
