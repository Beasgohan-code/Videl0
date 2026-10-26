/**
 * Reading `/api/health` out loud.
 *
 * A reachable backend is not a working bot. The health payload separates the
 * two — `status: "ok"` keeps uptime monitors calm while `degraded` names what
 * is not running — so the panel can say *why* instead of only *that*.
 */
export type HealthLike = {
  ok?: boolean;
  status?: string;
  bot_status?: string;
  database?: string;
  service?: string;
  uptime?: number;
  degraded?: boolean;
  degraded_reasons?: string[];
  bot_error?: string | null;
  bot_online_at?: number | null;
  bot_attempts?: number | null;
  assistant?: { configured?: boolean; ready?: boolean; state?: string };
  /** Round trip to MongoDB, measured separately from the HTTP API. */
  db?: { p95_ms?: number | null; samples?: number; connected?: boolean; last_ms?: number } | null;
};

/** What is not working, in the backend's own words. Empty means healthy. */
export function healthProblems(health: HealthLike | null | undefined): string[] {
  if (!health?.ok) return [];
  const reported = Array.isArray(health.degraded_reasons)
    ? health.degraded_reasons.filter((reason) => typeof reason === "string" && reason.trim())
    : [];
  const assistantProblem = health.assistant?.configured && !health.assistant.ready
    ? `Telegram voice assistant is ${health.assistant.state || "not connected"}`
    : "";
  if (reported.length) {
    return assistantProblem && !reported.includes(assistantProblem)
      ? [...reported, assistantProblem]
      : reported;
  }
  // A backend deployed before `degraded_reasons` existed still reports the two
  // facts that matter, so fall back to reading those rather than guessing "ok".
  const inferred: string[] = [];
  if (health.bot_status && health.bot_status !== "online") inferred.push(`Telegram bot is ${health.bot_status}`);
  if (health.database === "disconnected") inferred.push("MongoDB is disconnected");
  if (assistantProblem) inferred.push(assistantProblem);
  return inferred;
}

/** One-line status for the backend card. Never claims more than was measured. */
export function healthCaption(health: HealthLike | null | undefined): string {
  if (!health?.ok) return "Health check unavailable";
  const parts = [`API reachable`, `bot ${health.bot_status || "status unknown"}`];
  if (health.database) parts.push(`DB ${health.database}`);
  if (health.assistant?.configured) {
    parts.push(`voice assistant ${health.assistant.ready ? "connected" : health.assistant.state || "not ready"}`);
  }
  if (typeof health.uptime === "number") {
    parts.push(`uptime ${Math.floor(health.uptime / 3600)}h ${Math.floor((health.uptime % 3600) / 60)}m`);
  }
  if (typeof health.bot_online_at === "number" && health.bot_status === "online") {
    parts.push(`bot up since ${new Date(health.bot_online_at * 1000).toLocaleTimeString()}`);
  }
  return parts.join(" · ");
}

/**
 * Latency in the backend's own words. Two numbers, because "the panel is slow"
 * has two very different causes: our code, or the database under it.
 */
export function latencyCaption(health: HealthLike | null | undefined): string {
  if (!health?.ok) return "";
  const db = health.db;
  const parts: string[] = [];
  if (db) {
    parts.push(db.connected === false
      ? "MongoDB not answering"
      : db.p95_ms != null ? `MongoDB ${db.p95_ms} ms p95` : "MongoDB not measured yet");
  }
  return parts.join(" · ");
}

export function backendTone(health: HealthLike | null | undefined): "good" | "warn" | "bad" {
  if (!health?.ok) return "bad";
  if (healthProblems(health).length) return "warn";
  return "good";
}
