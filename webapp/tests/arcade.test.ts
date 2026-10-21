import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render } from "./dom";

/**
 * The arcade's client rules, tested where they can be wrong silently:
 * the cookie that names a player, the geometry that places a Ludo token, the
 * clock text, and the two screens that must render before any network answer.
 */

process.env.WEBAPP_SECRET = process.env.WEBAPP_SECRET || "test-secret";

function cookieRequest(cookie?: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (cookie) headers.set("cookie", cookie);
  return new Request("https://videl.example/api/session", { ...init, headers });
}

test("a player cookie round-trips and cannot be forged", async () => {
  const { playerCookies, validPlayer } = await import("../src/lib/player-auth");
  const cookies = playerCookies({ id: 42, name: "Ada" });
  assert.equal(cookies.length, 2, "a plain and a partitioned cookie for the WebView");
  const raw = cookies[0].split(";")[0];
  const player = validPlayer(cookieRequest(raw));
  assert.equal(player?.id, 42);
  assert.equal(player?.name, "Ada");

  // Flipping one character of the signature must invalidate the whole token.
  const [value, signature] = raw.split("=")[1].split(".");
  const tampered = `${value}.${signature.slice(0, -1)}${signature.endsWith("a") ? "b" : "a"}`;
  assert.equal(validPlayer(cookieRequest(`videl_player=${tampered}`)), null);

  // A token naming someone else is just as invalid.
  const other = await import("../src/lib/player-auth");
  const forged = await (async () => {
    const marker = other.playerMarker({ id: 99, name: "Mallory" });
    return marker!.split(".")[0] + "." + marker!.split(".")[1].replace(/^./, "0");
  })();
  assert.equal(validPlayer(cookieRequest(`videl_player=${forged}`)), null);
});

test("an expired or oversized player cookie is refused", async () => {
  const { playerMarker, validPlayer } = await import("../src/lib/player-auth");
  const marker = playerMarker({ id: 7, name: "Old" })!;
  const longAgo = Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 31;
  assert.equal(validPlayer(cookieRequest(`videl_player=${marker}`), longAgo), null);
  assert.equal(validPlayer(cookieRequest(`videl_player=${"x".repeat(4000)}`)), null);
});

test("the player cookie is not the owner cookie", async () => {
  const { playerCookies, PLAYER_COOKIE } = await import("../src/lib/player-auth");
  const cookie = playerCookies({ id: 5, name: "Player" })[0];
  assert.ok(cookie.startsWith(`${PLAYER_COOKIE}=`));
  assert.ok(!cookie.includes("videl_owner"));
});

test("an actor assertion names the player and expires quickly", async () => {
  const { actorHeaders } = await import("../src/lib/player-auth");
  const headers = actorHeaders(1234, 1_700_000_000);
  assert.equal(headers["X-Videl-Actor"], "1234");
  assert.equal(Number(headers["X-Videl-Actor-Exp"]) - 1_700_000_000, 50);
  assert.match(headers["X-Videl-Actor-Sig"], /^[a-f0-9]{64}$/);
  assert.notEqual(
    actorHeaders(1235, 1_700_000_000)["X-Videl-Actor-Sig"],
    headers["X-Videl-Actor-Sig"],
  );
});

test("a state change from another site is refused before it is read", async () => {
  const { playerRequired, playerCookies } = await import("../src/lib/player-auth");
  const cookie = playerCookies({ id: 9, name: "Ada" })[0].split(";")[0];
  const cross = new Request("https://videl.example/api/arcade", {
    method: "POST",
    headers: { cookie, origin: "https://evil.example" },
  });
  const checked = playerRequired(cross);
  assert.ok("denied" in checked);
  assert.equal(checked.denied.status, 403);

  const same = new Request("https://videl.example/api/arcade", {
    method: "POST",
    headers: { cookie, origin: "https://videl.example" },
  });
  assert.ok("player" in playerRequired(same));
});

test("signed-out reads answer 401 rather than a blank success", async () => {
  const { playerRequired } = await import("../src/lib/player-auth");
  const checked = playerRequired(new Request("https://videl.example/api/arcade"));
  assert.ok("denied" in checked);
  assert.equal(checked.denied.status, 401);
});

test("Ludo tokens sit on the ring, then in their own home column", async () => {
  const { ludoTokenCell, LUDO_RING, LUDO_HOME } = await import("../src/lib/arcade");
  // Seat 1's start is ring square 13; a token that has travelled 5 steps is on
  // square 18, and one that has entered its home column is in column 1.
  const start = LUDO_RING[13];
  const moved = ludoTokenCell(13, 5, 0);
  assert.deepEqual([moved.row, moved.col], [LUDO_RING[18][0], LUDO_RING[18][1]]);
  const home = ludoTokenCell(13, 51, 2);
  assert.deepEqual([home.row, home.col], [...LUDO_HOME[1][0]]);
  assert.equal(home.kind, "home");
  const base = ludoTokenCell(13, -1, 0);
  assert.equal(base.kind, "base");
  assert.ok(!Number.isInteger(base.row), "the base is drawn between squares");
  assert.equal(ludoTokenCell(13, 57, 0).kind, "centre");
});

test("the turn clock never renders a negative number", async () => {
  const { countdown } = await import("../src/lib/arcade");
  const now = Date.parse("2026-10-21T10:00:00.000Z");
  assert.equal(countdown("2026-10-21T10:00:45.000Z", now), "45s");
  assert.equal(countdown("2026-10-21T09:59:00.000Z", now), "0s");
  assert.equal(countdown(null, now), "");
});

test("a finished room names the winner instead of leaking an id", async () => {
  const { winnerText } = await import("../src/lib/arcade");
  const room = (winner: number | "draw" | null) =>
    ({
      code: "ABCDEF",
      status: "done",
      winner,
      seats: [{ user: 1, name: "Ada", seat: 0, online: true }],
    }) as never;
  assert.equal(winnerText(room(0)), "Ada won.");
  assert.equal(winnerText(room("draw")), "A draw.");
  assert.equal(winnerText(room(null)), "The game finished.");
});

test("the arcade screen renders its sign-in card without a session", async () => {
  const { default: Arcade } = await import("../src/components/studio/screens/Arcade");
  const html = render(createElement(Arcade));
  assert.match(html, /Continue with Telegram/);
  assert.match(html, /Ludo/);
  assert.ok(!/undefined/.test(html), "no undefined leaks into the screen");
});

test("the arcade is open without ownership, but the group manager is not", async () => {
  const { canOpenSection } = await import("../src/lib/access");
  assert.equal(canOpenSection("arcade", null), true);
  assert.equal(canOpenSection("groups", null), false);
  assert.equal(canOpenSection("arcade", true), true);
});
