import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Owner-only sanitized error categories; raw messages never cross the proxy. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/ops/logs", {}, { timeoutMs: 4_000, attempts: 1 });
  const payload = result.payload as Record<string, any>;
  const valid = result.ok && payload.schema_version === 1 && Array.isArray(payload.events);
  const events = valid ? payload.events.slice(0, 20).flatMap((item: any) => {
    if (!item || typeof item !== "object") return [];
    const source = typeof item.source === "string" ? item.source.slice(0, 80).replace(/[\r\n<>]/g, "") : "unknown";
    const allowed = ["timeout", "connection", "database", "permission", "rate_limit", "validation", "provider", "error"];
    return [{ at: typeof item.at === "number" && Number.isFinite(item.at) ? Math.floor(item.at) : null,
      source, kind: allowed.includes(item.kind) ? item.kind : "error" }];
  }) : null;
  return Response.json({ ok: Boolean(valid), schema_version: 1, measured_at: valid ? payload.measured_at ?? null : null, events }, {
    status: valid ? 200 : result.status || 503,
    headers: { "Cache-Control": "no-store" },
  });
}
