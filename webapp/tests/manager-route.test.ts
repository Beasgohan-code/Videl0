import test from "node:test";
import assert from "node:assert/strict";
import { GET, POST } from "../src/app/api/manager/[id]/route";
import { GET as groups } from "../src/app/api/manager/route";
import { playerMarker } from "../src/lib/player-auth";

const context = (id: string) => ({ params: Promise.resolve({ id }) });
const playerCookie = () => {
  const marker = playerMarker({ id: 24680, name: "Group admin" });
  assert.ok(marker);
  return `videl_player=${marker}`;
};

test("group-manager routes reject guests before contacting the backend", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new Error("unexpected backend call"); };
  try {
    assert.equal((await groups(new Request("https://studio.test/api/manager"))).status, 401);
    assert.equal((await GET(new Request("https://studio.test/api/manager/-100123"), context("-100123"))).status, 401);
    assert.equal((await POST(new Request("https://studio.test/api/manager/-100123", { method: "POST" }), context("-100123"))).status, 401);
    assert.equal(calls, 0);
  } finally { globalThis.fetch = originalFetch; }
});

test("group-manager writes reject cross-site requests and malformed objects before forwarding", async () => {
  const oldSecret = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "offline-manager-route";
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return Response.json({ ok: true }); };
  try {
    const crossSite = await POST(new Request("https://studio.test/api/manager/-100123", {
      method: "POST", headers: { cookie: playerCookie(), origin: "https://evil.test", "content-type": "application/json" },
      body: JSON.stringify({ action: "settings", settings: { lock_links: true } }),
    }), context("-100123"));
    assert.equal(crossSite.status, 403);

    const invalidId = await GET(new Request("https://studio.test/api/manager/123", { headers: { cookie: playerCookie() } }), context("123"));
    assert.equal(invalidId.status, 400);
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    if (oldSecret === undefined) delete process.env.WEBAPP_SECRET; else process.env.WEBAPP_SECRET = oldSecret;
  }
});

test("audit filters are bounded, date-normalized and carry a short-lived actor assertion", async () => {
  const oldSecret = process.env.WEBAPP_SECRET;
  const oldBackend = process.env.VIDEL_BACKEND_URL;
  process.env.WEBAPP_SECRET = "offline-manager-route";
  process.env.VIDEL_BACKEND_URL = "https://backend.test";
  const originalFetch = globalThis.fetch;
  let forwardedUrl = "";
  let forwardedHeaders: Headers | undefined;
  globalThis.fetch = async (input, init) => {
    forwardedUrl = String(input);
    forwardedHeaders = new Headers(init?.headers);
    return Response.json({ ok: true, events: [] });
  };
  try {
    const response = await GET(new Request(
      "https://studio.test/api/manager/-100123?audit=1&kind=moderation&q=%20ban%20&actor=24680&from=2026-10-01&through=2026-10-15&before=bad",
      { headers: { cookie: playerCookie() } },
    ), context("-100123"));
    assert.equal(response.status, 200);
    const url = new URL(forwardedUrl);
    assert.equal(url.pathname, "/internal/manager/chat/-100123/audit");
    assert.equal(url.searchParams.get("limit"), "40");
    assert.equal(url.searchParams.get("kind"), "moderation");
    assert.equal(url.searchParams.get("q"), "ban");
    assert.equal(url.searchParams.get("actor"), "24680");
    assert.equal(url.searchParams.get("from"), "2026-10-01T00:00:00.000Z");
    assert.equal(url.searchParams.get("through"), "2026-10-15T00:00:00.000Z");
    assert.equal(url.searchParams.has("before"), false);
    assert.equal(forwardedHeaders?.get("x-videl-actor"), "24680");
    assert.ok(Number(forwardedHeaders?.get("x-videl-actor-exp")) > Math.floor(Date.now() / 1000));
    assert.ok(forwardedHeaders?.get("x-videl-actor-sig"));
  } finally {
    globalThis.fetch = originalFetch;
    if (oldSecret === undefined) delete process.env.WEBAPP_SECRET; else process.env.WEBAPP_SECRET = oldSecret;
    if (oldBackend === undefined) delete process.env.VIDEL_BACKEND_URL; else process.env.VIDEL_BACKEND_URL = oldBackend;
  }
});
