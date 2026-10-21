"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Clock,
  Gamepad2,
  Globe2,
  Loader2,
  Lock,
  LogIn,
  Plus,
  RefreshCw,
  Trophy,
  Users,
} from "lucide-react";
import { usePlayerSession } from "@/lib/player";
import {
  GAME_ICON,
  type GameInfo,
  type Lobby,
  type PlayerRef,
  type RoomRow,
} from "@/lib/arcade";
import { RoomView } from "../RoomView";
import { Callout, PageHeader } from "../ui";

/**
 * The public arcade.
 *
 * Signing in is Telegram only: the room must know who is moving so it can
 * refuse a move from the wrong account. A visitor who has not opened the panel
 * from inside Telegram sees one clear explanation instead of a dead board.
 */
export default function Arcade() {
  const { player, error: signInError, signIn } = usePlayerSession();
  const [lobby, setLobby] = useState<Lobby | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [game, setGame] = useState("connect4");
  const [seats, setSeats] = useState(2);
  const [visibility, setVisibility] = useState<"private" | "public">("private");
  const [room, setRoom] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/arcade", { cache: "no-store" });
      if (response.status === 401) {
        setLobby(null);
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || "The arcade is unavailable.");
      setLobby(data as Lobby);
      setError("");
    } catch (failure) {
      setError((failure as Error).message);
    }
  }, []);

  useEffect(() => {
    if (!player) return;
    void load();
    const poll = setInterval(() => {
      if (document.visibilityState === "visible" && !room) void load();
    }, 12000);
    return () => clearInterval(poll);
  }, [load, player, room]);

  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("room");
    if (wanted && /^[A-Z2-9]{4,8}$/i.test(wanted)) setRoom(wanted.toUpperCase());
  }, []);

  const openRoom = useCallback((value: string) => {
    setRoom(value.toUpperCase());
    const url = new URL(window.location.href);
    url.searchParams.set("room", value.toUpperCase());
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
  }, []);

  const closeRoom = useCallback(() => {
    setRoom(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("room");
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
    void load();
  }, [load]);

  async function call(path: string, body: unknown) {
    setBusy(true);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || "The arcade refused that request.");
      setError("");
      return data;
    } catch (failure) {
      setError((failure as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  if (!player) {
    return (
      <main className="ios-page">
        <PageHeader
          eyebrow={
            <>
              <Gamepad2 size={13} aria-hidden /> Arcade
            </>
          }
          title="Play together, right here"
          subtitle="Connect Four, Reversi, Tic-tac-toe and Ludo for up to four. Rooms are shared by a six-character code; every move is checked on the server."
        />
        <div className="ios-card mt-6 max-w-xl p-5">
          <p className="text-sm text-indigo-100/70">
            The arcade uses your Telegram account, so nobody can move for you. Open Videl from
            inside Telegram, then come back to this tab.
          </p>
          <button onClick={() => void signIn()} disabled={busy} className="ios-btn ios-btn-primary mt-4">
            <LogIn size={16} aria-hidden /> Continue with Telegram
          </button>
          {signInError ? (
            <p className="mt-3 text-xs text-amber-200/80" role="status">
              {signInError}
            </p>
          ) : null}
        </div>
        <Callout tone="info" title="No downloads">
          Your board lives on the bot server. Close the panel, reopen the link, and the game is
          exactly where you left it — including your turn clock.
        </Callout>
      </main>
    );
  }

  if (room) {
    return (
      <main className="ios-page">
        <RoomView
          code={room}
          player={{ id: player.id, name: player.name } as PlayerRef}
          lobby={lobby}
          onBack={closeRoom}
          onChanged={() => void load()}
        />
      </main>
    );
  }

  const games: GameInfo[] = lobby?.games || FALLBACK_GAMES;
  const chosen = games.find((entry) => entry.key === game) || games[0];

  return (
    <main className="ios-page">
      <PageHeader
        eyebrow={
          <>
            <Gamepad2 size={13} aria-hidden /> Arcade
          </>
        }
        title="Pick a game and share the code"
        subtitle={`Signed in as ${player.name}. Rooms are private by default; a public room appears in the lobby below.`}
        actions={
          <button onClick={() => void load()} disabled={busy} className="ios-btn ios-btn-glass">
            <RefreshCw size={16} aria-hidden /> Refresh
          </button>
        }
      />

      {error ? (
        <Callout tone="warn" title="Arcade notice">
          {error}
        </Callout>
      ) : null}

      <section className="ios-card mt-5 p-4" aria-label="Start a game">
        <p className="ios-caps text-[11px] text-indigo-100/50">New room</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {games.map((entry) => (
            <button
              key={entry.key}
              onClick={() => {
                setGame(entry.key);
                setSeats(entry.seats[0]);
              }}
              aria-pressed={game === entry.key}
              className={`rounded-2xl border p-3 text-left transition ${
                game === entry.key
                  ? "border-indigo-300/50 bg-indigo-400/15"
                  : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <span className="text-2xl" aria-hidden>
                {GAME_ICON[entry.key] || "🎮"}
              </span>
              <span className="mt-1 block text-sm font-medium">{entry.name}</span>
              <span className="mt-0.5 block text-[11px] leading-4 text-indigo-100/50">
                {entry.seats.join("–")} players · {entry.turn_seconds}s a turn
              </span>
              <span className="mt-1 block text-[11px] leading-4 text-indigo-100/40">
                {entry.summary}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {chosen && chosen.seats.length > 1
            ? chosen.seats.map((count) => (
                <button
                  key={count}
                  onClick={() => setSeats(count)}
                  aria-pressed={seats === count}
                  className={`rounded-xl px-3 py-1.5 text-xs ${
                    seats === count
                      ? "bg-indigo-400/25 text-indigo-50"
                      : "bg-white/[0.05] text-indigo-100/60"
                  }`}
                >
                  {count} players
                </button>
              ))
            : null}
          <span className="mx-1 h-5 w-px bg-white/10" aria-hidden />
          <button
            onClick={() => setVisibility("private")}
            aria-pressed={visibility === "private"}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs ${
              visibility === "private" ? "bg-indigo-400/25 text-indigo-50" : "bg-white/[0.05] text-indigo-100/60"
            }`}
          >
            <Lock size={13} aria-hidden /> Private
          </button>
          <button
            onClick={() => setVisibility("public")}
            aria-pressed={visibility === "public"}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs ${
              visibility === "public" ? "bg-indigo-400/25 text-indigo-50" : "bg-white/[0.05] text-indigo-100/60"
            }`}
          >
            <Globe2 size={13} aria-hidden /> Public
          </button>
          <button
            onClick={async () => {
              const data = await call("/api/arcade", {
                game,
                seats: chosen?.seats.length === 1 ? chosen.seats[0] : seats,
                visibility,
              });
              if (data?.room?.code) openRoom(data.room.code);
            }}
            disabled={busy}
            className="ios-btn ios-btn-primary ml-auto"
          >
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Plus size={16} aria-hidden />}
            Create room
          </button>
        </div>
      </section>

      <section className="ios-card mt-4 p-4" aria-label="Join with a code">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={async (event) => {
            event.preventDefault();
            const value = code.trim().toUpperCase();
            if (!value) return;
            const data = await call("/api/arcade/join", { code: value });
            if (data?.room?.code) {
              setCode("");
              openRoom(data.room.code);
            }
          }}
        >
          <label className="min-w-0 flex-1">
            <span className="ios-caps block text-[11px] text-indigo-100/50">Have a code?</span>
            <input
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase().slice(0, 8))}
              placeholder="K7M2QX"
              maxLength={8}
              className="mono mt-1 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm tracking-[0.35em] outline-none focus:border-indigo-300/40"
              aria-label="Room code"
            />
          </label>
          <button type="submit" disabled={busy || code.trim().length < 4} className="ios-btn ios-btn-glass">
            <LogIn size={16} aria-hidden /> Join room
          </button>
        </form>
      </section>

      {lobby ? (
        <>
          <Rooms title="Your rooms" rows={lobby.mine} empty="You have no open rooms." onOpen={openRoom} />
          <Rooms title="Open to everyone" rows={lobby.public} empty="No public rooms right now." onOpen={openRoom} />
          <Leaderboards lobby={lobby} me={player.id} />
        </>
      ) : (
        <p className="mt-6 flex items-center gap-2 text-sm text-indigo-100/45">
          <Loader2 size={16} className="animate-spin" aria-hidden /> Loading the lobby…
        </p>
      )}
    </main>
  );
}

function Rooms({
  title,
  rows,
  empty,
  onOpen,
}: {
  title: string;
  rows: RoomRow[];
  empty: string;
  onOpen: (code: string) => void;
}) {
  return (
    <section className="ios-card mt-4 p-4" aria-label={title}>
      <p className="ios-caps flex items-center gap-2 text-[11px] text-indigo-100/50">
        <Users size={13} aria-hidden /> {title}
      </p>
      {rows.length === 0 ? (
        <p className="mt-2 text-xs text-indigo-100/35">{empty}</p>
      ) : (
        <ul className="mt-2 divide-y divide-white/5">
          {rows.map((row) => (
            <li key={row.code} className="flex flex-wrap items-center gap-2 py-2">
              <span className="text-lg" aria-hidden>
                {GAME_ICON[row.game] || "🎮"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm">
                  {row.game_name} <span className="mono text-xs text-indigo-100/45">{row.code}</span>
                </span>
                <span className="block truncate text-[11px] text-indigo-100/45">
                  {row.players.join(", ") || "Empty"} · {row.status}
                  {row.visibility === "private" ? " · private" : " · public"}
                </span>
              </span>
              <span className="mono flex items-center gap-1 text-[11px] text-indigo-100/40">
                <Clock size={12} aria-hidden /> {row.turn_seconds}s
              </span>
              <button onClick={() => onOpen(row.code)} className="ios-btn ios-btn-glass px-3 py-1.5 text-xs">
                Open <ArrowRight size={13} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Leaderboards({ lobby, me }: { lobby: Lobby; me: number }) {
  const boards = lobby.leaderboards || {};
  if (!Object.keys(boards).length) return null;
  return (
    <section className="ios-card mt-4 p-4" aria-label="Leaderboards">
      <p className="ios-caps flex items-center gap-2 text-[11px] text-indigo-100/50">
        <Trophy size={13} aria-hidden /> Rated games
      </p>
      <p className="mt-1 text-[11px] text-indigo-100/35">
        Elo moves only in two-player rooms of Connect Four, Reversi and Tic-tac-toe.
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-3">
        {Object.entries(boards).map(([game, rows]) => (
          <div key={game}>
            <p className="text-xs font-medium text-indigo-100/70">
              {GAME_ICON[game] || "🎮"} {game}
            </p>
            <ol className="mt-1 space-y-0.5 text-[11px] text-indigo-100/55">
              {rows.slice(0, 5).map((row, index) => (
                <li key={row.id} className={`flex justify-between gap-2 ${row.id === me ? "text-indigo-100" : ""}`}>
                  <span className="truncate">
                    {index + 1}. {row.name}
                  </span>
                  <span className="mono">{row.rating}</span>
                </li>
              ))}
              {rows.length === 0 ? <li className="text-indigo-100/30">No rated games yet.</li> : null}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}

const FALLBACK_GAMES: GameInfo[] = [
  { key: "connect4", name: "Connect Four", seats: [2], turn_seconds: 60, summary: "Line up four discs." },
  { key: "ludo", name: "Ludo", seats: [2, 3, 4], turn_seconds: 45, summary: "Race four tokens home." },
  { key: "reversi", name: "Reversi", seats: [2], turn_seconds: 90, summary: "Flank and flip." },
  { key: "tictactoe", name: "Tic-tac-toe", seats: [2], turn_seconds: 45, summary: "Three in a row." },
];
