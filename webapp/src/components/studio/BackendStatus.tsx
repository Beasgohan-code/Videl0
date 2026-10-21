"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { CloudOff, LoaderCircle, RefreshCw, Server, X } from "lucide-react";
import { healthProblems } from "@/lib/health";

type Probe = {
  state: "ready" | "waking" | "down" | "skip";
  detail: string;
};

type Health = {
  ok?: boolean;
  code?: string;
  error?: string;
  hint?: string;
  bot_status?: string;
  database?: string;
  status?: string;
  degraded?: boolean;
  degraded_reasons?: string[];
  bot_error?: string | null;
};

async function probeBackend(wake: boolean): Promise<Probe> {
  try {
    const response = await fetch(`/api/health${wake ? "?wake=1" : ""}`, { cache: "no-store" });
    // Not signed in: the Owner gate owns that conversation, not this strip.
    if (response.status === 401 || response.status === 403) return { state: "skip", detail: "" };
    const body = (await response.json().catch(() => ({}))) as Health;
    if (response.ok) return { state: "ready", detail: "" };
    const waking = body.code === "BACKEND_WAKING" || response.headers.get("Retry-After") === "5";
    return {
      state: waking ? "waking" : "down",
      detail: body.hint || body.error || "The bot backend did not answer.",
    };
  } catch {
    return {
      state: "down",
      detail: "Could not reach the bot backend. Check your connection, then retry.",
    };
  }
}

/**
 * Warm-up strip for the Render backend.
 *
 * Render's free instance sleeps when idle, so the first request of a session
 * can take 20–50 seconds. Instead of surfacing a scary "backend error", the app
 * wakes it in the background, says what is happening, and retries on its own.
 */
export function BackendStatus() {
  const [state, setState] = useState<"checking" | "waking" | "down" | "ready" | "hidden">("checking");
  const [detail, setDetail] = useState("");
  const [manual, setManual] = useState(0);
  const lastCheck = useRef(0);

  const run = useCallback(async (wake: boolean) => {
    lastCheck.current = Date.now();
    const result = await probeBackend(wake);
    if (result.state === "skip") {
      setState("hidden");
      return "skip" as const;
    }
    if (result.state === "ready") {
      setState("ready");
      setDetail("");
      return "ready" as const;
    }
    setState(result.state);
    setDetail(result.detail);
    return result.state;
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const loop = async (wake: boolean, tries: number) => {
      const result = await run(wake);
      if (cancelled) return;
      // Keep waking silently: 8 × 5 s covers a typical cold start without
      // hammering the backend once it is up.
      if (result === "waking" && tries < 8) {
        timer = setTimeout(() => void loop(true, tries + 1), 5000);
      }
    };

    // A manual retry restarts this effect (see `manual` below) and skips
    // straight to the wake path.

    // The first pass is a plain probe; a manual retry goes straight to wake.
    void loop(manual > 0, 0);

    // Returning to the tab after a while is exactly when Render has slept.
    const onVisible = () => {
      if (document.visibilityState === "visible" && Date.now() - lastCheck.current > 60000)
        void loop(true, 0);
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [run, manual]);

  if (state === "checking" || state === "ready" || state === "hidden") return null;

  const waking = state === "waking";
  return (
    <div role="status" className={`backend-strip ${waking ? "backend-strip-waking" : "backend-strip-down"}`}>
      <span className="backend-strip-icon">
        {waking ? <LoaderCircle size={15} className="animate-spin" /> : <CloudOff size={15} />}
      </span>
      <p className="min-w-0 flex-1 text-[11px] leading-5">
        <b className="font-semibold">{waking ? "Starting the bot backend" : "Bot backend unavailable"}</b>
        <span className="ml-2 text-white/60">
          {waking
            ? "Render is waking up — about a minute at most. Everything else keeps working."
            : detail}
        </span>
      </p>
      <button
        type="button"
        onClick={() => setManual((value) => value + 1)}
        className="backend-strip-action"
        aria-label="Retry backend connection"
      >
        <RefreshCw size={12} aria-hidden /> Retry
      </button>
      <button
        type="button"
        onClick={() => setState("hidden")}
        aria-label="Dismiss backend notice"
        className="backend-strip-close"
      >
        <X size={13} aria-hidden />
      </button>
    </div>
  );
}

/** Small inline chip used inside Settings. */
export function BackendStatusChip({ health }: { health: Health | null }) {
  if (!health) return <span className="ios-pill">Unknown</span>;
  if (health.ok) {
    const problems = healthProblems(health);
    // The API answering is not the bot working: say which is true.
    if (health.bot_status && health.bot_status !== "online")
      return (
        <span className="ios-pill ios-pill-amber" title={problems.join(" · ")}>
          Bot {health.bot_status === "starting" ? "starting" : "offline"} · API up
        </span>
      );
    if (health.database === "disconnected")
      return <span className="ios-pill ios-pill-amber">Database reconnecting</span>;
    if (problems.length)
      return <span className="ios-pill ios-pill-amber" title={problems.join(" · ")}>Running with issues</span>;
    return (
      <span className="ios-pill ios-pill-green">
        <Server size={11} /> Online
      </span>
    );
  }
  return (
    <span className="ios-pill ios-pill-amber">
      {health.code === "BACKEND_WAKING" ? "Starting…" : "Offline"}
    </span>
  );
}
