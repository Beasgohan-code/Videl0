/**
 * Tiny synth for the arcade.
 *
 * A game board with no sound feels like a spreadsheet. This is not a soundtrack
 * and it loads no files: a handful of short oscillator envelopes, made on the
 * first gesture the browser allows, so the whole thing costs a few hundred
 * bytes instead of a megabyte of samples. Every cue is short enough to fire
 * between two moves without stepping on the next one.
 *
 * Sound is opt-out and remembered per device. Haptics are best-effort: a
 * desktop simply has no vibration motor and nothing here pretends otherwise.
 */

export type Cue = "move" | "capture" | "check" | "win" | "lose" | "join" | "voice";

const KEY = "videl.arcade.sound";

let context: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!context) context = new Ctor();
  if (context.state === "suspended") void context.resume();
  return context;
}

export function soundOn(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setSoundOn(on: boolean): void {
  try {
    window.localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* a private window can refuse storage; sound still works this session */
  }
}

/** One shaped note: frequency, start offset, length, gain. */
function note(ctx: AudioContext, frequency: number, at: number, length: number, gain: number, type: OscillatorType = "sine") {
  const oscillator = ctx.createOscillator();
  const envelope = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, ctx.currentTime + at);
  envelope.gain.setValueAtTime(0.0001, ctx.currentTime + at);
  envelope.gain.exponentialRampToValueAtTime(gain, ctx.currentTime + at + 0.012);
  envelope.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + at + length);
  oscillator.connect(envelope).connect(ctx.destination);
  oscillator.start(ctx.currentTime + at);
  oscillator.stop(ctx.currentTime + at + length + 0.02);
}

const CUES: Record<Cue, (ctx: AudioContext) => void> = {
  move: (ctx) => note(ctx, 392, 0, 0.07, 0.05, "triangle"),
  capture: (ctx) => {
    note(ctx, 196, 0, 0.1, 0.07, "square");
    note(ctx, 147, 0.03, 0.12, 0.05, "triangle");
  },
  check: (ctx) => {
    note(ctx, 660, 0, 0.09, 0.05, "triangle");
    note(ctx, 880, 0.09, 0.1, 0.045, "triangle");
  },
  win: (ctx) => [523, 659, 784, 1047].forEach((hz, index) => note(ctx, hz, index * 0.085, 0.22, 0.055, "triangle")),
  lose: (ctx) => [392, 330, 262].forEach((hz, index) => note(ctx, hz, index * 0.1, 0.26, 0.045, "sine")),
  join: (ctx) => {
    note(ctx, 588, 0, 0.07, 0.035, "triangle");
    note(ctx, 784, 0.07, 0.08, 0.03, "triangle");
  },
  voice: (ctx) => note(ctx, 880, 0, 0.05, 0.028, "sine"),
};

export function cue(name: Cue, enabled = soundOn()): void {
  if (!enabled) return;
  const ctx = audio();
  if (!ctx) return;
  try {
    CUES[name](ctx);
  } catch {
    /* an audio context that refuses is not worth an error boundary */
  }
}

export function haptic(pattern: number | number[] = 12): void {
  if (typeof navigator === "undefined") return;
  // W3C's Vibration API types the pattern as one number or a list; the DOM
  // lib here only declares the iterable form, hence the cast.
  const device = navigator as unknown as { vibrate?: (pattern: number | number[]) => boolean };
  try {
    device.vibrate?.(pattern);
  } catch {
    /* no motor, no problem */
  }
}

/**
 * Which cue a room change deserves, from the room alone: the newest state is
 * the truth, so a reload that lands mid-game is silent while a real capture
 * still thuds.
 */
export function cueFor(room: {
  status: string;
  winner?: number | "draw" | null;
  you?: { seat: number | null };
  state: Record<string, unknown>;
}): Cue | null {
  const last = room.state.last as { capture?: boolean; check?: boolean; mate?: boolean } | null;
  if (room.status === "done") {
    if (room.winner === "draw") return "lose";
    const mine = room.you?.seat ?? null;
    return room.winner === mine ? "win" : "lose";
  }
  if (!last) return null;
  if (last.mate || last.check) return "check";
  if (last.capture) return "capture";
  return "move";
}
