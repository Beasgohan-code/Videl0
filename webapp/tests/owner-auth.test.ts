import test from "node:test";
import assert from "node:assert/strict";
import { ownerMarker, validOwnerCookie, ownerRequired } from "../src/lib/auth";
import { telegramLaunchData } from "../src/lib/telegram-launch";
test("owner sessions work in a browser and partitioned Mini App context; fake cookies fail", () => {
  const previous = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "offline-owner-session-test";
  try {
    const marker = ownerMarker();
    for (const name of ["videl_owner", "videl_owner_embedded"]) {
      const req = new Request("https://studio.example/api/stats", {
        headers: { cookie: `${name}=${marker}` },
      });
      assert.equal(validOwnerCookie(req), true);
      assert.equal(ownerRequired(req), null);
    }
    for (const cookie of [
      "",
      "videl_owner=forged",
      `videl_owner=${"0".repeat(64)}`,
    ])
      assert.equal(
        validOwnerCookie(
          new Request("https://studio.example/api/stats", {
            headers: { cookie },
          }),
        ),
        false,
      );
    const crossSite = new Request("https://studio.example/api/channel", {
      method: "POST",
      headers: {
        cookie: `videl_owner_embedded=${marker}`,
        origin: "https://attacker.example",
      },
    });
    assert.equal(ownerRequired(crossSite)?.status, 403);
    assert.equal(
      ownerRequired(
        new Request("https://studio.example/api/channel", {
          method: "POST",
          headers: {
            cookie: `videl_owner_embedded=${marker}`,
            origin: "https://studio.example",
          },
        }),
      ),
      null,
    );
  } finally {
    if (previous === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = previous;
  }
});
test("Mini App launch data works without the SDK and is not confused with a normal link", () => {
  const signed = "user=%7B%22id%22%3A1%7D&auth_date=123&hash=signature";
  assert.equal(
    telegramLaunchData(
      undefined,
      "",
      `#tgWebAppData=${encodeURIComponent(signed)}&tgWebAppVersion=8.0`,
    ),
    signed,
  );
  assert.equal(
    telegramLaunchData("", `?tgWebAppData=${encodeURIComponent(signed)}`, ""),
    signed,
  );
  assert.equal(telegramLaunchData(signed, "", ""), signed);
  assert.equal(telegramLaunchData(undefined, "?tab=auth", ""), "");
  assert.equal(telegramLaunchData("x".repeat(8193), "", ""), "");
});

test("owner sessions expire server-side and old static markers cannot be reused", () => {
  const previous = process.env.WEBAPP_SECRET;
  process.env.WEBAPP_SECRET = "expiry-test";
  try {
    const token = ownerMarker(1000)!;
    const req = new Request("https://studio.example/api/stats", {
      headers: { cookie: `videl_owner=${token}` },
    });
    assert.equal(validOwnerCookie(req, 1000), true);
    assert.equal(validOwnerCookie(req, 1000 + 86400), false);
    assert.equal(validOwnerCookie(req, 800), false);
    const [data, signature] = token.split(".");
    const forged = Buffer.from(
      JSON.stringify({
        ...JSON.parse(Buffer.from(data, "base64url").toString()),
        sub: "1",
      }),
    ).toString("base64url");
    assert.equal(
      validOwnerCookie(
        new Request(req.url, {
          headers: { cookie: `videl_owner=${forged}.${signature}` },
        }),
        1000,
      ),
      false,
    );
    process.env.WEBAPP_SECRET = "rotated";
    assert.equal(validOwnerCookie(req, 1000), false);
  } finally {
    if (previous === undefined) delete process.env.WEBAPP_SECRET;
    else process.env.WEBAPP_SECRET = previous;
  }
});
