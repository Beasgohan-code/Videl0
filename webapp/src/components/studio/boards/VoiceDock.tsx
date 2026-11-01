"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpRight,
  Headphones,
  Loader2,
  Mic,
  MicOff,
  PhoneOff,
  Volume2,
  VolumeX,
  Waves,
} from "lucide-react";
import { RoomVoice, VOICE_REACH, canVoice, type VoiceSignal, type VoiceState } from "@/lib/voice";
import type { RoomEvent, Seat } from "@/lib/arcade";

/**
 * The voice bar in a live room.
 *
 * This is not a settings panel: it is the table's call strip, sitting under the
 * board the way a speakerphone sits on a real table. Joining costs one press;
 * speaking is push-to-talk (hold the button or the space bar) because an open
 * mic in a four-seat room is a bug, not a feature. Anyone in the call is drawn
 * as an avatar with a ring that lights up when they speak, so the table can see
 * who is talking even with the volume down.
 *
 * Presence is a heartbeat: the bar posts `action: "voice"` every few seconds
 * while connected, so a closed tab leaves the call by itself instead of
 * haunting the room. Signals travel on the room's own event stream
 * (`action: "rtc"`), which means voice needs no second connection and stops
 * exactly when the room does.
 */

/**
 * The page to leave the webview for. Telegram opens links inside itself by
 * default, so the escape hatch is an ordinary anchor with a real URL: a press
 * that lands in Chrome is the whole point of showing it.
 */
function pageUrl(): string {
  if (typeof window === "undefined") return "/";
  return window.location.href;
}

const HEARTBEAT_MS = 12_000;

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
}

export function VoiceDock({
  room,
  seat,
  events,
  send,
  onSpeaking,
  muted,
  onMute,
}: {
  room: {
    code: string;
    seats: Seat[];
    you: { seat: number | null; member: boolean };
    status: string;
    voice?: number[];
  };
  seat: number | null;
  events: RoomEvent[];
  send: (payload: Record<string, unknown>) => Promise<unknown>;
  onSpeaking: (users: number[]) => void;
  muted: boolean;
  onMute: (muted: boolean) => void;
}) {
  const [state, setState] = useState<VoiceState>({ status: "off" });
  const [peers, setPeers] = useState<Record<number, string>>({});
  const [deafened, setDeafened] = useState(false);
  const [talkers, setTalkers] = useState<number[]>([]);
  const voice = useRef<RoomVoice | null>(null);
  const seen = useRef(new Set<number>());
  const audio = useRef(new Map<number, HTMLAudioElement>());
  const supported = useMemo(canVoice, []);

  const post = useCallback(
    (signal: VoiceSignal) => {
      void send({ action: "rtc", kind: signal.kind, to: signal.to, data: signal.data });
    },
    [send],
  );

  const active =
    state.status === "ready" || state.status === "live" || state.status === "connecting";

  /* ── presence ──────────────────────────────────────────────────────────────
     One heartbeat now, then every HEARTBEAT_MS. Leaving — by button, by tab
     close, by unmount — posts `on: false` so the room does not have to wait
     out the window. */
  useEffect(() => {
    if (!active || seat === null) return;
    // Straight to the route, not through the room's action pipeline: a
    // heartbeat should not disable the board's buttons or refetch the lobby.
    const beat = () =>
      void fetch(`/api/arcade/room/${encodeURIComponent(room.code)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "voice", on: true }),
        cache: "no-store",
        keepalive: true,
      }).catch(() => {});
    beat();
    const timer = window.setInterval(beat, HEARTBEAT_MS);
    const leave = () => {
      try {
        navigator.sendBeacon?.(
          `/api/arcade/room/${encodeURIComponent(room.code)}`,
          new Blob([JSON.stringify({ action: "voice", on: false })], {
            type: "application/json",
          }),
        );
      } catch {
        /* a closed tab is allowed to fail quietly */
      }
    };
    window.addEventListener("pagehide", leave);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pagehide", leave);
      void fetch(`/api/arcade/room/${encodeURIComponent(room.code)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "voice", on: false }),
        cache: "no-store",
        keepalive: true,
      }).catch(() => {});
    };
  }, [active, room.code, seat]);

  /* Every signal that names me is fed to the connection; everything else in
     the feed (chat, moves) is not the dock's business. */
  useEffect(() => {
    if (state.status === "off" || state.status === "asking" || state.status === "blocked") return;
    const engine = voice.current;
    if (!engine) return;
    for (const event of events) {
      if (event.kind !== "rtc" || seen.current.has(event.seq) || event.user === null) continue;
      seen.current.add(event.seq);
      try {
        const signal = JSON.parse(event.text) as {
          to: number;
          kind: VoiceSignal["kind"];
          data: Record<string, unknown>;
        };
        if (Number(signal.to) !== seat && seat !== null) continue;
        void engine.receive({ kind: signal.kind, to: signal.to, data: signal.data }, event.user);
      } catch {
        /* an event that is not a signal is ignored, never thrown */
      }
    }
  }, [events, seat, state.status]);

  useEffect(() => {
    return () => {
      voice.current?.hangUp();
      audio.current.forEach((element) => element.pause());
    };
  }, []);

  /* People who joined after the call started still need an offer. */
  useEffect(() => {
    const engine = voice.current;
    if (!engine || (state.status !== "ready" && state.status !== "live")) return;
    if (seat === null) return;
    for (const entry of room.seats) {
      if (entry.seat === seat) continue;
      if (!entry.online) continue;
      if (engine.live().includes(entry.user)) continue;
      void engine.offerTo(entry.user);
    }
    // Deliberately keyed to the seat list, not to the audio state: this is
    // "who is at the table", and a new chair is the only thing that matters.
  }, [room.seats, seat, state.status]);

  const start = useCallback(async () => {
    if (seat === null) return;
    const engine = new RoomVoice(seat, {
      send: post,
      onState: setState,
      onRemote: (peer, stream) => {
        const existing = audio.current.get(peer);
        if (!stream) {
          existing?.pause();
          audio.current.delete(peer);
          setPeers((current) => {
            const next = { ...current };
            delete next[peer];
            return next;
          });
          return;
        }
        const element = existing || new Audio();
        element.srcObject = stream;
        element.autoplay = true;
        element.muted = deafened;
        void element.play().catch(() => {});
        audio.current.set(peer, element);
        setPeers((current) => ({ ...current, [peer]: "live" }));
      },
    });
    voice.current = engine;
    const ready = await engine.start();
    if (!ready) return;
    onMute(true);
  }, [deafened, onMute, post, seat]);

  const stop = useCallback(() => {
    voice.current?.hangUp();
    voice.current = null;
    audio.current.forEach((element) => element.pause());
    audio.current.clear();
    setPeers({});
    setState({ status: "off" });
    setTalkers([]);
    onSpeaking([]);
  }, [onSpeaking]);

  const talk = useCallback(
    (on: boolean) => {
      const engine = voice.current;
      if (!engine || !engine.microphone()) return;
      engine.setMuted(!on);
      onMute(!on);
      const me = room.seats.find((entry) => entry.seat === seat)?.user;
      const next = on && me ? [me] : [];
      setTalkers(next);
      onSpeaking(next);
    },
    [onMute, onSpeaking, room.seats, seat],
  );

  useEffect(() => {
    if (state.status !== "ready" && state.status !== "live") return;
    function down(event: KeyboardEvent) {
      if (event.code !== "Space" || event.repeat) return;
      const target = event.target as HTMLElement | null;
      if (target && /input|textarea|button|select/i.test(target.tagName)) return;
      event.preventDefault();
      talk(true);
    }
    function up(event: KeyboardEvent) {
      if (event.code !== "Space") return;
      talk(false);
    }
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [state.status, talk]);

  if (seat === null || room.status === "done") return null;

  const connected = Object.keys(peers).length;
  const others = room.seats.filter((entry) => entry.seat !== seat && entry.online);
  const inCall = (room.voice || [])
    .map((user) => room.seats.find((entry) => entry.user === user))
    .filter((entry): entry is Seat => Boolean(entry));

  if (!supported) {
    return (
      <div className="voice-bar" data-state="blocked">
        <span className="voice-note">
          <Waves size={14} aria-hidden /> This browser cannot carry live voice. Table talk still works.
        </span>
      </div>
    );
  }

  return (
    <div
      className="voice-bar"
      data-state={active ? state.status : "off"}
      data-live={active && !muted ? "true" : "false"}
    >
      <div className="voice-call">
        <span className="voice-call-label">
          {active ? (
            <>
              <Waves size={13} aria-hidden /> Table talk
            </>
          ) : (
            <>
              <Headphones size={13} aria-hidden /> Table talk
            </>
          )}
        </span>

        <div className="voice-avatars" aria-label="People in the call">
          {!inCall.length ? (
            <img className="voice-art" src="/arcade/voice.jpg" alt="" aria-hidden decoding="async" />
          ) : null}
          {inCall.length ? (
            inCall.slice(0, 4).map((entry) => {
              const talking = talkers.includes(entry.user);
              return (
                <span
                  key={entry.user}
                  className="voice-avatar"
                  data-talking={talking}
                  data-me={entry.seat === seat}
                  title={`${entry.name}${talking ? " is speaking" : " is on voice"}`}
                >
                  {initials(entry.name)}
                  {talking ? (
                    <span className="voice-wave" aria-hidden>
                      <i />
                      <i />
                      <i />
                    </span>
                  ) : null}
                </span>
              );
            })
          ) : (
            <span className="voice-empty">Nobody in the call yet</span>
          )}
          {inCall.length > 4 ? <span className="voice-more">+{inCall.length - 4}</span> : null}
        </div>

        {active ? (
          <span className="voice-peers">
            <span className="voice-dot" data-on={connected > 0} aria-hidden />
            {connected ? `${connected} connected` : "connecting…"}
          </span>
        ) : null}
      </div>

      <div className="voice-controls">
        {!active ? (
          <button
            onClick={() => void start()}
            className="ios-btn ios-btn-glass voice-join"
            data-invite={others.length > 0}
            disabled={state.status === "asking"}
          >
            {state.status === "asking" ? (
              <Loader2 size={14} className="animate-spin" aria-hidden />
            ) : (
              <Headphones size={14} aria-hidden />
            )}
            {state.status === "asking"
              ? "Asking for the mic…"
              : inCall.length
                ? `Join ${inCall.length} on voice`
                : "Start voice"}
          </button>
        ) : (
          <>
            <button
              type="button"
              className="voice-talk"
              data-talking={!muted}
              onPointerDown={(event) => {
                event.preventDefault();
                talk(true);
              }}
              onPointerUp={() => talk(false)}
              onPointerLeave={() => talk(false)}
              onPointerCancel={() => talk(false)}
              aria-label="Hold to talk"
            >
              {muted ? <Mic size={15} aria-hidden /> : <Mic size={15} aria-hidden />}
              <span>{muted ? "Hold to talk" : "Talking…"}</span>
            </button>

            <button
              className="voice-icon"
              onClick={() => {
                const next = !deafened;
                setDeafened(next);
                audio.current.forEach((element) => (element.muted = next));
              }}
              aria-pressed={deafened}
              aria-label={deafened ? "Unmute the table" : "Mute the table"}
              title={deafened ? "Unmute the table" : "Mute the table"}
            >
              {deafened ? <VolumeX size={15} aria-hidden /> : <Volume2 size={15} aria-hidden />}
            </button>

            <button className="voice-icon" onClick={stop} aria-label="Leave voice" title="Leave voice">
              <PhoneOff size={15} aria-hidden />
            </button>
          </>
        )}
      </div>

      {!active && others.length ? (
        <span className="voice-invite">
          {others[0].name} is at the table — say hello out loud. Hold space to talk.
        </span>
      ) : null}
      {!active && !others.length ? (
        <span className="voice-invite" data-quiet="true">
          Voice opens when a second chair fills.
        </span>
      ) : null}

      {state.status === "blocked" || state.status === "unsupported" ? (
        <p className="voice-error" role="status">
          <MicOff size={12} aria-hidden /> {state.error}
          <a className="voice-escape" href={pageUrl()} target="_blank" rel="noreferrer">
            Open in a browser <ArrowUpRight size={11} aria-hidden />
          </a>
        </p>
      ) : null}

      {active ? <p className="voice-reach">{VOICE_REACH}</p> : null}

      {talkers.length && active ? <span className="sr-only">You are speaking</span> : null}
    </div>
  );
}

/** The seat ring reads this; exported so a seat can be lit without the dock. */
export function isSpeaking(talkers: number[], seat: Seat | undefined): boolean {
  return Boolean(seat && talkers.includes(seat.user));
}
