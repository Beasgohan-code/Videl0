import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Owner-only aggregate music/voice signals; identifiers never reach the browser. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/ops/music", {}, { timeoutMs: 4_000, attempts: 1 });
  if (!result.ok || result.payload.schema_version !== 1) {
    return Response.json({ ok: false, schema_version: 1, state: "unavailable" }, {
      status: result.status || 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
  const payload = result.payload as Record<string, any>;
  const count = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(100000, Math.floor(value))) : null;
  const state = (value: unknown, allowed: string[]) => allowed.includes(String(value)) ? String(value) : "unavailable";
  return Response.json({
    ok: true, schema_version: 1,
    measured_at: count(payload.measured_at),
    queue: {
      state: state(payload.queue?.state, ["measured", "unavailable"]),
      active_queues: count(payload.queue?.active_queues),
      upcoming_tracks: count(payload.queue?.upcoming_tracks),
    },
    voice: {
      state: state(payload.voice?.state, ["measured", "unavailable"]),
      active_calls: count(payload.voice?.active_calls),
    },
    downloads: {
      state: state(payload.downloads?.state, ["database", "process_only", "unavailable"]),
      window_seconds: count(payload.downloads?.window_seconds),
      observed: count(payload.downloads?.observed),
      preparing: count(payload.downloads?.preparing),
      ready: count(payload.downloads?.ready),
      failed: count(payload.downloads?.failed),
    },
  }, { headers: { "Cache-Control": "no-store" } });
}
