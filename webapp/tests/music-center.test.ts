import test from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server";
import { GET as musicStatus } from "../src/app/api/music/status/route";
import { GET as musicTrack } from "../src/app/api/music/track/[videoId]/route";
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

test("expired owner credentials reject a stream request before backend access", async () => {
  const previousSecret = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "expired-stream-test-secret";
  const expiredToken = ownerMarker(1);
  assert.ok(expiredToken);
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error("Expired stream must not reach backend");
  };
  try {
    const response = await musicTrack(new NextRequest("https://studio.example/api/music/track/abcdefghijk", {
      headers: { cookie: `videl_owner=${expiredToken}` },
    }), { params: Promise.resolve({ videoId: "abcdefghijk" }) });
    assert.equal(response.status, 401);
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    if (previousSecret === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = previousSecret;
  }
});

test("owner music track proxy preserves range response and never exposes internal auth", async () => {
  const previous = {
    secret: process.env.WEBAPP_SECRET,
    backend: process.env.VIDEL_BACKEND_URL,
  };
  process.env.WEBAPP_SECRET = "music-proxy-test-secret";
  process.env.VIDEL_BACKEND_URL = "https://backend.example";
  const token = ownerMarker();
  assert.ok(token);
  const originalFetch = globalThis.fetch;
  let requestUrl = "";
  let requestHeaders = new Headers();
  const bytes = new Uint8Array([50, 51, 52, 53]);
  globalThis.fetch = async (input, init) => {
    requestUrl = String(input);
    requestHeaders = new Headers(init?.headers);
    return new Response(bytes, {
      status: 206,
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": "4",
        "Accept-Ranges": "bytes",
        "Content-Range": "bytes 2-5/10",
      },
    });
  };
  try {
    const response = await musicTrack(new NextRequest(
      "https://studio.example/api/music/track/abcdefghijk?task_id=0123456789abcdef0123456789abcdef",
      {
        headers: {
          cookie: `videl_owner=${token}`,
          range: "bytes=2-5",
          "if-range": '"media-etag"',
        },
      },
    ), { params: Promise.resolve({ videoId: "abcdefghijk" }) });

    assert.equal(requestUrl, "https://backend.example/internal/music/track/abcdefghijk?task_id=0123456789abcdef0123456789abcdef");
    assert.equal(requestHeaders.get("range"), "bytes=2-5");
    assert.equal(requestHeaders.get("if-range"), '"media-etag"');
    assert.equal(requestHeaders.get("x-videl-internal"), "music-proxy-test-secret");
    assert.equal(response.status, 206);
    assert.equal(response.headers.get("content-type"), "audio/mpeg");
    assert.equal(response.headers.get("content-length"), "4");
    assert.equal(response.headers.get("accept-ranges"), "bytes");
    assert.equal(response.headers.get("content-range"), "bytes 2-5/10");
    assert.equal(response.headers.get("content-disposition"), "inline");
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.equal(response.headers.get("x-videl-internal"), null);
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
  } finally {
    globalThis.fetch = originalFetch;
    if (previous.secret === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = previous.secret;
    if (previous.backend === undefined) delete process.env.VIDEL_BACKEND_URL;
    else process.env.VIDEL_BACKEND_URL = previous.backend;
  }
});
