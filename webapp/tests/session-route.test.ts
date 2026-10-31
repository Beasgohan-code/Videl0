import test from "node:test";
import assert from "node:assert/strict";
import { DELETE, GET, POST } from "../src/app/api/session/route";

const oldEnv = () => ({
  secret: process.env.WEBAPP_SECRET,
  backend: process.env.VIDEL_BACKEND_URL,
});
function restoreEnv(previous: ReturnType<typeof oldEnv>) {
  if (previous.secret === undefined) delete process.env.WEBAPP_SECRET;
  else process.env.WEBAPP_SECRET = previous.secret;
  if (previous.backend === undefined) delete process.env.VIDEL_BACKEND_URL;
  else process.env.VIDEL_BACKEND_URL = previous.backend;
}

test("player session issuance, status and logout use the real route handlers", async () => {
  const previous = oldEnv();
  const originalFetch = globalThis.fetch;
  process.env.WEBAPP_SECRET = "offline-session-route";
  process.env.VIDEL_BACKEND_URL = "https://backend.test";
  let backendCalls = 0;
  globalThis.fetch = async (_input, init) => {
    backendCalls++;
    assert.equal(init?.method, "POST");
    assert.deepEqual(JSON.parse(String(init?.body)), { init_data: "signed-fixture" });
    return Response.json({ ok: true, player: { id: 24680, name: "Test admin" } });
  };
  try {
    const issued = await POST(new Request("https://studio.test/api/session", {
      method: "POST",
      headers: { origin: "https://studio.test", "content-type": "application/json" },
      body: JSON.stringify({ initData: "signed-fixture" }),
    }));
    assert.equal(issued.status, 200);
    assert.equal(backendCalls, 1);
    const cookies = issued.headers.getSetCookie();
    assert.equal(cookies.length, 2);
    assert.ok(cookies.some((cookie) => cookie.startsWith("videl_player=") && cookie.includes("HttpOnly") && cookie.includes("Secure") && cookie.includes("SameSite=Lax")));
    assert.ok(cookies.some((cookie) => cookie.startsWith("videl_player_embedded=") && cookie.includes("HttpOnly") && cookie.includes("Secure") && cookie.includes("SameSite=None") && cookie.includes("Partitioned")));
    const marker = cookies.find((cookie) => cookie.startsWith("videl_player="))!.split(";")[0];

    const status = await GET(new Request("https://studio.test/api/session", { headers: { cookie: marker } }));
    assert.equal(status.status, 200);
    assert.equal((await status.json()).player.id, 24680);

    const logout = await DELETE(new Request("https://studio.test/api/session", { method: "DELETE", headers: { origin: "https://studio.test" } }));
    assert.equal(logout.status, 200);
    assert.equal(logout.headers.getSetCookie().length, 2);
    assert.ok(logout.headers.getSetCookie().every((cookie) => cookie.includes("Max-Age=0")));
    assert.equal((await GET(new Request("https://studio.test/api/session"))).status, 401);
    assert.equal(backendCalls, 1, "session status and logout must not make backend calls");
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(previous);
  }
});

test("player login and logout refuse cross-site requests before backend access", async () => {
  const previous = oldEnv();
  const originalFetch = globalThis.fetch;
  process.env.WEBAPP_SECRET = "offline-session-route";
  process.env.VIDEL_BACKEND_URL = "https://backend.test";
  let calls = 0;
  globalThis.fetch = async () => { calls++; return Response.json({ ok: true }); };
  try {
    const body = JSON.stringify({ initData: "fixture" });
    const login = await POST(new Request("https://studio.test/api/session", {
      method: "POST", headers: { origin: "https://evil.test", "content-type": "application/json" }, body,
    }));
    assert.equal(login.status, 403);
    const logout = await DELETE(new Request("https://studio.test/api/session", {
      method: "DELETE", headers: { origin: "https://evil.test" },
    }));
    assert.equal(logout.status, 403);
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(previous);
  }
});
