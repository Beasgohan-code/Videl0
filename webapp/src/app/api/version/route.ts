import { ownerRequired } from "@/lib/auth";
import { backendUrl, callBackend, internalSecret } from "@/lib/backend";
import { backendRevision, buildReleaseCheck, webRevision } from "@/lib/release";

export const dynamic = "force-dynamic";

/**
 * Which commit each deployment is serving, plus the backend round-trip.
 *
 * The revision is read from the backend's own /health endpoint, so this is a
 * measurement rather than an assumption. A missing revision is reported as
 * "unknown" instead of being papered over.
 */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const web = webRevision(process.env.VERCEL_GIT_COMMIT_SHA);
  const checkedAt = new Date().toISOString();
  if (!backendUrl() || !internalSecret()) {
    return Response.json(
      buildReleaseCheck({ web, backend: null, status: "not_configured", latencyMs: null, checkedAt }),
      { headers: { "Cache-Control": "no-store" } },
    );
  }
  const result = await callBackend("/health", {}, { timeoutMs: 9000, attempts: 2 });
  const payload = result.payload as { revision?: unknown; status?: unknown; api?: { p95_ms?: unknown } };
  const backend = backendRevision(payload.revision);
  const status = result.ok ? "ok" : "unreachable";
  const rawP95 = Number(payload.api?.p95_ms);
  const p95Ms = Number.isFinite(rawP95) && rawP95 >= 0 ? rawP95 : null;
  return Response.json(
    buildReleaseCheck({
      web,
      backend,
      status,
      latencyMs: result.ms,
      p95Ms,
      checkedAt,
    }),
    { headers: { "Cache-Control": "no-store" } },
  );
}
