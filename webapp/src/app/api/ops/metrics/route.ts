import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Process telemetry is internal-only and owner-session protected at both hops. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/ops/metrics", {}, { timeoutMs: 5_000, attempts: 1 });
  if (!result.ok) {
    return Response.json({ ok: false, state: "unavailable" }, {
      status: result.status || 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
  const process = result.payload.process;
  if (!process || typeof process !== "object") {
    return Response.json({ ok: true, state: "unavailable", process: null }, { headers: { "Cache-Control": "no-store" } });
  }
  const value = process as Record<string, unknown>;
  const numeric = (key: string) => typeof value[key] === "number" && Number.isFinite(value[key]) ? value[key] : null;
  return Response.json({
    ok: true,
    state: "measured",
    process: {
      cpu: numeric("cpu"), process_cpu: numeric("process_cpu"),
      memory_used: numeric("memory_used"), memory_total: numeric("memory_total"),
      memory_percent: numeric("memory_percent"), rss: numeric("rss"),
      disk: typeof value.disk === "string" ? value.disk.slice(0, 100) : null,
      threads: numeric("threads"), file_descriptors: numeric("file_descriptors"),
      measured_at: numeric("measured_at"),
    },
  }, { headers: { "Cache-Control": "no-store" } });
}
