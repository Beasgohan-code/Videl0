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
    const [body, signature] = marker!.split(".");
    // Flip a hex digit rather than "replace with 0": the first character can
    // already be 0, which would leave a valid signature in place.
    const flipped = `${signature[0] === "0" ? "1" : "0"}${signature.slice(1)}`;
    return `${body}.${flipped}`;
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
  assert.match(html, /Pull up a chair/);
  for (const name of ["Ludo", "Checkers", "Connect Four", "Reversi", "Tic-tac-toe"]) {
    assert.match(html, new RegExp(name.replace("-", "\\-")), `the lobby shows ${name}`);
  }
  // The three steps are the whole explanation of why a password is not needed.
  assert.match(html, /Open Videl from the bot inside Telegram/);
  assert.match(html, /six-character code/);
  assert.ok(!/undefined/.test(html), "no undefined leaks into the screen");
});

test("seat initials stay readable for any Telegram name", async () => {
  const { initials } = await import("../src/lib/arcade");
  assert.equal(initials("Ada Lovelace"), "AL");
  assert.equal(initials("Grace"), "G");
  assert.equal(initials("  "), "?");
  // Two-character names keep a readable pair rather than the whole string.
  assert.equal(initials("李 小龙"), "李小");
});

test("the clock ring never runs past the turn it belongs to", async () => {
  const { turnFraction } = await import("../src/lib/arcade");
  const now = Date.parse("2026-10-21T10:00:00.000Z");
  assert.equal(turnFraction("2026-10-21T10:01:00.000Z", 60, now), 1);
  assert.equal(turnFraction("2026-10-21T10:00:30.000Z", 60, now), 0.5);
  assert.equal(turnFraction("2026-10-21T09:59:00.000Z", 60, now), 0);
  assert.equal(turnFraction(null, 60, now), 0);
});

test("the arcade is open without ownership, but the group manager is not", async () => {
  const { canOpenSection } = await import("../src/lib/access");
  assert.equal(canOpenSection("arcade", null), true);
  assert.equal(canOpenSection("groups", null), false);
  assert.equal(canOpenSection("arcade", true), true);
});


test("a pasted invite is understood as a code, a link or a Telegram payload", async () => {
  const { codeFromLink, inviteLink, telegramInvite } = await import("../src/lib/arcade");
  assert.equal(codeFromLink("k7m2qx"), "K7M2QX", "a typed code, lower case");
  assert.equal(codeFromLink("  K7M2QX  "), "K7M2QX", "whitespace from a chat bubble");
  assert.equal(codeFromLink("https://videl-studio.vercel.app/play/K7M2QX"), "K7M2QX");
  assert.equal(codeFromLink("https://videl-studio.vercel.app/?tab=arcade&room=K7M2QX"), "K7M2QX");
  assert.equal(codeFromLink("https://t.me/Videl0Bot?startapp=K7M2QX"), "K7M2QX");
  assert.equal(codeFromLink("https://example.com/play/K7M2QX"), "K7M2QX", "any host");
  assert.equal(codeFromLink("open the arcade"), "", "a sentence is not a room");
  assert.equal(codeFromLink("HELLO"), "HELLO", "a four-letter word is still a code shape");
  assert.equal(codeFromLink(""), "");

  // The canon of an invite: a real page, and Telegram's own door.
  assert.equal(inviteLink("k7m2qx", "https://videl.example/"), "https://videl.example/play/K7M2QX");
  assert.equal(inviteLink("K7M2QX"), "/play/K7M2QX");
  assert.equal(telegramInvite("k7m2qx"), "https://t.me/Videl0Bot?startapp=K7M2QX");
});

test("checkers chains are only the ones the server already offered", async () => {
  const { chainLanding, chainsFrom, isDarkSquare, checkerSeat, isCrowned, seatColour } =
    await import("../src/lib/arcade");
  const legal = [
    { from: 21, to: [35, 49], via: [28, 42], captures: 2 },
    { from: 21, to: [30], via: [25], captures: 1 },
    { from: 19, to: [28], via: null, captures: 0 },
  ];
  assert.equal(chainsFrom(legal, 21).length, 2);
  assert.equal(chainsFrom(legal, 17).length, 0, "a piece with no move offers nothing");
  assert.deepEqual(chainLanding(legal, 21, 49)?.to, [35, 49], "a tap sends the whole chain");
  assert.equal(chainLanding(legal, 21, 42), undefined, "an intermediate square is not a landing");
  assert.equal(chainLanding(legal, 21, 7), undefined, "an invented destination is refused");

  // The board itself: play happens on the dark squares, on row*8+col.
  assert.equal(isDarkSquare(0), false);
  assert.equal(isDarkSquare(1), true);
  assert.equal(isDarkSquare(10), true);
  assert.equal(isDarkSquare(16), false, "row 2, column 0 is a light square");
  assert.equal(isDarkSquare(8), true);
  assert.equal(checkerSeat(0), null);
  assert.equal(checkerSeat(1), 0);
  assert.equal(checkerSeat(2), 1);
  assert.equal(checkerSeat(4), 1);
  assert.equal(isCrowned(3), true);
  assert.equal(isCrowned(2), false);

  // Checkers plays bone against ink, not the ludo palette.
  assert.equal(seatColour("checkers", 0), "#f4e4bf");
  assert.equal(seatColour("checkers", 1), "#3b4266");
  assert.equal(seatColour("ludo", 0), "#ef4444");
});

test("every table has its own art, and every game has its terms", async () => {
  const { GAME_ART, GAME_ICON, GAME_TERMS, GAME_THEME } = await import("../src/lib/arcade");
  const games = Object.keys(GAME_THEME);
  assert.deepEqual(games.sort(), ["checkers", "connect4", "ludo", "reversi", "tictactoe"]);
  for (const game of games) {
    assert.match(GAME_ART[game], /^\/arcade\/[a-z0-9]+\.jpg$/, `${game} has local art`);
    assert.ok(GAME_ICON[game], `${game} has a glyph for when the art does not load`);
    assert.ok(GAME_TERMS[game]?.length, `${game} explains its own rules`);
  }
});

test("the invite page renders the code before anyone signs in", async () => {
  const { InviteRoom } = await import("../src/components/arcade/InviteRoom");
  const html = render(createElement(InviteRoom, { code: "K7M2QX" }));
  assert.match(html, /A chair is waiting/);
  for (const character of ["K", "7", "M", "2", "Q", "X"]) {
    assert.match(html, new RegExp(`>${character}<`), "the code is readable without a session");
  }
  assert.match(html, /https:\/\/t\.me\/Videl0Bot\?startapp=K7M2QX/);
  assert.match(html, /Copy link/);
  assert.ok(!/undefined/.test(html), "no undefined leaks into the invite");
});

test("the checkers board draws every square and never offers a bad tap", async () => {
  const { CheckersBoard } = await import("../src/components/studio/boards/CheckersBoard");
  const board = new Array(64).fill(0);
  board[17] = 1; // bone man
  board[26] = 2; // ink man
  board[56] = 3; // bone king on the back row
  const room = {
    code: "K7M2QX",
    game: "checkers",
    game_name: "Checkers",
    status: "playing",
    turn: 0,
    seat_count: 2,
    version: 7,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    you: { seat: 0, is_host: true, member: true },
    legal: [{ from: 17, to: [30], via: [26], captures: 1 }],
    state: { board, turn: 0, winner: null, last: { from: 56, to: 49, captures: 0, crowned: false } },
  } as never;
  const html = render(
    createElement(CheckersBoard, { room, myTurn: true, busy: false, onMove: () => {} }),
  );
  assert.equal((html.match(/role="gridcell"/g) || []).length, 64, "sixty-four squares");
  assert.equal((html.match(/class="checkers-piece"/g) || []).length, 3, "three pieces on the board");
  assert.match(html, /data-king="true"/, "the crowned piece is drawn as a king");
  assert.match(html, /A capture is on the board/, "a forced capture is announced, not hidden");
  assert.ok(!/undefined/.test(html), "no undefined leaks into the board");
});
