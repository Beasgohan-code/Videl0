import test from "node:test";
import assert from "node:assert/strict";
import { GET } from "../src/app/api/summary/route";
import { GET as health } from "../src/app/api/health/route";
import { ownerMarker } from "../src/lib/auth";
test("owner health view exposes only bounded measured revision and latency fields", async () => {
  const priorSecret = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "health-test-secret";
  const original = globalThis.fetch;
  const marker = ownerMarker();
  assert.ok(marker);
  globalThis.fetch = async () => new Response(JSON.stringify({
    status: "ok", revision: "abc123", api: { p95_ms: 17.5, samples: 9, unsafe: "secret" },
    bot_status: "online", database: "connected", uptime: 5,
    assistant: { configured: true, ready: false, state: "offline", token: "never-forward" },
    media_downloaders: { primary: "shruti", shruti: { state: "configured", configured: true, api_key: "never-forward" }, fallbacks: ["eldian", "local_yt_dlp", "private"] },
  }), { status: 200, headers: { "Content-Type": "application/json" } });
  try {
    const response = await health(new Request("https://studio.example/api/health", {
      headers: { cookie: `videl_owner=${marker}` },
    }));
    const data = await response.json();
    assert.equal(response.status, 200);
    assert.equal(data.revision, "abc123");
    assert.deepEqual(data.api, { p95_ms: 17.5, samples: 9 });
    assert.equal(data.api.unsafe, undefined);
    assert.deepEqual(data.assistant, { configured: true, ready: false, state: "offline" });
    assert.deepEqual(data.media_downloaders, { primary: "shruti", shruti: { state: "configured", configured: true }, fallbacks: ["eldian", "local_yt_dlp"] });
    assert.equal(JSON.stringify(data).includes("never-forward"), false);
  } finally {
    globalThis.fetch = original;
    if (priorSecret === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = priorSecret;
  }
});

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
