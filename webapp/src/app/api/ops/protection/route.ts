import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Owner-only bounded group-protection coverage aggregates. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/ops/protection", {}, { timeoutMs: 4_000, attempts: 1 });
  const payload = result.payload as Record<string, any>;
  const count = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(2000, Math.floor(value))) : null;
  const state = result.ok && payload.schema_version === 1 && payload.state === "measured" ? "measured" : "unavailable";
  return Response.json({
    ok: true, schema_version: 1, state,
    measured_at: count(payload.measured_at),
    sampled_groups: state === "measured" ? count(payload.sampled_groups) : null,
    protected_groups: state === "measured" ? count(payload.protected_groups) : null,
    sample_limit: 2000,
    sample_truncated: state === "measured" && payload.sample_truncated === true,
  }, { headers: { "Cache-Control": "no-store" } });
}
