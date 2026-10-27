export type Seat = {
  user: number;
  name: string;
  seat: number;
  online: boolean;
};

export type Room = {
  code: string;
  game: string;
  game_name: string;
  visibility: "private" | "public";
  status: "open" | "playing" | "done" | "abandoned";
  host: number;
  seat_count: number;
  seats: Seat[];
  turn: number;
  you: { seat: number | null; is_host: boolean; member: boolean };
  state: Record<string, unknown>;
  legal: Record<string, unknown>[];
  deadline_at: string | null;
  server_time: string;
  version: number;
  seq: number;
  winner: number | "draw" | null;
  chat_id: number | null;
  title: string;
  turn_seconds: number;
  end_reason?: "played" | "forfeit" | "resign" | "agreement" | string | null;
  draw_offer?: number | null;
  /** User ids currently in the voice call; a heartbeat decides membership. */
  voice?: number[];
};

export type RoomEvent = {
  seq: number;
  kind: string;
  user: number | null;
  text: string;
  at: string | null;
};

export type RoomRow = {
  code: string;
  game: string;
  game_name: string;
  status: string;
  visibility: string;
  seat_count: number;
  players: string[];
  host: number;
  updated_at: string | null;
  turn_seconds: number;
};

export type GameInfo = {
  key: string;
  name: string;
  seats: number[];
  turn_seconds: number;
  summary: string;
};

export function randomGameChoice(
  games: GameInfo[],
  currentKey: string,
  random: () => number = Math.random,
): { game: GameInfo; seats: number } | null {
  const playable = games.filter((game) =>
    game.seats.some((count) => Number.isInteger(count) && count >= 2 && count <= 6),
  );
  if (!playable.length) return null;
  const different = playable.filter((game) => game.key !== currentKey);
  const pool = different.length ? different : playable;
  const draw = Number(random());
  const fraction = Number.isFinite(draw) ? Math.min(0.999999, Math.max(0, draw)) : 0;
  const game = pool[Math.floor(fraction * pool.length)];
  const seatOptions = game.seats.filter((count) => Number.isInteger(count) && count >= 2 && count <= 6);
  const seatDraw = Number(random());
  const seatFraction = Number.isFinite(seatDraw) ? Math.min(0.999999, Math.max(0, seatDraw)) : 0;
  const seats = seatOptions[Math.floor(seatFraction * seatOptions.length)];
  return { game, seats };
}

export type PlayerRef = { id: number; name: string };

export type Stat = {
  wins: number;
  losses: number;
  draws: number;
  rating: number;
  games: number;
};

export type Lobby = {
  ok: boolean;
  games: GameInfo[];
  public: RoomRow[];
  mine: RoomRow[];
  me?: PlayerRef & { stats?: Record<string, Stat> };
  leaderboards?: Record<string, { id: number; name: string; rating: number; games: number }[]>;
};

export const GAME_ICON: Record<string, string> = {
  checkers: "♛",
  chess: "♞",
  connect4: "◍",
  gomoku: "⬤",
  reversi: "◐",
  tictactoe: "✕",
  ludo: "◈",
  chinese: "✦",
  dots: "⠿",
  yacht: "🎲",
};

/**
 * One piece of original art per table, drawn for this arcade and served from
 * /public/arcade. A card without its image still reads, because the accent
 * and the name carry it — the art is the invitation, not the information.
 */
export const GAME_ART: Record<string, string> = {
  checkers: "/arcade/checkers.jpg",
  chess: "/arcade/chess.jpg",
  connect4: "/arcade/connect4.jpg",
  gomoku: "/arcade/gomoku.jpg",
  reversi: "/arcade/reversi.jpg",
  tictactoe: "/arcade/tictactoe.jpg",
  ludo: "/arcade/ludo.jpg",
  chinese: "/arcade/chinese.jpg",
  dots: "/arcade/dots.jpg",
  yacht: "/arcade/yacht.jpg",
};

/** One accent per game, used by cards, rooms, chips and the board surface. */
export const GAME_THEME: Record<string, { accent: string; soft: string; tagline: string }> = {
  checkers: { accent: "#f5c451", soft: "rgba(245,196,81,0.20)", tagline: "Crown a man, own the board" },
  chess: { accent: "#c4b5fd", soft: "rgba(196,181,253,0.20)", tagline: "Mate in the endgame" },
  gomoku: { accent: "#5eead4", soft: "rgba(94,234,212,0.20)", tagline: "Five stones, one line" },
  connect4: { accent: "#fb7185", soft: "rgba(251,113,133,0.20)", tagline: "Drop, stack, connect" },
  ludo: { accent: "#a78bfa", soft: "rgba(167,139,250,0.20)", tagline: "Four tokens, one crown" },
  reversi: { accent: "#34d399", soft: "rgba(52,211,153,0.20)", tagline: "Flip the whole board" },
  tictactoe: { accent: "#60a5fa", soft: "rgba(96,165,250,0.20)", tagline: "Three moves is all it takes" },
  chinese: { accent: "#f0abfc", soft: "rgba(240,171,252,0.20)", tagline: "Hop the star, fill your far camp" },
  dots: { accent: "#fbbf24", soft: "rgba(251,191,36,0.20)", tagline: "One line can claim a box" },
  yacht: { accent: "#38bdf8", soft: "rgba(56,189,248,0.20)", tagline: "Five dice, thirteen chances" },
};

/** Terms someone actually needs to know one board and no manual. */
export const GAME_TERMS: Record<string, string[]> = {
  chess: [
    "A bishop on its own colour and a knight are the only pieces that may move on the first turn's outside files.",
    "Castling needs the king and rook untouched, an empty path and a king never in check.",
    "A pawn that reaches the last rank becomes any piece you choose.",
    "Checkmate wins; stalemate, the fifty-move rule and threefold repetition draw.",
  ],
  gomoku: [
    "Place a stone on any empty intersection; black moves first.",
    "Five in a row — across, down or either diagonal — wins.",
    "The board has 225 points; no stones are ever removed.",
  ],
  checkers: [
    "Captures are compulsory, and the longest chain is the only one allowed.",
    "A man crowned on the eighth row ends its move there.",
    "Kings fly the whole diagonal and may land anywhere past a captured piece.",
    "A side with no legal move loses.",
  ],
  connect4: [
    "Discs fall to the lowest free cell in a column.",
    "Four in a row wins — across, down or diagonally.",
  ],
  reversi: [
    "A move must bracket at least one rival disc; those discs flip.",
    "No legal move passes the turn; two passes end the game. Most discs wins.",
  ],
  tictactoe: [
    "Three in a row — across, down or diagonally — wins the round.",
    "A full board with no line is a draw; there is no perfect-play trap here.",
    "The turn clock is 45 seconds, so a stalling opponent forfeits quickly.",
  ],
  ludo: [
    "A six leaves the base and earns another roll.",
    "Three sixes in a row forfeit the turn.",
    "Landing on a rival sends it home — except on the eight safe squares.",
    "Tokens may share a square. First player home wins the table.",
  ],
  chinese: [
    "Move one peg to a neighbouring hole, or jump over a peg into the empty hole beyond it.",
    "Chain jumps may turn; stop at any empty landing along the chain.",
    "Fill all ten holes in the camp opposite your starting corner to win.",
    "Two, three, four or six players can take a seat at the star.",
  ],
  dots: [
    "Draw one horizontal or vertical line on your turn.",
    "The fourth side closes a box, scores it and gives you another line.",
    "When every line is drawn, the player with the most boxes wins.",
    "Tied box counts are a draw. The board is six by five boxes.",
  ],
  yacht: [
    "Roll five dice up to three times; tap a die to keep it between rolls.",
    "Write your final roll in one of thirteen score boxes. Each box is used once.",
    "A full house is 25, a small straight 30, a large straight 40 and five alike 50.",
    "At least 63 in the upper six boxes earns a 35-point bonus; highest total wins.",
  ],
};

export function themeOf(game: string) {
  return GAME_THEME[game] || { accent: "#818cf8", soft: "rgba(129,140,248,0.2)", tagline: "A quick game" };
}

export function initials(name: string): string {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** The colour that seat plays, which depends on the board it is sitting at. */
export function seatColour(game: string, seat: number): string {
  if (game === "checkers") return CHECKERS_COLOUR[seat] || CHECKERS_COLOUR[0];
  return SEAT_COLOUR[seat] || "#6366f1";
}

/** CSS variables that colour a token or an avatar without color-mix(). */
export function seatVars(seat: number): Record<string, string> {
  const base = SEAT_COLOUR[seat] || "#6366f1";
  const dark = SEAT_DARK[seat] || "#312e81";
  return { "--seat": base, "--seat-dark": dark, "--seat-light": "#ffffff" };
}

export function laneVars(seat: number): Record<string, string> {
  const base = SEAT_COLOUR[seat] || "#6366f1";
  return { "--lane": base, "--lane-soft": `${base}33` };
}

/** How much of this turn is left, for the conic clock. 0..1 */
export function turnFraction(deadline: string | null, total: number, now = Date.now()): number {
  if (!deadline || !total) return 0;
  const left = (Date.parse(deadline) - now) / 1000;
  if (!Number.isFinite(left)) return 0;
  return Math.max(0, Math.min(1, left / total));
}

export function playerName(room: Room, user: number | null): string {
  if (user === null) return "Videl";
  return room.seats.find((seat) => seat.user === user)?.name || `Player ${user}`;
}

export function seatFor(room: Room, user: number | null): Seat | undefined {
  return room.seats.find((seat) => seat.user === user);
}

export function isMyTurn(room: Room): boolean {
  return room.status === "playing" && room.you.seat !== null && room.turn === room.you.seat;
}

export function winnerText(room: Room): string {
  if (room.status !== "done") return "";
  if (room.winner === "draw") return "A draw.";
  if (typeof room.winner === "number") {
    const seat = room.seats.find((entry) => entry.seat === room.winner);
    return `${seat?.name || "Someone"} won.`;
  }
  return "The game finished.";
}

/** "42s" while it matters, "" once there is no clock. */
export function countdown(deadline: string | null, now = Date.now()): string {
  if (!deadline) return "";
  const left = Math.max(0, Date.parse(deadline) - now);
  if (!Number.isFinite(left)) return "";
  const seconds = Math.ceil(left / 1000);
  return seconds > 99 ? `${Math.ceil(seconds / 60)}m` : `${seconds}s`;
}

export function describeEvent(room: Room, event: RoomEvent): string {
  if (event.kind === "chat") return event.text;
  if (event.kind === "join") return event.text || "joined";
  if (event.kind === "move") return `${playerName(room, event.user)} ${event.text}`;
  return event.text;
}

/** The invite link opens a real page in a real browser, not a panel tab. */
export function inviteLink(code: string, origin = ""): string {
  return `${origin.replace(/\/+$/, "")}/play/${String(code).toUpperCase()}`;
}

/** Telegram's own door: tapping this opens the Mini App with the room seated. */
export function telegramInvite(code: string, bot = "videlapp"): string {
  return `https://t.me/${bot}?startapp=${String(code).toUpperCase()}`;
}

/**
 * A pasted invite is a link, a Telegram payload or a bare code. All three mean
 * the same thing, so the join field accepts all three instead of scolding.
 */
export function codeFromLink(value: string): string {
  const text = String(value || "").trim();
  if (!text) return "";
  const bare = text.toUpperCase();
  if (/^[A-Z2-9]{4,8}$/.test(bare)) return bare;
  const page = text.match(/\/play\/([A-Za-z2-9]{4,8})/i);
  if (page) return page[1].toUpperCase();
  const param = text.match(/[?&](?:room|startapp)=([A-Za-z2-9]{4,8})/i);
  if (param) return param[1].toUpperCase();
  return "";
}

/** A shareable sentence that survives being pasted into a group chat. */
export function inviteMessage(gameName: string, code: string, origin = ""): string {
  return `${gameName} on Videl — tap to take the other chair: ${inviteLink(code, origin)}`;
}

// ── Ludo geometry ───────────────────────────────────────────────────────────
/** The 52 ring squares clockwise from red's start, as [row, column]. */
export const LUDO_RING: [number, number][] = [
  [6, 1], [6, 2], [6, 3], [6, 4], [6, 5],
  [5, 6], [4, 6], [3, 6], [2, 6], [1, 6],
  [0, 6], [0, 7], [0, 8],
  [1, 8], [2, 8], [3, 8], [4, 8], [5, 8],
  [6, 9], [6, 10], [6, 11], [6, 12], [6, 13], [6, 14],
  [7, 14], [8, 14],
  [8, 13], [8, 12], [8, 11], [8, 10], [8, 9],
  [9, 8], [10, 8], [11, 8], [12, 8], [13, 8],
  [14, 8], [14, 7], [14, 6],
  [13, 6], [12, 6], [11, 6], [10, 6], [9, 6],
  [8, 5], [8, 4], [8, 3], [8, 2], [8, 1], [8, 0],
  [7, 0], [6, 0],
];

export const LUDO_SAFE = new Set([0, 8, 13, 21, 26, 34, 39, 47]);

export const LUDO_HOME: Record<number, [number, number][]> = {
  0: [[7, 1], [7, 2], [7, 3], [7, 4], [7, 5], [7, 6]],
  1: [[1, 7], [2, 7], [3, 7], [4, 7], [5, 7], [6, 7]],
  2: [[7, 13], [7, 12], [7, 11], [7, 10], [7, 9], [7, 8]],
  3: [[13, 7], [12, 7], [11, 7], [10, 7], [9, 7], [8, 7]],
};

export const LUDO_BASE: [number, number][] = [[1.4, 1.4], [1.4, 10.4], [10.4, 10.4], [10.4, 1.4]];
export const SEAT_COLOUR = ["#ef4444", "#22c55e", "#eab308", "#3b82f6", "#a855f7", "#f97316"];
/** Checkers plays bone against ink, the way a wooden board is actually set. */
export const CHECKERS_COLOUR = ["#f4e4bf", "#3b4266"];
export const SEAT_DARK = ["#7f1d1d", "#14532d", "#713f12", "#1e3a8a", "#581c87", "#7c2d12"];

export function colourOf(start: number): number {
  return Math.max(0, [0, 13, 26, 39].indexOf(start));
}

export type LudoCell = { row: number; col: number; kind: "ring" | "home" | "base" | "centre" };

/** Where one token sits on the 15×15 board. */
export function ludoTokenCell(
  start: number,
  progress: number,
  token: number,
): LudoCell {
  const colour = colourOf(start);
  if (progress === -1) {
    const [row, col] = LUDO_BASE[colour];
    const offset = [[0, 0], [0, 2.1], [2.1, 0], [2.1, 2.1]][token] || [0, 0];
    return { row: row + offset[0], col: col + offset[1], kind: "base" };
  }
  if (progress >= 57) return { row: 6.5, col: 6.5, kind: "centre" };
  if (progress >= 51) {
    const [row, col] = LUDO_HOME[colour][Math.min(5, progress - 51)];
    return { row, col, kind: "home" };
  }
  const [row, col] = LUDO_RING[(start + progress) % LUDO_RING.length];
  return { row, col, kind: "ring" };
}


// ── Checkers geometry ───────────────────────────────────────────────────────
/** One legal move the server offered: where from, and every landing in order. */
export type Chain = {
  from: number;
  to: number[];
  via: (number | null)[];
  captures: number;
};

/** The chains that start on one square. */
export function chainsFrom(legal: Record<string, unknown>[], square: number): Chain[] {
  return (legal as unknown as Chain[]).filter(
    (entry) => entry && Number(entry.from) === square && Array.isArray(entry.to),
  );
}

/** The exact chain that ends on `target`, so a tap sends what the server expects. */
export function chainLanding(legal: Record<string, unknown>[], from: number, target: number): Chain | undefined {
  return chainsFrom(legal, from).find(
    (entry) => Number(entry.to[entry.to.length - 1]) === target,
  );
}

/** Dark squares are the ones you can stand on. */
export function isDarkSquare(index: number): boolean {
  const row = Math.floor(index / 8);
  const col = index % 8;
  return (row + col) % 2 === 1;
}

/** Who owns a cell, as a seat index, or null. 1/2 men, 3/4 kings. */
export function checkerSeat(cell: number): number | null {
  if (cell === 1 || cell === 3) return 0;
  if (cell === 2 || cell === 4) return 1;
  return null;
}

export function isCrowned(cell: number): boolean {
  return cell === 3 || cell === 4;
}


// ── Chess geometry ──────────────────────────────────────────────────────────
/** A board square as row and column, for a flat 64-cell list. */
export function squareAt(index: number): { row: number; col: number } {
  return { row: Math.floor(index / 8), col: index % 8 };
}

/** All the legal moves starting from one square. */
export function movesFrom(legal: Record<string, unknown>[], square: number) {
  return legal.filter((entry) => Number(entry.from) === square);
}

/** The legal move that lands on a square, or undefined if the tap is invalid. */
export function moveTo(legal: Record<string, unknown>[], from: number, to: number) {
  return movesFrom(legal, from).find((entry) => Number(entry.to) === to);
}

/** Does this square hold a piece from the seat on move? */
export function ownsSquare(board: string[], square: number, seat: number | null): boolean {
  const piece = board[square];
  if (!piece || piece === "." || seat === null) return false;
  return seat === 0 ? piece === piece.toUpperCase() : piece === piece.toLowerCase();
}

/** A readable name for a piece, used in labels and the captured tray. */
export const PIECE_NAME: Record<string, string> = {
  p: "pawn", n: "knight", b: "bishop", r: "rook", q: "queen", k: "king",
};

// ── Gomoku geometry ─────────────────────────────────────────────────────────
export const GOMOKU_SIZE = 15;

export function gomokuPoint(cell: number): { x: number; y: number } {
  return { x: (cell % GOMOKU_SIZE) + 0.5, y: Math.floor(cell / GOMOKU_SIZE) + 0.5 };
}
