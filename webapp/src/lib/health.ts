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
};

/** What is not working, in the backend's own words. Empty means healthy. */
export function healthProblems(health: HealthLike | null | undefined): string[] {
  if (!health?.ok) return [];
  const reported = Array.isArray(health.degraded_reasons)
    ? health.degraded_reasons.filter((reason) => typeof reason === "string" && reason.trim())
    : [];
  if (reported.length) return reported;
  // A backend deployed before `degraded_reasons` existed still reports the two
  // facts that matter, so fall back to reading those rather than guessing "ok".
  const inferred: string[] = [];
  if (health.bot_status && health.bot_status !== "online") inferred.push(`Telegram bot is ${health.bot_status}`);
  if (health.database === "disconnected") inferred.push("MongoDB is disconnected");
  return inferred;
}

/** One-line status for the backend card. Never claims more than was measured. */
export function healthCaption(health: HealthLike | null | undefined): string {
  if (!health?.ok) return "Health check unavailable";
  const parts = [`API reachable`, `bot ${health.bot_status || "status unknown"}`];
  if (health.database) parts.push(`DB ${health.database}`);
  if (typeof health.uptime === "number") {
    parts.push(`uptime ${Math.floor(health.uptime / 3600)}h ${Math.floor((health.uptime % 3600) / 60)}m`);
  }
  if (typeof health.bot_online_at === "number" && health.bot_status === "online") {
    parts.push(`bot up since ${new Date(health.bot_online_at * 1000).toLocaleTimeString()}`);
  }
  return parts.join(" · ");
}

export function backendTone(health: HealthLike | null | undefined): "good" | "warn" | "bad" {
  if (!health?.ok) return "bad";
  if (healthProblems(health).length) return "warn";
  return "good";
}
