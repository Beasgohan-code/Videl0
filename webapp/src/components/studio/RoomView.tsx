"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  ArrowLeft,
  Check,
  Clock3,
  Copy,
  Crown,
  DoorOpen,
  Link2,
  Loader2,
  MessageSquare,
  Play,
  RotateCcw,
  Send,
  Sparkles,
  Trophy,
  UserX,
  Wifi,
  WifiOff,
  Zap,
} from "lucide-react";
import {
  GAME_ICON,
  GAME_TERMS,
  LUDO_HOME,
  LUDO_RING,
  LUDO_SAFE,
  countdown,
  initials,
  isMyTurn,
  laneVars,
  ludoTokenCell,
  inviteLink,
  playerName,
  seatColour,
  seatVars,
  telegramInvite,
  themeOf,
  turnFraction,
  winnerText,
  type Lobby,
  type PlayerRef,
  type Room,
  type RoomEvent,
} from "@/lib/arcade";
import { CheckersBoard } from "./boards/CheckersBoard";
import { ChessBoard } from "./boards/ChessBoard";
import { GomokuBoard } from "./boards/GomokuBoard";
import { VoiceDock } from "./boards/VoiceDock";
import { TableActions } from "./boards/TableActions";
import { Callout } from "./ui";

/**
 * One open room: the table, the clock, the people and the talk.
 *
 * The browser never owns the board — it polls for a delta (`after=<seq>`) and
 * sends only a move. A refused move (409) reloads instead of retrying, because
 * the server has already resolved a race this client lost.
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
  const [skew, setSkew] = useState(0);
  const [copied, setCopied] = useState<"" | "link" | "code">("");
  const [talkers, setTalkers] = useState<number[]>([]);
  const [muted, setMuted] = useState(true);
  const seq = useRef(0);
  const triedJoin = useRef(false);
  const feed = useRef<HTMLDivElement>(null);

  const apply = useCallback((next: Room, rows: RoomEvent[]) => {
    // The turn clock is measured on the server; a phone with a wrong clock must
    // not see "0s" while the room still has half a minute.
    const serverNow = Date.parse(next.server_time);
    if (Number.isFinite(serverNow)) setSkew(serverNow - Date.now());
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
      if (response.status === 403 && !triedJoin.current) {
        // A shared link is an invitation. Take the free seat if there is one,
        // then read again: a room already in play is watchable when public,
        // and a private one explains itself instead of showing a dead card.
        triedJoin.current = true;
        const join = await fetch("/api/arcade/join", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
          cache: "no-store",
        }).catch(() => null);
        const answer = await join?.json().catch(() => ({}));
        if (join?.ok && answer?.room) {
          setError("");
          apply(answer.room as Room, []);
        }
        return load();
      }
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
    triedJoin.current = false;
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
          setError("Someone moved first. The table is being reloaded.");
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

  const seated = room ? room.you.seat !== null : false;
  const myTurn = room ? isMyTurn(room) : false;
  const theme = themeOf(room?.game || "connect4");
  const seats = room?.seats || [];
  const online = seats.filter((seat) => seat.online).length;
  const current = room?.seats.find((seat) => seat.seat === room.turn);

  /* One invite, three ways to hand it over: the share sheet, the clipboard,
     then the link printed in the notice. The link is a real page that opens in
     Chrome, so a friend without Telegram can still see the table. */
  const share = useCallback(async () => {
    if (!room) return;
    const link = inviteLink(room.code, window.location.origin);
    const text = `${room.game_name} on Videl — ${room.seat_count} seats, code ${room.code}. Take a chair:`;
    const sheet = (navigator as Navigator & {
      share?: (data: ShareData) => Promise<void>;
    }).share;
    if (sheet) {
      try {
        await sheet.call(navigator, { title: `${room.game_name} · ${room.code}`, text, url: link });
        return;
      } catch {
        /* dismissed — fall through to the clipboard instead of scolding */
      }
    }
    try {
      await navigator.clipboard.writeText(`${text} ${link}`);
      setCopied("link");
      setTimeout(() => setCopied(""), 1800);
    } catch {
      setError(`Copy this link: ${link}`);
    }
  }, [room]);

  const copyCode = useCallback(async () => {
    if (!room) return;
    try {
      await navigator.clipboard.writeText(room.code);
      setCopied("code");
      setTimeout(() => setCopied(""), 1800);
    } catch {
      setError(`The room code is ${room.code}`);
    }
  }, [room]);

  const join = useCallback(async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/arcade/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || "That seat could not be taken.");
      apply(data.room as Room, []);
      setError("");
      onChanged();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }, [apply, code, onChanged]);

  return (
    <div className="space-y-3">
      <div className="arcade-room-bar">
        <button onClick={onBack} className="ios-btn ios-btn-glass px-3 py-1.5 text-xs" aria-label="Back to the arcade">
          <ArrowLeft size={15} aria-hidden /> Arcade
        </button>
        <button
          onClick={() => void copyCode()}
          className="arcade-code"
          title="Copy the room code"
          aria-label={`Room code ${code}. Copy code`}
        >
          {code}
          {copied === "code" ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
        </button>
        {room ? (
          <span className="arcade-live ml-auto hidden sm:inline-flex">
            {online > 0 ? <Wifi size={11} aria-hidden /> : <WifiOff size={11} aria-hidden />}
            {online}/{room.seats.length || room.seat_count} online
            <span className="text-indigo-100/25">·</span>
            <span className="mono">v{room.version}</span>
          </span>
        ) : null}
        {room && seated && room.status !== "done" ? (
          <button onClick={() => void send({ action: "leave" })} disabled={busy} className="ios-btn ios-btn-glass px-3 py-1.5 text-xs">
            <DoorOpen size={14} aria-hidden /> Leave
          </button>
        ) : null}
        <a
          href={telegramInvite(code)}
          target="_blank"
          rel="noreferrer"
          className="ios-btn ios-btn-glass px-3 py-1.5 text-xs"
          aria-label="Open this table in Telegram"
          title="Open the table in Telegram"
        >
          <Send size={13} aria-hidden /> <span className="hidden sm:inline">Telegram</span>
        </a>
        <button onClick={() => void share()} className="ios-btn ios-btn-glass px-3 py-1.5 text-xs" aria-label="Copy an invite link">
          <Link2 size={14} aria-hidden />{" "}
          <span className="hidden sm:inline">{copied === "link" ? "Sent" : "Invite"}</span>
        </button>
      </div>

      {error ? (
        <Callout tone="warn" title="Table notice">
          {error}
        </Callout>
      ) : null}

      {!room ? (
        <div className="arcade-table flex items-center gap-3 p-8 text-sm text-indigo-100/55">
          <Loader2 size={18} className="animate-spin" aria-hidden /> Setting the table {code}…
        </div>
      ) : (
        <>
          {room.status === "done" ? (
            <div className="arcade-result">
              <span className="arcade-trophy" aria-hidden>
                🏆
              </span>
              <div className="min-w-0 flex-1">
                <b>{winnerText(room)}</b>
                <span>
                  {room.title || room.game_name} · {room.code}
                </span>
              </div>
              {room.you.is_host ? (
                <button onClick={() => void send({ action: "rematch" })} disabled={busy} className="ios-btn ios-btn-primary px-3 py-2 text-xs">
                  <RotateCcw size={14} aria-hidden /> Rematch
                </button>
              ) : (
                <span className="text-[10px] text-indigo-100/45">
                  the host can start a rematch
                </span>
              )}
            </div>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_21rem]">
            <section className="arcade-table" aria-label={`${room.game_name} board`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="ios-caps text-[10px] tracking-[0.16em] text-indigo-200/45">
                    <span aria-hidden>{GAME_ICON[room.game]}</span> {room.game_name}
                    {" · "}
                    {room.seat_count} seats
                    {!seated ? " · watching" : ""}
                  </p>
                  <h2 className="mt-1 truncate text-[1.05rem] font-semibold tracking-tight">
                    {room.title || `Table ${room.code}`}
                  </h2>
                </div>
                <span
                  className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em]"
                  style={{ background: `${theme.accent}22`, color: theme.accent }}
                >
                  {room.status === "open" ? "waiting" : room.status}
                </span>
              </div>

              <div className="arcade-seats mt-2.5">
                {seats.map((seat) => (
                  <span
                    key={seat.user}
                    className="arcade-seat"
                    data-turn={room.status === "playing" && room.turn === seat.seat}
                    data-offline={!seat.online}
                    data-speaking={talkers.includes(seat.user)}
                    style={{ "--seat": seatColour(room.game, seat.seat) } as CSSProperties}
                  >
                    <span className="arcade-seat-avatar" aria-hidden>
                      {initials(seat.name)}
                    </span>
                    <span className="max-w-[7rem] truncate">{seat.name}</span>
                    {seat.user === player.id ? <span className="arcade-seat-tag">you</span> : null}
                    {seat.user === room.host ? <Crown size={11} className="text-amber-300/80" aria-label="host" /> : null}
                    {room.status === "playing" && room.turn === seat.seat ? <Zap size={11} className="text-amber-300" aria-label="their turn" /> : null}
                  </span>
                ))}
                {Array.from({ length: Math.max(0, room.seat_count - seats.length) }).map((_, index) => (
                  <span key={`empty-${index}`} className="arcade-seat-empty">
                    empty seat
                  </span>
                ))}
              </div>

              {room.status !== "done" ? (
              <div className="arcade-turn mt-2.5" data-mine={myTurn && room.status === "playing"}>
                <span
                  className="grid h-9 w-9 flex-none place-items-center rounded-xl"
                  style={{ background: `${theme.accent}22`, color: theme.accent }}
                  aria-hidden
                >
                  {myTurn ? <Zap size={17} /> : <Clock3 size={17} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="arcade-turn-title">{turnTitle(room, myTurn, seated)}</p>
                  <p className="arcade-turn-sub truncate">{turnSubtitle(room, myTurn, seated, current ? current.name : "")}</p>
                </div>
                {room.status === "playing" && room.deadline_at ? (
                  <span
                    className="arcade-clock"
                    data-idle={!myTurn}
                    style={{
                      "--left": String(turnFraction(room.deadline_at, room.turn_seconds, now + skew)),
                    } as CSSProperties}
                    aria-label="turn clock"
                  >
                    <span>{countdown(room.deadline_at, now + skew) || "…"}</span>
                  </span>
                ) : null}
              </div>
              ) : null}

              <div className="mt-3">
                <Board room={room} myTurn={myTurn} busy={busy} onMove={move} />
              </div>

              <TableActions room={room} busy={busy} send={send} />

              <VoiceDock
                room={room}
                seat={room.you.seat}
                events={events}
                send={send}
                onSpeaking={setTalkers}
                muted={muted}
                onMute={setMuted}
              />
              <HouseRules game={room.game} />

              <div className="arcade-actions">
                {room.status === "open" && room.you.is_host ? (
                  <button
                    onClick={() => void send({ action: "start" })}
                    disabled={busy || seats.length < 2}
                    className="ios-btn ios-btn-primary"
                  >
                    <Play size={15} aria-hidden /> Start game
                  </button>
                ) : null}
                {room.status === "open" && !seated ? (
                  <button onClick={() => void join()} disabled={busy} className="ios-btn ios-btn-primary">
                    <DoorOpen size={15} aria-hidden /> Take a seat
                  </button>
                ) : null}
                {room.status === "done" && room.you.is_host ? (
                  <button onClick={() => void send({ action: "rematch" })} disabled={busy} className="ios-btn ios-btn-primary">
                    <RotateCcw size={15} aria-hidden /> Rematch
                  </button>
                ) : null}
                <button onClick={() => void share()} className="ios-btn ios-btn-glass">
                  <Copy size={14} aria-hidden /> {copied === "link" ? "Invite copied" : "Invite"}
                </button>
                {room.you.is_host
                  ? seats
                      .filter((seat) => seat.user !== room.host)
                      .map((seat) => (
                        <button
                          key={`kick-${seat.user}`}
                          onClick={() => void send({ action: "kick", user: seat.user })}
                          disabled={busy || room.status === "playing"}
                          className="ios-btn ios-btn-glass text-[11px] opacity-70"
                          title={room.status === "playing" ? "A game in progress cannot kick" : `Remove ${seat.name}`}
                        >
                          <UserX size={12} aria-hidden /> {seat.name}
                        </button>
                      ))
                  : null}
              </div>
            </section>

            <aside className="arcade-chat" aria-label="Room chat">
              <div className="arcade-chat-head">
                <span className="inline-flex items-center gap-1.5">
                  <MessageSquare size={12} aria-hidden /> Table talk
                </span>
                <span className="inline-flex items-center gap-1.5 text-[10px] text-indigo-100/40">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" aria-hidden />
                  {online} here
                </span>
              </div>
              <div ref={feed} className="arcade-chat-feed" aria-live="polite">
                {events.length === 0 ? (
                  <p className="py-10 text-center text-xs text-indigo-100/30">
                    Quiet table. Say hello while you wait.
                  </p>
                ) : (
                  events.map((event) => {
                    if (event.kind === "chat") {
                      const own = event.user === player.id;
                      return (
                        <p key={`${event.seq}-${event.kind}`} className="arcade-bubble" data-own={own}>
                          {!own ? (
                            <span className="arcade-bubble-name">{playerName(room, event.user)}</span>
                          ) : null}
                          {event.text}
                        </p>
                      );
                    }
                    return (
                      <p key={`${event.seq}-${event.kind}`} className="arcade-event">
                        {event.text || event.kind}
                      </p>
                    );
                  })
                )}
              </div>
              <form
                className="arcade-composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  const value = text.trim();
                  if (!value || !seated) return;
                  setText("");
                  void send({ action: "chat", text: value });
                }}
              >
                <input
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  maxLength={400}
                  placeholder={seated ? "Message the table" : "Only seated players can chat"}
                  aria-label="Room message"
                  disabled={!seated}
                  title={seated ? undefined : "Join a seat to chat"}
                />
                <button
                  type="submit"
                  disabled={!seated || busy || !text.trim()}
                  className="arcade-send"
                  aria-label="Send message"
                >
                  <Send size={15} aria-hidden />
                </button>
              </form>
            </aside>
          </div>

          {lobby?.leaderboards && Object.keys(lobby.leaderboards).length ? (
            <div className="arcade-section">
              <div className="arcade-section-head">
                <span className="arcade-section-title">
                  <span className="inline-flex items-center gap-1.5">
                    <Trophy size={12} aria-hidden /> Top players
                  </span>
                </span>
                <span className="arcade-section-hint">rated rooms only</span>
              </div>
              <div className="arcade-podiums">
                {Object.entries(lobby.leaderboards).map(([game, rows]) => (
                  <div key={game} className="arcade-podium">
                    <p className="arcade-podium-name">
                      <span aria-hidden>{GAME_ICON[game]}</span> {game}
                    </p>
                    <ol>
                      {rows.slice(0, 5).map((row, index) => (
                        <li key={row.id} data-me={row.id === player.id}>
                          <span className="truncate">
                            <span className="arcade-medal" aria-hidden>
                              {["🥇", "🥈", "🥉"][index] || `${index + 1}.`}
                            </span>{" "}
                            {row.name}
                          </span>
                          <b>{row.rating}</b>
                        </li>
                      ))}
                      {rows.length === 0 ? <li>No results yet</li> : null}
                    </ol>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function HouseRules({ game }: { game: string }) {
  const rows = GAME_TERMS[game];
  if (!rows) return null;
  return (
    <details className="arcade-rules">
      <summary>House rules</summary>
      <ul>
        {rows.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
    </details>
  );
}

function turnTitle(room: Room, myTurn: boolean, seated: boolean): string {
  if (room.status === "open") {
    if (!seated) return "Watching the table fill up";
    return room.you.is_host ? "You are hosting" : "You are in — waiting for the host";
  }
  if (room.status === "done") return winnerText(room) || "Game over";
  return myTurn ? "Your move" : "Their move";
}

function turnSubtitle(room: Room, myTurn: boolean, seated: boolean, currentName: string): string {
  if (room.status === "open") {
    return `${room.seats.length} of ${room.seat_count} seats taken${
      room.seats.length >= 2 && room.you.is_host ? " — start whenever you like" : ""
    }`;
  }
  if (room.status === "done") return `${room.game_name} · ${room.code}`;
  return myTurn
    ? `The clock is yours — ${room.turn_seconds}s a turn, then the server plays`
    : `${currentName || "The other chair"} has ${room.turn_seconds}s on the clock${seated ? "" : " · you are watching"}`;
}

function Board({
  room,
  myTurn,
  busy,
  onMove,
}: {
  room: Room;
  myTurn: boolean;
  busy: boolean;
  onMove: (move: Record<string, unknown>) => void;
}) {
  const state = room.state as Record<string, unknown>;
  const legal = room.legal || [];
  const cells = useMemo(() => new Set(legal.map((entry) => Number(entry.cell ?? -1))), [legal]);
  const columns = useMemo(() => new Set(legal.map((entry) => Number(entry.column ?? -1))), [legal]);
  const board = (state.board as number[]) || [];
  const winner = state.winner as number | "draw" | null;

  if (room.status === "open") {
    return (
      <div className="arcade-empty flex flex-col items-center gap-2 py-12">
        <span className="text-3xl" aria-hidden>
          {GAME_ICON[room.game] || "🎮"}
        </span>
        <p className="max-w-xs text-center">
          The board appears when the host starts. Share the code{" "}
          <b className="mono text-indigo-100/80">{room.code}</b> to fill the last chairs.
        </p>
      </div>
    );
  }

  if (room.game === "ludo") {
    return <LudoBoard room={room} myTurn={myTurn} busy={busy} onMove={onMove} />;
  }

  if (room.game === "checkers") {
    return <CheckersBoard room={room} myTurn={myTurn} busy={busy} onMove={onMove} />;
  }

  if (room.game === "chess") {
    return <ChessBoard room={room} myTurn={myTurn} busy={busy} onMove={onMove} />;
  }

  if (room.game === "gomoku") {
    return <GomokuBoard room={room} myTurn={myTurn} busy={busy} onMove={onMove} />;
  }

  if (room.game === "reversi") {
    const score = (state.score as number[]) || [0, 0];
    const last = state.last as number | null;
    return (
      <div>
        <div className="arcade-reversi mx-auto w-full max-w-[33rem]">
          {board.map((value, index) => {
            const open = myTurn && cells.has(index);
            return (
              <button
                key={index}
                onClick={() => open && onMove({ cell: index })}
                disabled={!open || busy}
                aria-label={`square ${index + 1}${value ? `, player ${value}` : ""}`}
                className="arcade-reversi-cell"
                data-legal={open}
                data-last={last === index}
              >
                {value ? (
                  <span className={`arcade-reversi-disc ${value === 1 ? "arcade-disc-black" : "arcade-disc-white"}`} />
                ) : null}
              </button>
            );
          })}
        </div>
        <div className="arcade-scorebar">
          <span className="arcade-scorebar-side">
            <span className="arcade-score-dot arcade-disc-black" aria-hidden /> Black <b>{score[0]}</b>
          </span>
          <span className="ios-caps text-[10px] text-indigo-100/35">flips</span>
          <span className="arcade-scorebar-side">
            <b>{score[1]}</b> White <span className="arcade-score-dot arcade-disc-white" aria-hidden />
          </span>
        </div>
      </div>
    );
  }

  if (room.game === "tictactoe") {
    const winning = new Set(((state.line as number[]) || []).map(Number));
    return (
      <div>
        <div className="arcade-ttt mx-auto w-full max-w-[21rem]">
          {board.map((value, index) => {
            const open = myTurn && cells.has(index);
            return (
              <button
                key={index}
                onClick={() => open && onMove({ cell: index })}
                disabled={!open || busy}
                aria-label={`square ${index + 1}${value ? `, player ${value}` : ""}`}
                className="arcade-ttt-cell"
                data-mark={value || undefined}
                data-win={winning.has(index)}
                data-live={open}
              >
                {value === 1 ? "✕" : value === 2 ? "◯" : ""}
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-center text-[11px] text-indigo-100/45">
          {winner === "draw" ? "Drawn. Nobody blinked." : myTurn ? "Tap an empty square." : "\u00a0"}
        </p>
      </div>
    );
  }

  // Connect Four: a drop row over the field.
  const winning = new Set(((state.line as number[]) || []).map(Number));
  const last = state.last as number | null;
  return (
    <div>
      <div className="arcade-drops mx-auto max-w-[30rem]">
        {Array.from({ length: 7 }).map((_, column) => {
          const open = myTurn && columns.has(column);
          return (
            <button
              key={column}
              onClick={() => open && onMove({ column })}
              disabled={!open || busy}
              aria-label={`drop in column ${column + 1}`}
              className="arcade-drop-btn"
              data-live={open}
            >
              drop
            </button>
          );
        })}
      </div>
      <div className="arcade-c4 mx-auto max-w-[30rem]">
        {Array.from({ length: 42 }).map((_, index) => {
          const value = board[index] || 0;
          return (
            <span
              key={index}
              className="arcade-c4-cell"
              aria-label={value ? `player ${value} disc` : undefined}
            >
              {value ? (
                <span
                  className={`arcade-disc ${value === 1 ? "arcade-disc-red" : "arcade-disc-yellow"}`}
                  data-win={winning.has(index)}
                  data-last={last === index}
                />
              ) : null}
            </span>
          );
        })}
      </div>
      <p className="mt-2 text-center text-[11px] text-indigo-100/45">
        {winner === "draw"
          ? "Board full. A draw."
          : myTurn
            ? "Pick a column."
            : "Watching the discs settle."}
      </p>
    </div>
  );
}

function LudoBoard({
  room,
  myTurn,
  busy,
  onMove,
}: {
  room: Room;
  myTurn: boolean;
  busy: boolean;
  onMove: (move: Record<string, unknown>) => void;
}) {
  const state = room.state as Record<string, unknown>;
  const tokens = (state.tokens as number[][]) || [];
  const starts = (state.starts as number[]) || [];
  const roll = state.roll as number | null;
  const actions = new Set((room.legal || []).map((entry) => String(entry.action)));
  const movable = new Set(
    (room.legal || []).filter((entry) => entry.action === "move").map((entry) => Number(entry.token)),
  );

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

  const seatsInPlay = Math.max(2, room.seat_count);

  return (
    <div>
      <div className="arcade-ludo mx-auto">
        <div className="arcade-ludo-board">
          {Array.from({ length: seatsInPlay }).map((_, seat) => {
            const top = seat < 2 ? 2.5 : 69.5;
            const left = seat % 2 === 0 ? 2.5 : 69.5;
            return (
              <span
                key={`base-${seat}`}
                className="arcade-ludo-base"
                style={{ top: `${top}%`, left: `${left}%`, ...laneVars(seat) } as CSSProperties}
                aria-hidden
              />
            );
          })}
          {LUDO_RING.map(([row, col], index) => (
            <span
              key={`ring-${index}`}
              className="arcade-ludo-cell"
              data-safe={LUDO_SAFE.has(index)}
              style={{
                top: `${(row / 15) * 100}%`,
                left: `${(col / 15) * 100}%`,
                width: `${100 / 15}%`,
                height: `${100 / 15}%`,
              }}
              aria-hidden
            >
              {LUDO_SAFE.has(index) ? (
                <span className="absolute inset-0 grid place-items-center text-[7px] text-amber-200/70">✦</span>
              ) : null}
            </span>
          ))}
          {Object.entries(LUDO_HOME).map(([seat, list]) =>
            list.map(([row, col], index) => (
              <span
                key={`home-${seat}-${index}`}
                className="arcade-ludo-cell"
                data-kind="home"
                style={{
                  top: `${(row / 15) * 100}%`,
                  left: `${(col / 15) * 100}%`,
                  width: `${100 / 15}%`,
                  height: `${100 / 15}%`,
                  ...laneVars(Number(seat)),
                } as CSSProperties}
                aria-hidden
              />
            )),
          )}
          <span
            className="arcade-ludo-cell"
            data-kind="centre"
            style={{ top: `${(6 / 15) * 100}%`, left: `${(6 / 15) * 100}%`, width: "20%", height: "20%" }}
            aria-hidden
          >
            <span className="absolute inset-0 grid place-items-center text-sm">🏁</span>
          </span>
          {placed.map(({ seat, token, cell }) => {
            const selectable = myTurn && seat === room.you.seat && movable.has(token) && !busy;
            const same = placed.filter(
              (other) => other.cell.row === cell.row && other.cell.col === cell.col,
            );
            const order = same.findIndex((other) => other.seat === seat && other.token === token);
            return (
              <button
                key={`token-${seat}-${token}`}
                onClick={() => selectable && onMove({ action: "move", token })}
                disabled={!selectable}
                aria-label={`seat ${seat + 1} token ${token + 1}`}
                className="arcade-ludo-token"
                data-live={selectable}
                style={{
                  top: `${((cell.row + 0.18) / 15) * 100 + (order > 1 ? 4 : 0)}%`,
                  left: `${((cell.col + 0.18) / 15) * 100 + (order % 2) * 3}%`,
                  width: `${(0.68 / 15) * 100}%`,
                  height: `${(0.68 / 15) * 100}%`,
                  ...seatVars(seat),
                } as CSSProperties}
              />
            );
          })}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        <span className="arcade-ludo-die">
          🎲 <b>{roll === null ? "—" : roll}</b> {roll === null ? "roll to move" : "rolled"}
        </span>
        {myTurn && actions.has("roll") ? (
          <button onClick={() => onMove({ action: "roll" })} disabled={busy} className="ios-btn ios-btn-primary">
            Roll the die
          </button>
        ) : null}
        {myTurn && actions.has("pass") ? (
          <button onClick={() => onMove({ action: "pass" })} disabled={busy} className="ios-btn ios-btn-glass">
            Pass
          </button>
        ) : null}
        {myTurn && roll !== null && movable.size > 0 ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-indigo-100/55">
            <Sparkles size={12} aria-hidden /> pick a glowing token
          </span>
        ) : null}
        {!myTurn ? (
          <span className="text-[11px] text-indigo-100/35">
            Waiting for {playerName(room, room.seats.find((seat) => seat.seat === room.turn)?.user ?? null)}
          </span>
        ) : null}
      </div>
    </div>
  );
}
