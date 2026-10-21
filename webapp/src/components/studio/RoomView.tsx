"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  Clock,
  Copy,
  Crown,
  DoorOpen,
  Loader2,
  MessageSquare,
  Play,
  RotateCcw,
  Send,
  UserX,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  GAME_ICON,
  LUDO_HOME,
  LUDO_RING,
  LUDO_SAFE,
  SEAT_COLOUR,
  SEAT_DARK,
  countdown,
  isMyTurn,
  ludoTokenCell,
  playerName,
  winnerText,
  type Lobby,
  type PlayerRef,
  type Room,
  type RoomEvent,
} from "@/lib/arcade";
import { Callout } from "./ui";

/**
 * One open room: the board, the clock, who is here and the chat beside it.
 *
 * The browser never owns the board. It polls the same endpoint for a *delta*
 * (`after=<seq>`), so a missed request costs nothing and a duplicated one is
 * harmless. A refused move (409) reloads instead of retrying: the server has
 * already resolved a race that this client lost.
 */
export function RoomView({
  code,
  player,
  lobby,
  onBack,
  onChanged,
}: {
  code: string;
  player: PlayerRef;
  lobby: Lobby | null;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [room, setRoom] = useState<Room | null>(null);
  const [events, setEvents] = useState<RoomEvent[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [copied, setCopied] = useState(false);
  const seq = useRef(0);
  const feed = useRef<HTMLDivElement>(null);

  const apply = useCallback((next: Room, rows: RoomEvent[]) => {
    setRoom(next);
    seq.current = Math.max(seq.current, next.seq);
    if (rows.length) setEvents((current) => [...current, ...rows].slice(-120));
  }, []);

  /** One read. `after` makes it cheap and idempotent. */
  const load = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/arcade/room/${encodeURIComponent(code)}?after=${seq.current}`,
        { cache: "no-store" },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        if (response.status === 404) {
          setError(data.error || "That room no longer exists.");
          setRoom(null);
          return;
        }
        throw new Error(data.error || "The room is unavailable.");
      }
      apply(data.room as Room, (data.events || []) as RoomEvent[]);
      setError("");
    } catch (failure) {
      setError((failure as Error).message);
    }
  }, [apply, code]);

  useEffect(() => {
    seq.current = 0;
    void load();
    const poll = setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, 2200);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [load]);

  useEffect(() => {
    const node = feed.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [events.length]);

  const send = useCallback(
    async (payload: Record<string, unknown>) => {
      setBusy(true);
      try {
        const response = await fetch(`/api/arcade/room/${encodeURIComponent(code)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          cache: "no-store",
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 409) {
          setError("Someone moved first. The board is being reloaded.");
          seq.current = 0;
          setEvents([]);
          await load();
          return;
        }
        if (!response.ok || !data.ok) throw new Error(data.error || "That action was refused.");
        setError("");
        if (data.room) apply(data.room as Room, (data.events || []) as RoomEvent[]);
        else await load();
        onChanged();
      } catch (failure) {
        setError((failure as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [apply, code, load, onChanged],
  );

  const move = useCallback(
    (payload: Record<string, unknown>) => {
      if (!room || busy) return;
      void send({ action: "move", move: payload });
    },
    [busy, room, send],
  );

  const mine = room?.you.seat !== null && room?.you.seat !== undefined;
  const myTurn = room ? isMyTurn(room) : false;
  const ready = room?.legal || [];
  const chatOnly = room ? !mine : true;

  const share = useCallback(async () => {
    if (!room) return;
    const link = `${window.location.origin}/?tab=arcade&room=${room.code}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setError(`Copy this link: ${link}`);
    }
  }, [room]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={onBack} className="ios-btn ios-btn-glass">
          <ArrowLeft size={16} aria-hidden /> Arcade
        </button>
        <span className="mono rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm tracking-[0.3em]">
          {code}
        </span>
        <button onClick={share} className="ios-btn ios-btn-glass">
          {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
          {copied ? "Link copied" : "Share room"}
        </button>
        {room ? (
          <span className="ios-caps ml-auto flex items-center gap-1.5 text-[11px] text-indigo-100/60">
            {room.seats.some((seat) => seat.online) ? (
              <Wifi size={13} aria-hidden />
            ) : (
              <WifiOff size={13} aria-hidden />
            )}
            {room.seats.filter((seat) => seat.online).length}/{room.seats.length || room.seat_count} online
            <span className="mx-1 text-indigo-100/25">·</span>
            <span className="mono">v{room.version}</span>
          </span>
        ) : null}
      </div>

      {error ? (
        <Callout tone="warn" title="Room notice">
          {error}
        </Callout>
      ) : null}

      {!room ? (
        <div className="ios-card flex items-center gap-3 p-6 text-sm text-indigo-100/60">
          <Loader2 size={18} className="animate-spin" aria-hidden /> Opening room {code}…
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-4">
            <header className="ios-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="ios-caps text-[11px] text-indigo-200/50">
                    {GAME_ICON[room.game] || "🎮"} {room.game_name} · {room.seat_count} seats
                  </p>
                  <h2 className="mt-1 text-xl font-semibold">
                    {room.title || `Room ${room.code}`}
                  </h2>
                  <p className="mt-1 text-xs text-indigo-100/55">
                    {room.status === "open"
                      ? "Waiting for players. The host starts the game."
                      : room.status === "playing"
                        ? myTurn
                          ? "Your turn."
                          : `Waiting for ${playerName(room, room.seats.find((seat) => seat.seat === room.turn)?.user ?? null)}.`
                        : winnerText(room)}
                  </p>
                </div>
                {room.status === "playing" && room.deadline_at ? (
                  <span
                    className={`mono flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm ${
                      myTurn ? "bg-amber-400/15 text-amber-200" : "bg-white/[0.05] text-indigo-100/60"
                    }`}
                  >
                    <Clock size={14} aria-hidden /> {countdown(room.deadline_at, now) || "…"}
                  </span>
                ) : null}
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {room.seats.map((seat) => (
                  <span
                    key={seat.user}
                    className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs"
                    style={
                      room.game === "ludo"
                        ? { borderColor: `${SEAT_COLOUR[seat.seat] || "#6366f1"}66` }
                        : undefined
                    }
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: SEAT_COLOUR[seat.seat] || "#6366f1" }}
                      aria-hidden
                    />
                    {seat.name}
                    {seat.user === room.host ? <Crown size={12} aria-label="host" /> : null}
                    {seat.online ? null : (
                      <span className="text-[10px] text-indigo-100/35">away</span>
                    )}
                    {room.status === "playing" && room.turn === seat.seat ? (
                      <span className="ios-caps text-[9px] text-indigo-200/70">turn</span>
                    ) : null}
                  </span>
                ))}
                {Array.from({ length: Math.max(0, room.seat_count - room.seats.length) }).map(
                  (_, index) => (
                    <span
                      key={`empty-${index}`}
                      className="rounded-xl border border-dashed border-white/15 px-2.5 py-1.5 text-xs text-indigo-100/35"
                    >
                      Empty seat
                    </span>
                  ),
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {room.status === "open" && room.you.is_host ? (
                  <button
                    onClick={() => void send({ action: "start" })}
                    disabled={busy || room.seats.length < 2}
                    className="ios-btn ios-btn-primary"
                  >
                    <Play size={16} aria-hidden /> Start game
                  </button>
                ) : null}
                {room.status === "open" && !mine ? (
                  <button
                    onClick={() => void send({ action: "move", move: {} })}
                    disabled={busy}
                    className="ios-btn ios-btn-primary"
                  >
                    <DoorOpen size={16} aria-hidden /> Take a seat
                  </button>
                ) : null}
                {room.status === "done" ? (
                  <button onClick={() => void send({ action: "rematch" })} disabled={busy} className="ios-btn ios-btn-primary">
                    <RotateCcw size={16} aria-hidden /> Rematch
                  </button>
                ) : null}
                {mine && room.status !== "done" ? (
                  <button onClick={() => void send({ action: "leave" })} disabled={busy} className="ios-btn ios-btn-glass">
                    <DoorOpen size={16} aria-hidden /> Leave
                  </button>
                ) : null}
                {room.you.is_host
                  ? room.seats
                      .filter((seat) => seat.user !== room.host)
                      .map((seat) => (
                        <button
                          key={`kick-${seat.user}`}
                          onClick={() => void send({ action: "kick", user: seat.user })}
                          disabled={busy || room.status === "playing"}
                          className="ios-btn ios-btn-glass text-[11px]"
                          title={room.status === "playing" ? "A game in progress cannot kick" : `Remove ${seat.name}`}
                        >
                          <UserX size={13} aria-hidden /> {seat.name}
                        </button>
                      ))
                  : null}
              </div>
            </header>

            <div className="ios-card p-3 sm:p-5">
              <Board room={room} myTurn={myTurn} legal={ready} busy={busy} onMove={move} />
            </div>

            {room.status === "open" && !chatOnly ? (
              <Callout tone="info" title="Waiting room">
                Share the code <b className="mono">{room.code}</b> or the room link. The board
                opens when the game starts.
              </Callout>
            ) : null}
          </div>

          <aside className="ios-card flex min-h-[24rem] flex-col p-3">
            <p className="ios-caps flex items-center gap-2 px-1 text-[11px] text-indigo-100/50">
              <MessageSquare size={14} aria-hidden /> Room chat
            </p>
            <div ref={feed} className="mt-2 flex-1 space-y-1.5 overflow-y-auto px-1" aria-live="polite">
              {events.length === 0 ? (
                <p className="py-8 text-center text-xs text-indigo-100/35">
                  Nothing yet. Say hello.
                </p>
              ) : (
                events.map((event) => {
                  if (event.kind === "chat") {
                    const own = event.user === player.id;
                    return (
                      <p
                        key={`${event.seq}-${event.kind}`}
                        className={`rounded-xl px-2.5 py-1.5 text-xs leading-5 ${
                          own ? "bg-indigo-400/15 text-indigo-50" : "bg-white/[0.05]"
                        }`}
                      >
                        <span className="mr-1.5 font-medium text-indigo-200/70">
                          {playerName(room, event.user)}
                        </span>
                        {event.text}
                      </p>
                    );
                  }
                  return (
                    <p key={`${event.seq}-${event.kind}`} className="px-1 text-[11px] text-indigo-100/40">
                      {event.text || event.kind}
                    </p>
                  );
                })
              )}
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const value = text.trim();
                if (!value) return;
                setText("");
                void send({ action: "chat", text: value });
              }}
              className="mt-2 flex gap-2"
            >
              <input
                value={text}
                onChange={(event) => setText(event.target.value)}
                maxLength={400}
                placeholder="Message the room"
                aria-label="Room message"
                className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs outline-none focus:border-indigo-300/40"
              />
              <button type="submit" disabled={busy || !text.trim()} className="ios-btn ios-btn-primary px-3" aria-label="Send message">
                <Send size={14} aria-hidden />
              </button>
            </form>
          </aside>
        </div>
      )}

      {lobby?.leaderboards && Object.keys(lobby.leaderboards).length ? (
        <div className="ios-card p-4">
          <p className="ios-caps text-[11px] text-indigo-100/50">Top players</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            {Object.entries(lobby.leaderboards).map(([game, rows]) => (
              <div key={game}>
                <p className="text-xs font-medium text-indigo-100/70">
                  {GAME_ICON[game] || "🎮"} {game}
                </p>
                <ol className="mt-1 space-y-0.5 text-[11px] text-indigo-100/55">
                  {rows.slice(0, 5).map((row, index) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span className="truncate">
                        {index + 1}. {row.name}
                      </span>
                      <span className="mono">{row.rating}</span>
                    </li>
                  ))}
                  {rows.length === 0 ? <li className="text-indigo-100/30">No games yet.</li> : null}
                </ol>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Board({
  room,
  myTurn,
  legal,
  busy,
  onMove,
}: {
  room: Room;
  myTurn: boolean;
  legal: Record<string, unknown>[];
  busy: boolean;
  onMove: (move: Record<string, unknown>) => void;
}) {
  const cells = useMemo(() => new Set(legal.map((entry) => Number(entry.cell ?? -1))), [legal]);
  const columns = useMemo(
    () => new Set(legal.map((entry) => Number(entry.column ?? -1))),
    [legal],
  );
  const state = room.state as Record<string, unknown>;
  const board = (state.board as number[]) || [];
  const winner = state.winner as number | "draw" | null;

  if (room.status === "open") {
    return (
      <p className="py-12 text-center text-sm text-indigo-100/40">
        The board appears when the host starts the game.
      </p>
    );
  }

  if (room.game === "ludo") {
    const tokens = (state.tokens as number[][]) || [];
    const roll = state.roll as number | null;
    const starts = (state.starts as number[]) || [];
    const actions = new Set(legal.map((entry) => String(entry.action)));
    const movable = new Set(
      legal.filter((entry) => entry.action === "move").map((entry) => Number(entry.token)),
    );
    return (
      <div className="space-y-3">
        <LudoBoard room={room} tokens={tokens} starts={starts} movable={movable} myTurn={myTurn} busy={busy} onMove={onMove} />
        <div className="flex flex-wrap items-center gap-2">
          <span className="mono rounded-xl border border-white/10 px-3 py-2 text-sm">
            {roll === null ? "No roll yet" : `Rolled ${roll}`}
          </span>
          {myTurn && actions.has("roll") ? (
            <button onClick={() => onMove({ action: "roll" })} disabled={busy} className="ios-btn ios-btn-primary">
              🎲 Roll
            </button>
          ) : null}
          {myTurn && actions.has("pass") ? (
            <button onClick={() => onMove({ action: "pass" })} disabled={busy} className="ios-btn ios-btn-glass">
              Pass
            </button>
          ) : null}
          {myTurn && roll !== null && movable.size > 0 ? (
            <span className="text-xs text-indigo-100/55">Pick a glowing token.</span>
          ) : null}
          {!myTurn ? <span className="text-xs text-indigo-100/40">Waiting for the other players.</span> : null}
        </div>
      </div>
    );
  }

  if (room.game === "reversi") {
    return (
      <div className="space-y-3">
        <div className="mx-auto grid w-full max-w-[34rem] grid-cols-8 gap-1 rounded-2xl bg-emerald-900/40 p-2">
          {board.map((value, index) => (
            <button
              key={index}
              onClick={() => cells.has(index) && onMove({ cell: index })}
              disabled={!myTurn || busy || !cells.has(index)}
              aria-label={`square ${index + 1}${value ? `, player ${value}` : ""}`}
              className={`relative aspect-square rounded-md ${
                cells.has(index) && myTurn ? "bg-emerald-700/60 hover:bg-emerald-600/70" : "bg-emerald-800/50"
              } disabled:cursor-default`}
            >
              {value ? (
                <span
                  className="absolute inset-[18%] rounded-full"
                  style={{ background: value === 1 ? "#0b0b12" : "#f8fafc", boxShadow: "inset 0 1px 2px rgba(255,255,255,0.25)" }}
                />
              ) : cells.has(index) && myTurn ? (
                <span className="absolute inset-[30%] rounded-full border border-indigo-200/60" />
              ) : null}
            </button>
          ))}
        </div>
        <p className="text-center text-xs text-indigo-100/55">
          Black {((state.score as number[]) || [0, 0])[0]} · White {((state.score as number[]) || [0, 0])[1]}
          {room.state.turn !== undefined && room.status === "playing"
            ? ` · ${room.turn === 0 ? "Black" : "White"} to move`
            : ""}
        </p>
      </div>
    );
  }

  if (room.game === "tictactoe") {
    const colours = ["#38bdf8", "#fb7185"];
    return (
      <div className="mx-auto grid w-full max-w-[20rem] grid-cols-3 gap-2">
        {board.map((value, index) => (
          <button
            key={index}
            onClick={() => cells.has(index) && onMove({ cell: index })}
            disabled={!myTurn || busy || !cells.has(index)}
            aria-label={`square ${index + 1}${value ? `, player ${value}` : ""}`}
            className={`grid aspect-square place-items-center rounded-2xl border text-4xl font-semibold ${
              cells.has(index) && myTurn
                ? "border-indigo-300/40 bg-indigo-400/10 hover:bg-indigo-400/20"
                : "border-white/10 bg-white/[0.03]"
            } disabled:cursor-default`}
            style={value ? { color: colours[value - 1] } : undefined}
          >
            {value === 1 ? "✕" : value === 2 ? "◯" : ""}
          </button>
        ))}
        {winner === "draw" ? (
          <p className="col-span-3 text-center text-sm text-indigo-100/60">Drawn.</p>
        ) : null}
      </div>
    );
  }

  // Connect Four: seven drop buttons over a six-row field.
  const winning = new Set(((state.line as number[]) || []).map(Number));
  return (
    <div className="space-y-2">
      <div className="mx-auto grid w-full max-w-[30rem] grid-cols-7 gap-1">
        {Array.from({ length: 7 }).map((_, column) => (
          <button
            key={column}
            onClick={() => columns.has(column) && onMove({ column })}
            disabled={!myTurn || busy || !columns.has(column)}
            aria-label={`drop in column ${column + 1}`}
            className={`rounded-lg py-1.5 text-[10px] ${
              myTurn && columns.has(column)
                ? "bg-indigo-400/20 text-indigo-100 hover:bg-indigo-400/35"
                : "text-indigo-100/25"
            }`}
          >
            ▼
          </button>
        ))}
      </div>
      <div className="mx-auto grid w-full max-w-[30rem] grid-cols-7 gap-1 rounded-2xl bg-indigo-950/60 p-2">
        {Array.from({ length: 42 }).map((_, index) => {
          const row = Math.floor(index / 7);
          const column = index % 7;
          const value = board[row * 7 + column] || 0;
          return (
            <span
              key={index}
              className="grid aspect-square place-items-center rounded-full"
              style={{
                background: value === 1 ? "#ef4444" : value === 2 ? "#facc15" : "rgba(255,255,255,0.06)",
                outline: winning.has(row * 7 + column) ? "2px solid #a5b4fc" : undefined,
              }}
            />
          );
        })}
      </div>
      <p className="text-center text-xs text-indigo-100/55">
        Red {board.filter((value) => value === 1).length} · Yellow {board.filter((value) => value === 2).length}
      </p>
    </div>
  );
}

function LudoBoard({
  room,
  tokens,
  starts,
  movable,
  myTurn,
  busy,
  onMove,
}: {
  room: Room;
  tokens: number[][];
  starts: number[];
  movable: Set<number>;
  myTurn: boolean;
  busy: boolean;
  onMove: (move: Record<string, unknown>) => void;
}) {
  /** Every token, including the ones still in the four bases. */
  const placed = useMemo(
    () =>
      tokens.flatMap((progress, seat) =>
        progress.map((value, token) => ({
          seat,
          token,
          cell: ludoTokenCell(starts[seat] ?? 0, value, token),
        })),
      ),
    [starts, tokens],
  );

  const seatColour = (seat: number) => SEAT_COLOUR[seat] || "#6366f1";

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[32rem] rounded-2xl bg-white/[0.03] p-1">
      <div className="relative h-full w-full overflow-hidden rounded-xl">
        {[0, 1, 2, 3].slice(0, Math.max(2, room.seat_count)).map((seat) => (
          <span
            key={`base-${seat}`}
            className="absolute rounded-xl opacity-15"
            style={{
              width: "28%",
              height: "28%",
              left: `${(seat % 2 === 0 ? 2.5 : 69.5)}%`,
              top: `${seat < 2 ? 2.5 : 69.5}%`,
              background: seatColour(seat),
            }}
          />
        ))}
        {LUDO_RING.map(([row, col], index) => (
          <span
            key={`ring-${index}`}
            className="absolute rounded-[3px]"
            style={{
              left: `${(col / 15) * 100}%`,
              top: `${(row / 15) * 100}%`,
              width: `${100 / 15}%`,
              height: `${100 / 15}%`,
              background: LUDO_SAFE.has(index) ? "rgba(250,204,21,0.20)" : "rgba(255,255,255,0.07)",
            }}
          />
        ))}
        {Object.entries(LUDO_HOME).flatMap(([seat, list]) =>
          list.map(([row, col], index) => (
            <span
              key={`home-${seat}-${index}`}
              className="absolute rounded-[3px]"
              style={{
                left: `${(col / 15) * 100}%`,
                top: `${(row / 15) * 100}%`,
                width: `${100 / 15}%`,
                height: `${100 / 15}%`,
                background: `${seatColour(Number(seat))}55`,
              }}
            />
          )),
        )}
        <span
          className="absolute rounded-lg"
          style={{
            left: `${(6 / 15) * 100}%`,
            top: `${(6 / 15) * 100}%`,
            width: `${(3 / 15) * 100}%`,
            height: `${(3 / 15) * 100}%`,
            background: "rgba(165,180,252,0.30)",
          }}
        />
        {placed.map(({ seat, token, cell }) => {
          const selectable =
            myTurn && seat === room.you.seat && movable.has(token) && !busy;
          const sameCell = placed.filter(
            (other) => other.cell.row === cell.row && other.cell.col === cell.col,
          );
          const order = sameCell.findIndex((other) => other.seat === seat && other.token === token);
          return (
            <button
              key={`token-${seat}-${token}`}
              onClick={() => selectable && onMove({ action: "move", token })}
              disabled={!selectable}
              aria-label={`seat ${seat + 1} token ${token + 1}`}
              className={`absolute rounded-full transition ${
                selectable
                  ? "z-20 ring-2 ring-white ring-offset-1 ring-offset-slate-900 hover:scale-110"
                  : "z-10"
              }`}
              style={{
                left: `${((cell.col + 0.18) / 15) * 100 + (order % 2) * 3}%`,
                top: `${((cell.row + 0.18) / 15) * 100 + (order > 1 ? 4 : 0)}%`,
                width: `${(0.68 / 15) * 100}%`,
                height: `${(0.68 / 15) * 100}%`,
                minWidth: 12,
                minHeight: 12,
                background: seatColour(seat),
                border: `1.5px solid ${SEAT_DARK[seat] || "#312e81"}`,
                boxShadow: "0 1px 3px rgba(0,0,0,0.45)",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
