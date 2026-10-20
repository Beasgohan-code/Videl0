import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Owner-only backend health for the status strip and the Settings panel.
 * It returns only what the bot's own /health returns (status, bot status,
 * uptime, watchdog) plus a plain-language diagnosis — no secrets, no actions.
 * Long timeouts absorb a Render cold start instead of showing a false
 * "backend unreachable".
 */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const url = new URL(req.url);
  const wake = url.searchParams.get("wake") === "1";
  const result = await callBackend("/health", {}, { timeoutMs: wake ? 28000 : 20000, attempts: 2 });
  const body = result.payload || {};
  if (!result.ok) {
    return Response.json(
      {
        status: "error",
        service: "Videl",
        code: result.payload.code || (result.code === "WAKING" ? "BACKEND_WAKING" : "BACKEND_UNREACHABLE"),
        error: body.error || result.hint || "Backend health endpoint is unreachable",
        hint: result.hint,
        retry_in: result.code === "WAKING" ? 5 : null,
      },
      { status: 503, headers: { "Cache-Control": "no-store", "Retry-After": result.code === "WAKING" ? "5" : "30" } },
    );
  }
  return Response.json(
    {
      status: body.status || "ok",
      service: body.service || "videl-render-backend",
      bot_status: body.bot_status || "unknown",
      database: body.database || "unknown",
      uptime: body.uptime ?? null,
      watchdog: body.watchdog ?? null,
      latency_ms: result.ms,
      attempts: result.attempts,
    },
    { status: 200, headers: { "Cache-Control": "no-store" } },
  );
}
