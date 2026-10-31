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
  const apiTelemetry = body.api && typeof body.api === "object"
    ? body.api as Record<string, unknown>
    : null;
  const assistant = body.assistant && typeof body.assistant === "object"
    ? body.assistant as Record<string, unknown>
    : null;
  const downloader = body.media_downloaders && typeof body.media_downloaders === "object"
    ? body.media_downloaders as Record<string, unknown>
    : null;
  const shruti = downloader?.shruti && typeof downloader.shruti === "object"
    ? downloader.shruti as Record<string, unknown>
    : null;
  const fallbacks = Array.isArray(downloader?.fallbacks) ? downloader.fallbacks : [];
  return Response.json(
    {
      status: body.status || "ok",
      service: body.service || "videl-render-backend",
      bot_status: body.bot_status || "unknown",
      database: body.database === "connected" || body.database === "disconnected" ? body.database : "unknown",
      assistant: assistant ? {
        configured: assistant.configured === true,
        ready: assistant.ready === true,
        state: typeof assistant.state === "string" ? assistant.state.slice(0, 40) : "unknown",
      } : null,
      media_downloaders: downloader ? {
        primary: downloader.primary === "shruti" ? "shruti" : "unknown",
        shruti: shruti ? {
          state: typeof shruti.state === "string" && ["configured", "needs_api_key", "invalid_url"].includes(shruti.state) ? shruti.state : "unknown",
          configured: shruti.configured === true,
        } : null,
        fallbacks: fallbacks.filter((name: unknown) => ["eldian", "local_yt_dlp"].includes(String(name))).slice(0, 2),
      } : null,
      uptime: body.uptime ?? null,
      // "The API answers" and "the bot works" are different facts. Pass both
      // through, with the backend's own diagnosis, so the panel can say why.
      degraded: body.degraded === true,
      degraded_reasons: Array.isArray(body.degraded_reasons) ? body.degraded_reasons : [],
      bot_error: typeof body.bot_error === "string" ? body.bot_error : null,
      bot_online_at: typeof body.bot_online_at === "number" ? body.bot_online_at : null,
      bot_attempts: typeof body.bot_attempts === "number" ? body.bot_attempts : null,
      db: body.db ?? null,
      watchdog: body.watchdog ?? null,
      latency_ms: result.ms,
      revision: typeof body.revision === "string" ? body.revision.slice(0, 40) : null,
      api: apiTelemetry ? {
        p95_ms: typeof apiTelemetry.p95_ms === "number" && Number.isFinite(apiTelemetry.p95_ms) ? apiTelemetry.p95_ms : null,
        samples: typeof apiTelemetry.samples === "number" && Number.isFinite(apiTelemetry.samples) ? Math.max(0, apiTelemetry.samples) : 0,
      } : null,
      attempts: result.attempts,
    },
    { status: 200, headers: { "Cache-Control": "no-store" } },
  );
}
