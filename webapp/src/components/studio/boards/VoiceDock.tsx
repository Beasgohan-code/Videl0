"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Headphones, Loader2, Mic, MicOff, PhoneOff, Volume2, VolumeX, Waves } from "lucide-react";
import { RoomVoice, canVoice, type VoiceSignal, type VoiceState } from "@/lib/voice";
import type { RoomEvent, Seat } from "@/lib/arcade";

/**
 * The voice dock in a live room.
 *
 * Push-to-talk, not an open mic: joining a table should not put somebody's
 * kitchen into four strangers' speakers. Hold the button (or press and hold
 * the space bar) to speak; the ring around your seat lights up so the table can
 * see who is talking even with the volume down.
 *
 * The signals travel on the room's own event stream (`action: "rtc"`), so voice
 * needs no second connection and stops working exactly when the room does.
 */
export function VoiceDock({
  room,
  seat,
  events,
  send,
  onSpeaking,
  muted,
  onMute,
}: {
  room: { code: string; seats: Seat[]; you: { seat: number | null; member: boolean }; status: string };
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
        const signal = JSON.parse(event.text) as { to: number; kind: VoiceSignal["kind"]; data: Record<string, unknown> };
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
    if (!engine || state.status !== "ready" && state.status !== "live") return;
    if (seat === null) return;
    const seated = room.seats.filter((entry) => entry.user !== undefined);
    for (const entry of seated) {
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

  const active = state.status === "ready" || state.status === "live" || state.status === "connecting";
  const connected = Object.keys(peers).length;

  if (!supported) {
    return (
      <div className="voice-dock" data-state="blocked">
        <span className="voice-note">
          <Waves size={14} aria-hidden /> This browser cannot carry live voice. Table talk still works.
        </span>
      </div>
    );
  }

  return (
    <div className="voice-dock" data-state={state.status} data-live={active && !muted ? "true" : "false"}>
      {!active ? (
        <button onClick={() => void start()} className="ios-btn ios-btn-glass voice-join" disabled={state.status === "asking"}>
          {state.status === "asking" ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Headphones size={14} aria-hidden />}
          {state.status === "asking" ? "Asking for the mic…" : "Start voice"}
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
            {muted ? <Mic size={15} aria-hidden /> : <Mic size={15} className="voice-pulse" aria-hidden />}
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

          <span className="voice-peers">
            <span className="voice-dot" data-on={connected > 0} aria-hidden />
            {connected ? `${connected} on voice` : "nobody else yet"}
          </span>

          <button className="voice-icon" onClick={stop} aria-label="Leave voice" title="Leave voice">
            <PhoneOff size={15} aria-hidden />
          </button>
        </>
      )}

      {state.status === "blocked" || state.status === "unsupported" ? (
        <p className="voice-error" role="status">
          <MicOff size={12} aria-hidden /> {state.error}
        </p>
      ) : null}

      {talkers.length && active ? <span className="sr-only">You are speaking</span> : null}
    </div>
  );
}

/** The seat ring reads this; exported so a seat can be lit without the dock. */
export function isSpeaking(talkers: number[], seat: Seat | undefined): boolean {
  return Boolean(seat && talkers.includes(seat.user));
}
