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
  for (const name of ["Chess", "Ludo", "Checkers", "Five in a Row", "Connect Four", "Reversi", "Tic-tac-toe"]) {
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

test("group manager is available to non-owners but its separate Telegram session gates controls", async () => {
  const { canOpenSection } = await import("../src/lib/access");
  assert.equal(canOpenSection("arcade", null), true);
  assert.equal(canOpenSection("groups", null), true);
  assert.equal(canOpenSection("automation", null), false);
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
  assert.deepEqual(games.sort(), ["checkers", "chess", "chinese", "connect4", "dots", "gomoku", "ludo", "reversi", "tictactoe", "yacht"]);
  for (const game of games) {
    assert.match(GAME_ART[game], /^\/arcade\/[a-z0-9]+\.jpg$/, `${game} has local art`);
    assert.ok(GAME_ICON[game], `${game} has a glyph for when the art does not load`);
    assert.ok(GAME_TERMS[game]?.length, `${game} explains its own rules`);
  }
});

test("surprise-me picks a different playable table and one of its valid seat counts", async () => {
  const { randomGameChoice } = await import("../src/lib/arcade");
  const games = [
    { key: "solo", name: "Solo", seats: [1], turn_seconds: 30, summary: "No" },
    { key: "chess", name: "Chess", seats: [2], turn_seconds: 180, summary: "Mate" },
    { key: "ludo", name: "Ludo", seats: [2, 3, 4], turn_seconds: 45, summary: "Race" },
  ];
  const choice = randomGameChoice(games, "ludo", () => 0.999999);
  assert.equal(choice?.game.key, "chess", "does not repeat the current game when another is available");
  assert.equal(choice?.seats, 2, "single-seat-count games stay valid");
  assert.equal(randomGameChoice([], "ludo"), null);
  assert.equal(randomGameChoice(games.slice(0, 1), "solo"), null, "unsupported seat counts are ignored");
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

test("chess taps can only send a move the server listed", async () => {
  const { movesFrom, moveTo, ownsSquare, PIECE_NAME } = await import("../src/lib/arcade");
  const legal = [
    { from: 52, to: 36, flags: "double" },
    { from: 62, to: 45, flags: "" },
    { from: 8, to: 0, flags: "promotion", promote: "q" },
    { from: 8, to: 0, flags: "promotion", promote: "n" },
  ];
  assert.equal(movesFrom(legal, 52).length, 1);
  assert.equal(movesFrom(legal, 60).length, 0, "a piece with no move offers nothing");
  assert.equal(moveTo(legal, 62, 45)?.flags, "");
  assert.equal(moveTo(legal, 62, 44), undefined, "an invented square is refused");
  assert.equal(movesFrom(legal, 8).length, 2, "a promotion offers one move per piece");

  const board = "rnbqkbnrpppppppp".padEnd(64, ".").split("");
  board[60] = "K";
  assert.equal(ownsSquare(board, 60, 0), true);
  assert.equal(ownsSquare(board, 4, 0), false, "the onyx king is not mine");
  assert.equal(ownsSquare(board, 4, 1), true);
  assert.equal(ownsSquare(board, 20, 0), false);
  assert.equal(ownsSquare(board, 20, null), false);
  assert.equal(PIECE_NAME.n, "knight");
});

test("the chess board draws pieces, not glyphs, and marks a check", async () => {
  const { ChessBoard } = await import("../src/components/studio/boards/ChessBoard");
  const board = "rnbqkbnrpppppppp".padEnd(64, ".").split("");
  board[60] = "K";
  board[52] = "R";
  const room = {
    code: "K7M2QX",
    game: "chess",
    game_name: "Chess",
    status: "playing",
    turn: 0,
    seat_count: 2,
    version: 3,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    you: { seat: 0, is_host: true, member: true },
    legal: [{ from: 52, to: 44, flags: "" }],
    state: { board, turn: 0, winner: null, check: true, last: { from: 52, to: 44, san: "Re3" } },
  } as never;
  const html = render(createElement(ChessBoard, { room, myTurn: true, busy: false, onMove: () => {} }));
  assert.equal((html.match(/role="gridcell"/g) || []).length, 64);
  assert.match(html, /class="chess-alert">Check/);
  assert.match(html, /<svg viewBox="0 0 24 24"/, "pieces are drawn, so no emoji font decides the game");
  assert.ok(!/undefined/.test(html), "no undefined leaks into the board");
});

test("a microphone refusal becomes a sentence, not a stuck spinner", async () => {
  const { voiceFailure, canVoice } = await import("../src/lib/voice");
  const denied = voiceFailure({ name: "NotAllowedError" });
  assert.equal(denied.status, "blocked");
  assert.match(denied.error, /microphone/i);
  assert.match(denied.error, /voice notes/i, "the fallback is named, not implied");
  assert.equal(voiceFailure({ name: "NotFoundError" }).status, "unsupported");
  assert.match(voiceFailure({ name: "NotReadableError" }).error, /another app/i);
  assert.equal(voiceFailure(new Error("boom")).status, "blocked");
  // No window in this server-rendered test: the dock must say so, not throw.
  assert.equal(canVoice(), false);
});

test("the voice dock refuses to promise what a silent webview cannot do", async () => {
  const { VoiceDock } = await import("../src/components/studio/boards/VoiceDock");
  const room = {
    code: "K7M2QX",
    status: "playing",
    seats: [{ user: 1, name: "Ada", seat: 0, online: true }],
    you: { seat: 0, member: true },
  };
  const html = render(
    createElement(VoiceDock, {
      room,
      seat: 0,
      events: [],
      send: async () => null,
      onSpeaking: () => {},
      muted: true,
      onMute: () => {},
    }),
  );
  assert.match(html, /cannot carry live voice/i);
  assert.ok(!/undefined/.test(html));
});

test("the post flow names its four stages and never claims a done step", async () => {
  const { PostFlow } = await import("../src/components/studio/PostFlow");
  const html = render(
    createElement(PostFlow, {
      characters: 0,
      limit: 4096,
      hasImage: false,
      buttons: 0,
      canPublish: false,
    }),
  );
  for (const stage of ["Write", "Design", "Preview", "Queue"]) {
    assert.match(html, new RegExp(stage), `the rail names ${stage}`);
  }
  assert.match(html, /0<i>\/4096<\/i>/, "the counter starts honest");
  assert.match(html, /data-state="next"/, "the first unfinished stage is marked");
  assert.ok(!/undefined/.test(html));
});

test("a draw offer shows the answer, not another offer", async () => {
  const { TableActions } = await import("../src/components/studio/boards/TableActions");
  const room = {
    code: "K7M2QX",
    game: "chess",
    status: "playing",
    seat_count: 2,
    turn: 0,
    draw_offer: 1,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    you: { seat: 0, member: true },
  } as never;
  const html = render(
    createElement(TableActions, { room, busy: false, send: async () => ({}) }),
  );
  assert.match(html, /Grace offers a draw/);
  assert.match(html, /Accept/);
  assert.match(html, /Keep playing/);
  assert.ok(!/Offer a draw/.test(html), "the offer is already on the table");
});

test("resigning asks in place and four-seat tables never see the button", async () => {
  const { TableActions } = await import("../src/components/studio/boards/TableActions");
  const base = {
    code: "K7M2QX",
    game: "chess",
    status: "playing",
    seat_count: 2,
    turn: 0,
    draw_offer: null,
    seats: [{ user: 1, name: "Ada", seat: 0, online: true }],
    you: { seat: 0, member: true },
  };
  const html = render(createElement(TableActions, { room: base as never, busy: false, send: async () => ({}) }));
  assert.match(html, /Offer a draw/);
  assert.match(html, /Resign/);
  assert.ok(!/Give the game away/.test(html), "the question is not asked before it is needed");

  const ludo = { ...base, game: "ludo", seat_count: 4, you: { seat: 0, member: true } };
  assert.equal(render(createElement(TableActions, { room: ludo as never, busy: false, send: async () => ({}) })), "");
});

test("a finished game says how it finished", async () => {
  const { TableActions } = await import("../src/components/studio/boards/TableActions");
  const room = {
    code: "K7M2QX",
    game: "chess",
    status: "done",
    seat_count: 2,
    winner: 0,
    end_reason: "resign",
    draw_offer: null,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    you: { seat: 0, member: true },
  } as never;
  const html = render(createElement(TableActions, { room, busy: false, send: async () => ({}) }));
  assert.match(html, /Grace resigned/);
});

test("voice reach is stated, not implied", async () => {
  const { VOICE_REACH } = await import("../src/lib/voice");
  assert.match(VOICE_REACH, /peer to peer/i);
  assert.match(VOICE_REACH, /mobile networks/i);
});

test("the invite page shows every plate the arcade advertises", async () => {
  const { GAME_ART } = await import("../src/lib/arcade");
  const source = await import("node:fs/promises").then((fs) =>
    fs.readFile(new URL("../src/components/arcade/InviteRoom.tsx", import.meta.url), "utf8"),
  );
  for (const game of Object.keys(GAME_ART)) {
    assert.ok(
      source.includes(`"${game}"`),
      `the invite mosaic is missing ${game}; a seven-board arcade cannot advertise five`,
    );
  }
});

test("a result card picks its artwork from the player's outcome, not the room's", async () => {
  const { ResultOverlay } = await import("../src/components/studio/boards/ResultOverlay");
  const base = {
    code: "K7M2QX",
    game: "chess",
    status: "done",
    seat_count: 2,
    draw_offer: null,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    state: { log: ["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"] },
  };
  const render_for = (winner: number | "draw", seat: number, end_reason: string) =>
    render(
      createElement(ResultOverlay, {
        room: { ...base, winner, end_reason, you: { seat, is_host: seat === 0, member: true } } as never,
        busy: false,
        send: async () => ({}),
        onBack: () => {},
        onShare: () => {},
      }),
    );

  const lost = render_for(1, 0, "played");
  assert.match(lost, /data-outcome="lose"/);
  assert.match(lost, /Grace wins/);
  assert.match(lost, /results\/lose\.jpg/, "a loss gets its own plate");
  assert.match(lost, /Qxf7#/, "the scoresheet comes with the verdict");

  const won = render_for(0, 0, "resign");
  assert.match(won, /data-outcome="win"/);
  assert.match(won, /results\/win\.jpg/);
  assert.match(won, /result-confetti/, "winning throws confetti");

  const drawn = render_for("draw", 1, "agreement");
  assert.match(drawn, /data-outcome="draw"/);
  assert.match(drawn, /A draw/);
  assert.match(drawn, /results\/draw\.jpg/);
  assert.ok(!/result-confetti/.test(drawn), "a draw is not a party");
});

test("the result card never promises a rematch to a spectator", async () => {
  const { ResultOverlay } = await import("../src/components/studio/boards/ResultOverlay");
  const html = render(
    createElement(ResultOverlay, {
      room: {
        code: "K7M2QX",
        game: "chess",
        status: "done",
        winner: 0,
        seat_count: 2,
        seats: [{ user: 1, name: "Ada", seat: 0, online: true }],
        you: { seat: null, is_host: false, member: false },
        state: {},
      } as never,
      busy: false,
      send: async () => ({}),
      onBack: () => {},
      onShare: () => {},
    }),
  );
  assert.match(html, /The host can start a rematch/);
  assert.ok(!/>Rematch</.test(html), "a spectator cannot press a button that will fail");
});

test("the arcade's audio maps a room change to exactly one cue", async () => {
  const { cueFor, soundOn, setSoundOn } = await import("../src/lib/audio");
  const base = { status: "playing", you: { seat: 0 }, state: {} };
  assert.equal(cueFor({ ...base, state: { last: { capture: false } } }), "move");
  assert.equal(cueFor({ ...base, state: { last: { capture: true } } }), "capture");
  assert.equal(cueFor({ ...base, state: { last: { check: true } } }), "check");
  assert.equal(cueFor({ ...base, state: {} }), null, "nothing to hear on a fresh board");
  assert.equal(cueFor({ ...base, status: "done", winner: "draw", state: {} }), "lose");
  assert.equal(cueFor({ ...base, status: "done", winner: 0, state: {} }), "win");
  assert.equal(cueFor({ ...base, status: "done", winner: 1, state: {} }), "lose");
  // Server-rendered: no localStorage, so the default has to be sound on.
  assert.equal(soundOn(), true);
  assert.equal(setSoundOn(true), undefined, "a missing storage must not throw");
});

test("chess prints a scoresheet, a flip button and a starting cursor", async () => {
  const { ChessBoard } = await import("../src/components/studio/boards/ChessBoard");
  const board = "rnbqkbnrpppppppp".padEnd(64, ".").split("");
  const room = {
    code: "K7M2QX",
    game: "chess",
    game_name: "Chess",
    status: "playing",
    turn: 0,
    seat_count: 2,
    version: 4,
    seats: [
      { user: 1, name: "Ada", seat: 0, online: true },
      { user: 2, name: "Grace", seat: 1, online: true },
    ],
    you: { seat: 0, is_host: true, member: true },
    legal: [{ from: 52, to: 36, flags: "double" }],
    state: { board, turn: 0, winner: null, check: false, log: ["e4", "e5"] },
  } as never;
  const html = render(createElement(ChessBoard, { room, myTurn: true, busy: false, onMove: () => {} }));
  assert.match(html, /chess-log/);
  assert.match(html, /e4/);
  assert.match(html, /Flip/);
  assert.match(html, /data-cursor="true"/, "the keyboard cursor starts on the board");
  assert.equal((html.match(/role="gridcell"/g) || []).length, 64);
});

test("a voice note is a player in the feed, not a raw payload", async () => {
  const { VoiceClip, VoiceNote } = await import("../src/components/studio/boards/VoiceNote");
  const clip = render(createElement(VoiceClip, { id: "abcDEF123456", seconds: 6.4, mine: true }));
  assert.match(clip, /Voice note · 6\.4s/);
  assert.ok(!/undefined/.test(clip));

  const recorder = render(createElement(VoiceNote, { onSend: async () => ({}) }));
  assert.match(recorder, /Leave a voice note/);
  assert.match(recorder, /data-state="idle"/);
});

test("every game the arcade offers has rules a player can read", async () => {
  const { GAME_TERMS, GAME_ART } = await import("../src/lib/arcade");
  for (const game of Object.keys(GAME_ART)) {
    const terms = GAME_TERMS[game];
    assert.ok(Array.isArray(terms) && terms.length >= 2, `${game} needs its own rules`);
    for (const line of terms) assert.ok(line.length > 20, `${game} has a stub rule`);
  }
});

test("the three new multiplayer tables have board handlers and original local art", async () => {
  const { GAME_ART, GAME_TERMS } = await import("../src/lib/arcade");
  const { ChineseCheckersBoard } = await import("../src/components/studio/boards/ChineseCheckersBoard");
  const { DotsAndBoxesBoard } = await import("../src/components/studio/boards/DotsAndBoxesBoard");
  const { YachtBoard } = await import("../src/components/studio/boards/YachtBoard");
  assert.match(GAME_ART.chinese, /chinese/);
  assert.match(GAME_ART.dots, /dots/);
  assert.match(GAME_ART.yacht, /yacht/);
  assert.ok(GAME_TERMS.chinese.length >= 2);
  assert.ok(GAME_TERMS.dots.length >= 2);
  assert.ok(GAME_TERMS.yacht.length >= 2);
  assert.equal(typeof ChineseCheckersBoard, "function");
  assert.equal(typeof DotsAndBoxesBoard, "function");
  assert.equal(typeof YachtBoard, "function");
});

test("seat profiles load Telegram avatars through our player API", async () => {
  const { PlayerProfile } = await import("../src/components/studio/boards/PlayerProfile");
  const html = render(createElement(PlayerProfile, { id: 42, name: "Ada", game: "chinese" }));
  assert.match(html, /View Ada&#x27;s player profile/);
  assert.match(html, /api\/arcade\/avatar\/42/);
});

test("the post rail reports a save state it can actually know", async () => {
  const { PostFlow } = await import("../src/components/studio/PostFlow");
  const html = render(
    createElement(PostFlow, {
      characters: 96,
      limit: 1024,
      hasImage: true,
      buttons: 1,
      canPublish: true,
      words: 18,
      save: { state: "saved", note: "saved 4s ago" },
    }),
  );
  assert.match(html, /18 words/);
  assert.match(html, /saved 4s ago/);
  assert.match(html, /data-state="saved"/);
  assert.ok(!/scheduling is available/.test(html), "the rail says the useful thing, not the old filler");
});
