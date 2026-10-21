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

export type PlayerRef = { id: number; name: string };

export type Lobby = {
  ok: boolean;
  games: GameInfo[];
  public: RoomRow[];
  mine: RoomRow[];
  me?: PlayerRef & { stats?: Record<string, { wins: number; losses: number; draws: number; rating: number; games: number }> };
  leaderboards?: Record<string, { id: number; name: string; rating: number; games: number }[]>;
};

export const GAME_ICON: Record<string, string> = {
  connect4: "🔴",
  reversi: "⚫",
  tictactoe: "❌",
  ludo: "🎲",
};

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

/** The shareable room link keeps the panel and the room in one URL. */
export function roomLink(code: string, chatId?: number | null): string {
  const params = new URLSearchParams({ tab: "arcade", room: code });
  if (chatId) params.set("group", String(chatId));
  return `/?${params.toString()}`;
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
export const SEAT_COLOUR = ["#ef4444", "#22c55e", "#eab308", "#3b82f6"];
export const SEAT_DARK = ["#7f1d1d", "#14532d", "#713f12", "#1e3a8a"];

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
