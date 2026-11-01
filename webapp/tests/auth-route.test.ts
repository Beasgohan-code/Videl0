import test from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server";
import { POST, DELETE } from "../src/app/api/auth/route";
import { GET as stats } from "../src/app/api/stats/route";
import { GET as groups } from "../src/app/api/groups/route";
import { GET as chat } from "../src/app/api/chat/route";
import { GET as analytics } from "../src/app/api/analytics/route";
import { GET as settings } from "../src/app/api/bot-settings/route";
import { POST as publish } from "../src/app/api/channel/route";
import { GET as groupDetail, POST as groupAction } from "../src/app/api/groups/[id]/route";
import { POST as groupBulk } from "../src/app/api/groups/bulk/route";
import { POST as broadcast } from "../src/app/api/broadcast/route";
import { GET as onboarding } from "../src/app/api/onboarding/route";
import { GET as arcadeEvents, POST as createEvent } from "../src/app/api/arcade/events/route";
import { GET as eventGroups } from "../src/app/api/arcade/events/groups/route";
import { GET as eventDetail, POST as rsvpEvent } from "../src/app/api/arcade/events/[id]/route";

test("all private bot APIs deny guests without contacting the backend", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    throw new Error("Unexpected backend request");
  };
  try {
    for (const handler of [stats, groups, chat, analytics, settings, onboarding])
      assert.equal(
        (await handler(new NextRequest("https://studio.example/api/private")))
          .status,
        401,
      );
    for (const handler of [publish, broadcast])
      assert.equal(
        (
          await handler(
            new NextRequest("https://studio.example/api/private", {
              method: "POST",
            }),
          )
        ).status,
        401,
      );
    for (const handler of [groupDetail, groupAction])
      assert.equal(
        (
          await handler(
            new NextRequest("https://studio.example/api/groups/-100123"),
            { params: Promise.resolve({ id: "-100123" }) },
          )
        ).status,
        401,
      );
    assert.equal(
      (
        await groupBulk(
          new NextRequest("https://studio.example/api/groups/bulk", {
            method: "POST",
          }),
        )
      ).status,
      401,
    );
    for (const handler of [arcadeEvents, eventGroups])
      assert.equal(
        (await handler(new NextRequest("https://studio.example/api/arcade/events"))).status,
        401,
      );
    assert.equal(
      (await createEvent(new NextRequest("https://studio.example/api/arcade/events", { method: "POST" }))).status,
      401,
    );
    for (const handler of [eventDetail, rsvpEvent])
      assert.equal(
        (await handler(
          new NextRequest("https://studio.example/api/arcade/events/ABCDEFGH", { method: handler === rsvpEvent ? "POST" : "GET" }),
          { params: Promise.resolve({ id: "ABCDEFGH" }) },
        )).status,
        401,
      );
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = original;
  }
});
test("auth proxy checks explicit owner even when a backend accepts another user", async () => {
  const original = globalThis.fetch;
  const oldUrl = process.env.VIDEL_BACKEND_URL,
    oldSecret = process.env.WEBAPP_SECRET;
  process.env.VIDEL_BACKEND_URL = "https://backend.example";
  process.env.WEBAPP_SECRET = "offline-secret";
  try {
    for (const [id, status] of [
      [1, 403],
      [6265999542, 200],
    ]) {
      globalThis.fetch = async () =>
        Response.json({ ok: true, user: { id, first_name: "Test" } });
      const response = await POST(
        new NextRequest("https://studio.example/api/auth", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ initData: "offline-fixture" }),
        }),
      );
      assert.equal(response.status, status);
      assert.equal(response.headers.getSetCookie().length, 2);
      if (status === 403)
        assert.ok(response.headers.get("set-cookie")?.includes("Max-Age=0"));
      else {
        assert.equal((await response.json()).owner, true);
        const cookies = response.headers.getSetCookie();
        assert.ok(cookies.some((cookie) => cookie.startsWith("videl_owner=") && cookie.includes("HttpOnly") && cookie.includes("Secure") && cookie.includes("SameSite=Lax") && cookie.includes("Max-Age=86400")));
        assert.ok(cookies.some((cookie) => cookie.startsWith("videl_owner_embedded=") && cookie.includes("HttpOnly") && cookie.includes("Secure") && cookie.includes("SameSite=None") && cookie.includes("Partitioned") && cookie.includes("Max-Age=86400")));
      }
    }
  } finally {
    globalThis.fetch = original;
    if (oldUrl === undefined) delete process.env.VIDEL_BACKEND_URL;
    else process.env.VIDEL_BACKEND_URL = oldUrl;
    if (oldSecret === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = oldSecret;
  }
});
test("cross-site sign-in is rejected and sign-out clears both cookie contexts", async () => {
  const req = new NextRequest("https://studio.example/api/auth", {
    method: "POST",
    headers: { origin: "https://evil.example" },
  });
  assert.equal((await POST(req)).status, 403);
  const logout = await DELETE(
    new NextRequest("https://studio.example/api/auth", { method: "DELETE" }),
  );
  assert.equal(logout.status, 200);
  assert.equal(logout.headers.getSetCookie().length, 2);
  assert.ok(
    logout.headers
      .getSetCookie()
      .every((cookie) => cookie.includes("Max-Age=0")),
  );
});
