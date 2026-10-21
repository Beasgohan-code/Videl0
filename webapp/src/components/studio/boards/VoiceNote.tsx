"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, Send, Square, Trash2 } from "lucide-react";

/**
 * Voice notes.
 *
 * The honest fallback for the call that cannot happen: a webview that refuses
 * the microphone, a mobile network that blocks a peer connection, or two
 * people who are simply never online together. Recording is capped at twenty
 * seconds and one take at a time — a voice note is a sentence, not a podcast.
 *
 * The microphone permission is the same one a call would ask for, so this is
 * offered everywhere in the room rather than only after a failure: somebody
 * who knows their network will not carry a call should not have to try it and
 * fail first.
 */

const LIMIT = 20;

function pick(recorder: MediaRecorder): string {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  const found = options.find((type) => MediaRecorder.isTypeSupported?.(type));
  return found || recorder.mimeType || "audio/webm";
}

export function VoiceNote({
  disabled,
  onSend,
}: {
  disabled?: boolean;
  onSend: (payload: { data: string; mime: string; seconds: number }) => Promise<unknown>;
}) {
  const [state, setState] = useState<"idle" | "recording" | "review" | "sending" | "denied">("idle");
  const [seconds, setSeconds] = useState(0);
  const [draft, setDraft] = useState<{ data: string; mime: string; seconds: number; url: string } | null>(null);
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const started = useRef(0);

  const release = useCallback(() => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    recorder.current?.stream.getTracks().forEach((track) => track.stop());
    recorder.current = null;
    chunks.current = [];
  }, []);

  useEffect(() => release, [release]);

  const stop = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  async function record() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("denied");
      setError("This browser cannot record audio.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const instance = new MediaRecorder(stream);
      chunks.current = [];
      instance.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      instance.onstop = () => {
        const elapsed = Math.min(LIMIT, Math.max(1, (Date.now() - started.current) / 1000));
        const blob = new Blob(chunks.current, { type: pick(instance) });
        release();
        if (!blob.size) {
          setState("idle");
          setError("That take was empty. Try again a little louder.");
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const data = String(reader.result || "").split(",")[1] || "";
          setDraft({ data, mime: blob.type || "audio/webm", seconds: Math.round(elapsed * 10) / 10, url: URL.createObjectURL(blob) });
          setSeconds(Math.round(elapsed * 10) / 10);
          setState("review");
        };
        reader.readAsDataURL(blob);
      };
      recorder.current = instance;
      started.current = Date.now();
      setSeconds(0);
      setState("recording");
      instance.start();
      timer.current = window.setInterval(() => {
        const elapsed = (Date.now() - started.current) / 1000;
        setSeconds(Math.round(elapsed * 10) / 10);
        if (elapsed >= LIMIT) stop();
      }, 100);
    } catch (failure) {
      const name = (failure as { name?: string })?.name || "";
      setState("denied");
      setError(
        name === "NotAllowedError"
          ? "The microphone was refused. Voice notes need it once, then they work."
          : "No microphone was available.",
      );
    }
  }

  async function send() {
    if (!draft) return;
    setState("sending");
    try {
      await onSend({ data: draft.data, mime: draft.mime, seconds: draft.seconds });
      URL.revokeObjectURL(draft.url);
      setDraft(null);
      setState("idle");
      setSeconds(0);
    } catch (failure) {
      setError((failure as Error).message || "That note did not send.");
      setState("review");
    }
  }

  function discard() {
    if (draft) URL.revokeObjectURL(draft.url);
    setDraft(null);
    setSeconds(0);
    setState("idle");
    setError("");
  }

  return (
    <div className="voice-note" data-state={state}>
      {state === "idle" || state === "denied" ? (
        <button type="button" className="voice-note-btn" onClick={() => void record()} disabled={disabled}>
          <Mic size={13} aria-hidden /> Leave a voice note
        </button>
      ) : null}

      {state === "recording" ? (
        <button type="button" className="voice-note-btn" data-live="true" onClick={stop}>
          <Square size={12} aria-hidden /> Stop · {seconds.toFixed(1)}s
          <span className="voice-note-meter" aria-hidden>
            <i style={{ width: `${Math.min(100, (seconds / LIMIT) * 100)}%` }} />
          </span>
        </button>
      ) : null}

      {state === "review" && draft ? (
        <>
          <audio className="voice-note-audio" src={draft.url} controls preload="metadata" />
          <button type="button" className="voice-note-btn" data-send="true" onClick={() => void send()}>
            <Send size={12} aria-hidden /> Send {draft.seconds.toFixed(1)}s
          </button>
          <button type="button" className="voice-note-btn" onClick={discard} aria-label="Discard this recording">
            <Trash2 size={12} aria-hidden />
          </button>
        </>
      ) : null}

      {state === "sending" ? (
        <span className="voice-note-btn" data-busy="true">
          <Loader2 size={12} className="animate-spin" aria-hidden /> Sending…
        </span>
      ) : null}

      {error ? <span className="voice-note-error">{error}</span> : null}
      {state === "recording" && !error ? (
        <span className="voice-note-hint">Up to {LIMIT}s. Tap stop when you are done.</span>
      ) : null}
    </div>
  );
}

/** A received note: fetched on demand so an unplayed clip costs nothing. */
export function VoiceClip({ id, seconds, mine }: { id: string; seconds: number; mine: boolean }) {
  const [src, setSrc] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true);
    try {
      const response = await fetch(`/api/arcade/clip/${encodeURIComponent(id)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("That note has expired.");
      const blob = await response.blob();
      setSrc(URL.createObjectURL(blob));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="voice-clip" data-mine={mine}>
      {src ? (
        <audio src={src} controls autoPlay preload="metadata" className="voice-clip-audio" />
      ) : (
        <button type="button" className="voice-clip-play" onClick={() => void load()} disabled={busy}>
          {busy ? <Loader2 size={12} className="animate-spin" aria-hidden /> : "▶"}
          <span>Voice note · {seconds.toFixed(1)}s</span>
        </button>
      )}
      {error ? <span className="voice-clip-error">{error}</span> : null}
    </span>
  );
}
