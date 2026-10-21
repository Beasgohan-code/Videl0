"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  Check,
  ChevronRight,
  Gamepad2,
  Globe2,
  Loader2,
  Lock,
  LogIn,
  Plus,
  RefreshCw,
  Sparkles,
  Trophy,
  Users,
  Wifi,
} from "lucide-react";
import { usePlayerSession } from "@/lib/player";
import {
  GAME_ART,
  GAME_ICON,
  GAME_THEME,
  codeFromLink,
  inviteLink,
  themeOf,
  type GameInfo,
  type Lobby,
  type PlayerRef,
  type RoomRow,
  type Stat,
} from "@/lib/arcade";
import { RoomView } from "../RoomView";
import { Callout } from "../ui";

/**
 * The arcade lobby.
 *
 * A table, not a settings page: pick a game like picking up a box, choose how
 * many chairs, and the invite card is the loudest thing on screen. Signing in
 * is still Telegram-only — the room has to know who is moving.
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
  const [copied, setCopied] = useState(false);

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
    const upper = value.toUpperCase();
    setRoom(upper);
    const url = new URL(window.location.href);
    url.searchParams.set("room", upper);
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

  const games: GameInfo[] = useMemo(
    () => lobby?.games?.length ? lobby.games : FALLBACK_GAMES,
    [lobby],
  );
  const chosen = games.find((entry) => entry.key === game) || games[0];
  const stats = lobby?.me?.stats;
  const best = useMemo(() => {
    const rows = Object.values(stats || {}) as Stat[];
    const played = rows.filter((row) => Number(row?.games) > 0);
    if (!played.length) return null;
    return played.reduce((top, row) => (row.rating > top.rating ? row : top));
  }, [stats]);

  /* ── a room takes the whole screen ─────────────────────────────────────── */
  if (player && room) {
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

  /* ── signed out: explain the door, show the room ───────────────────────── */
  if (!player) {
    return (
      <main className="ios-page">
        <Hero
          kicker="Arcade"
          title="Pull up a chair."
          subtitle="Five boards, one to four chairs each. Rooms live on the server, so closing the app never loses your turn — or your clock."
          stats={[
            { value: String(FALLBACK_GAMES.length), label: "boards" },
            { value: "2–4", label: "chairs" },
            { value: "∞", label: "rematches" },
          ]}
        />
        <div className="arcade-signin">
          <div>
            <span className="arcade-kicker">
              <Sparkles size={12} aria-hidden /> Your seat
            </span>
            <h2 className="mt-3 text-xl font-semibold tracking-tight">
              Sign in with Telegram
            </h2>
            <p className="mt-1.5 max-w-md text-sm leading-6 text-indigo-100/60">
              Your Telegram account is your player card. No password, no email, no new
              profile — and nobody can move for you.
            </p>
            <button
              onClick={() => void signIn()}
              disabled={busy}
              className="ios-btn ios-btn-primary mt-4 w-full sm:w-auto"
            >
              <LogIn size={16} aria-hidden /> Continue with Telegram
            </button>
            {signInError ? (
              <p className="mt-3 text-xs text-amber-200/85" role="status">
                {signInError}
              </p>
            ) : null}
            <div className="arcade-signin-steps mt-4">
              <p className="arcade-step">
                <b>1</b> Open Videl from the bot inside Telegram.
              </p>
              <p className="arcade-step">
                <b>2</b> Tap the arcade, then this button — Telegram confirms it is you.
              </p>
              <p className="arcade-step">
                <b>3</b> Create a room and send the six-character code to a friend.
              </p>
            </div>
          </div>
          <div>
            <div className="arcade-minis">
              {FALLBACK_GAMES.map((entry) => (
                <div
                  key={entry.key}
                  className="arcade-mini"
                  style={{ "--accent-soft": themeOf(entry.key).soft } as CSSProperties}
                  aria-hidden
                >
                  {GAME_ART[entry.key] ? (
                    <img src={GAME_ART[entry.key]} alt="" loading="lazy" decoding="async" />
                  ) : null}
                  <span>{entry.name}</span>
                </div>
              ))}
            </div>
            <Callout tone="info" title="No downloads, no accounts">
              Your board lives on the bot server. Reopen the link and the game is exactly
              where you left it, clock included.
            </Callout>
          </div>
        </div>
      </main>
    );
  }

  /* ── signed in: the lobby ──────────────────────────────────────────────── */
  return (
    <main className="ios-page">
      <Hero
        kicker="Arcade"
        title="Pull up a chair."
        subtitle={`Signed in as ${player.name}. Pick a table, or drop in with a code somebody sent you.`}
        live={`${lobby?.public.length ?? 0} open now`}
        stats={[
          { value: String(lobby?.public.length ?? 0), label: "open tables" },
          { value: String(lobby?.mine.length ?? 0), label: "your tables" },
          { value: best ? String(best.rating) : "—", label: best ? "best rating" : "unrated" },
        ]}
        action={
          <button onClick={() => void load()} disabled={busy} className="arcade-live" aria-label="Refresh lobby">
            <RefreshCw size={12} className={busy ? "animate-spin" : undefined} aria-hidden /> refresh
          </button>
        }
      />

      {error ? (
        <div className="mt-3">
          <Callout tone="warn" title="Arcade notice">
            {error}
          </Callout>
        </div>
      ) : null}

      <section className="arcade-section" aria-label="Choose a game">
        <div className="arcade-section-head">
          <span className="arcade-section-title">Choose a table</span>
          <span className="arcade-section-hint">{chosen ? `${chosen.turn_seconds}s a turn` : ""}</span>
        </div>
        <div className="arcade-gallery" role="group" aria-label="Games">
          {games.map((entry) => {
            const theme = themeOf(entry.key);
            const active = game === entry.key;
            return (
              <button
                key={entry.key}
                onClick={() => {
                  setGame(entry.key);
                  setSeats(entry.seats[0]);
                }}
                aria-pressed={active}
                className="arcade-plate"
                style={{ "--accent": theme.accent, "--accent-soft": theme.soft } as CSSProperties}
              >
                <span className="arcade-plate-art" aria-hidden>
                  {GAME_ART[entry.key] ? (
                    <img
                      src={GAME_ART[entry.key]}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      width={720}
                      height={393}
                    />
                  ) : null}
                  <span className="arcade-plate-glow" />
                </span>
                <span className="arcade-plate-body">
                  <span className="arcade-plate-name">
                    <span className="arcade-plate-glyph" aria-hidden>
                      {GAME_ICON[entry.key] || "◍"}
                    </span>
                    {entry.name}
                  </span>
                  <span className="arcade-plate-meta">
                    {entry.seats.length > 1
                      ? `${entry.seats[0]}–${entry.seats[entry.seats.length - 1]} players`
                      : `${entry.seats[0]} players`}{" "}
                    · {entry.turn_seconds}s turn
                  </span>
                  <span className="arcade-plate-note">{theme.tagline}</span>
                </span>
                {active ? (
                  <span className="arcade-plate-check" aria-hidden>
                    <Check size={13} strokeWidth={3} />
                  </span>
                ) : (
                  <span className="arcade-plate-open" aria-hidden>
                    <Plus size={12} /> table
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="arcade-setup">
          {chosen && chosen.seats.length > 1 ? (
            <div className="arcade-seg" role="group" aria-label="Seats">
              {chosen.seats.map((count) => (
                <button
                  key={count}
                  onClick={() => setSeats(count)}
                  aria-pressed={seats === count}
                >
                  {count} seats
                </button>
              ))}
            </div>
          ) : (
            <span className="arcade-seat-empty">Two players</span>
          )}
          <div className="arcade-seg" role="group" aria-label="Who can see this room">
            <button onClick={() => setVisibility("private")} aria-pressed={visibility === "private"}>
              <span className="inline-flex items-center gap-1.5">
                <Lock size={12} aria-hidden /> Private
              </span>
            </button>
            <button onClick={() => setVisibility("public")} aria-pressed={visibility === "public"}>
              <span className="inline-flex items-center gap-1.5">
                <Globe2 size={12} aria-hidden /> Public
              </span>
            </button>
          </div>
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
            className="ios-btn arcade-create"
          >
            {busy ? (
              <Loader2 size={16} className="animate-spin" aria-hidden />
            ) : (
              <Plus size={16} aria-hidden />
            )}
            Create room
          </button>
        </div>
      </section>

      <section className="arcade-section" aria-label="Join with a code">
        <div className="arcade-section-head">
          <span className="arcade-section-title">
            <span className="inline-flex items-center gap-1.5">
              <Wifi size={12} aria-hidden /> Have an invitation?
            </span>
          </span>
          <span className="arcade-section-hint">A code, or paste the whole link</span>
        </div>
        <form
          className="arcade-invite"
          onSubmit={async (event) => {
            event.preventDefault();
            const value = codeFromLink(code);
            if (!value) return;
            const data = await call("/api/arcade/join", { code: value });
            if (data?.room?.code) {
              setCode("");
              openRoom(data.room.code);
            }
          }}
        >
          <label className="min-w-[10rem] flex-1">
            <span className="ios-caps block text-[10px] text-indigo-100/45">Room code</span>
            <input
              value={code}
              onChange={(event) => setCode(event.target.value.slice(0, 120))}
              onPaste={(event) => {
                const found = codeFromLink(event.clipboardData.getData("text"));
                if (found) {
                  event.preventDefault();
                  setCode(found);
                }
              }}
              placeholder="K7M2QX or a link"
              maxLength={120}
              className="arcade-code-input mt-1"
              aria-label="Room code"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
            />
          </label>
          <button
            type="submit"
            disabled={busy || codeFromLink(code).length < 4}
            className="ios-btn ios-btn-glass min-h-[44px]"
          >
            <LogIn size={16} aria-hidden /> Take a seat
          </button>
        </form>
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <RoomList
            title="Your tables"
            hint={lobby?.mine.length ? "Pick up where you stopped" : "Nothing running"}
            rows={lobby?.mine || []}
            empty="You have no open games. A new table takes one tap."
            onOpen={openRoom}
          />
          <RoomList
            title="Open to everyone"
            hint="Public rooms you can watch or join"
            rows={lobby?.public || []}
            empty="No public tables right now — be the first."
            onOpen={openRoom}
          />
        </div>
        <Leaderboards lobby={lobby} me={player.id} />
      </div>

      {lobby?.me ? (
        <div className="arcade-section" aria-label="Your card">
          <div className="arcade-section-head">
            <span className="arcade-section-title">Your player card</span>
            <span className="arcade-section-hint">rated tables only</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(GAME_THEME)
              .filter(([key]) => key !== "ludo")
              .map(([key, theme]) => {
                const row = (lobby.me?.stats || {})[key];
                return (
                  <div
                    key={key}
                    className="rounded-2xl border border-white/10 bg-white/[0.03] p-2.5"
                    style={{ borderColor: `${theme.accent}33` }}
                  >
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold">
                      <span aria-hidden>{GAME_ICON[key]}</span> {key}
                    </p>
                    <p className="mono mt-1 text-lg leading-none">{row?.rating ?? "—"}</p>
                    <p className="mt-1 text-[10px] text-indigo-100/45">
                      {row?.games ?? 0} played · {row?.wins ?? 0}W {row?.losses ?? 0}L{" "}
                      {row?.draws ?? 0}D
                    </p>
                  </div>
                );
              })}
          </div>
          <p className="mt-2 text-[10px] text-indigo-100/35">
            Ludo is unrated: chance should not move a number you care about.
          </p>
        </div>
      ) : null}
    </main>
  );
}

function Hero({
  kicker,
  title,
  subtitle,
  stats,
  live = "server-run tables",
  action,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  stats: { value: string; label: string }[];
  live?: string;
  action?: React.ReactNode;
}) {
  return (
    <section className="arcade-hero">
      <div className="arcade-hero-grid" aria-hidden />
      <div className="arcade-orb arcade-orb-a" aria-hidden />
      <div className="arcade-orb arcade-orb-b" aria-hidden />
      <div className="relative z-[1]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="arcade-kicker">
            <Gamepad2 size={12} aria-hidden /> {kicker}
          </span>
          <span className="flex items-center gap-2">
            <span className="arcade-live">
              <i aria-hidden /> {live}
            </span>
            {action}
          </span>
        </div>
        <h1 className="arcade-title">{title}</h1>
        <p className="arcade-sub">{subtitle}</p>
        <div className="arcade-stats">
          {stats.map((stat) => (
            <div key={stat.label} className="arcade-stat">
              <b>{stat.value}</b>
              <span>{stat.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RoomList({
  title,
  hint,
  rows,
  empty,
  onOpen,
}: {
  title: string;
  hint: string;
  rows: RoomRow[];
  empty: string;
  onOpen: (code: string) => void;
}) {
  return (
    <section className="arcade-section" aria-label={title}>
      <div className="arcade-section-head">
        <span className="arcade-section-title">
          <span className="inline-flex items-center gap-1.5">
            <Users size={12} aria-hidden /> {title}
          </span>
        </span>
        <span className="arcade-section-hint">{hint}</span>
      </div>
      {rows.length === 0 ? (
        <p className="arcade-empty">{empty}</p>
      ) : (
        <ul className="arcade-list">
          {rows.map((row) => {
            const theme = themeOf(row.game);
            return (
              <li key={row.code}>
                <button
                  onClick={() => onOpen(row.code)}
                  className="arcade-row w-full text-left"
                  style={{ "--accent-soft": theme.soft } as CSSProperties}
                >
                  <span className="arcade-row-icon" aria-hidden>
                    {GAME_ICON[row.game] || "🎮"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="arcade-row-title">
                      {row.game_name}
                      <span className="arcade-row-code">{row.code}</span>
                      <span className="arcade-status" data-state={row.status}>
                        {row.status === "playing" ? "live" : row.status}
                      </span>
                    </span>
                    <span className="arcade-row-meta block truncate">
                      {row.players.length ? row.players.join(" vs ") : "Empty table"}
                      {" · "}
                      {row.visibility}
                    </span>
                  </span>
                  <span className="arcade-section-hint hidden sm:inline">{row.turn_seconds}s</span>
                  <span
                    className="grid h-8 w-8 place-items-center rounded-full"
                    style={{ background: `${theme.accent}22`, color: theme.accent }}
                    aria-hidden
                  >
                    <ChevronRight size={16} />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function Leaderboards({ lobby, me }: { lobby: Lobby | null; me: number }) {
  const boards = lobby?.leaderboards || {};
  const games = Object.keys(boards);
  return (
    <section className="arcade-section" aria-label="Leaderboards">
      <div className="arcade-section-head">
        <span className="arcade-section-title">
          <span className="inline-flex items-center gap-1.5">
            <Trophy size={12} aria-hidden /> Leaderboards
          </span>
        </span>
        <span className="arcade-section-hint">rated · 2 players</span>
      </div>
      {games.length === 0 ? (
        <p className="arcade-empty">No rated games yet. Win one and this fills up.</p>
      ) : (
        <div className="arcade-podiums">
          {games.map((game) => (
            <div key={game} className="arcade-podium">
              <p className="arcade-podium-name">
                <span aria-hidden>{GAME_ICON[game]}</span>
                {boards[game].length ? boards[game][0].name : game}
              </p>
              <ol>
                {(boards[game] || []).slice(0, 5).map((row, index) => (
                  <li key={row.id} data-me={row.id === me}>
                    <span className="truncate">
                      <span className="arcade-medal" aria-hidden>
                        {["🥇", "🥈", "🥉"][index] || `${index + 1}.`}
                      </span>{" "}
                      {row.name}
                    </span>
                    <b>{row.rating}</b>
                  </li>
                ))}
                {boards[game].length === 0 ? <li>No results yet</li> : null}
              </ol>
            </div>
          ))}
        </div>
      )}
      <p className="mt-2 text-[10px] leading-4 text-indigo-100/35">
        Elo moves only in two-player Connect Four, Reversi and Tic-tac-toe rooms.
      </p>
    </section>
  );
}

const FALLBACK_GAMES: GameInfo[] = [
  { key: "checkers", name: "Checkers", seats: [2], turn_seconds: 75, summary: "Draughts with forced chains." },
  { key: "connect4", name: "Connect Four", seats: [2], turn_seconds: 60, summary: "Line up four discs." },
  { key: "ludo", name: "Ludo", seats: [2, 3, 4], turn_seconds: 45, summary: "Race four tokens home." },
  { key: "reversi", name: "Reversi", seats: [2], turn_seconds: 90, summary: "Flank and flip." },
  { key: "tictactoe", name: "Tic-tac-toe", seats: [2], turn_seconds: 45, summary: "Three in a row." },
];
