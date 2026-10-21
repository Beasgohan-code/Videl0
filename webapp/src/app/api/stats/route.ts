import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const denied = ownerRequired(req); if (denied) return denied;
  // Stats is the first thing the dashboard asks for, so it must survive a
  // Render cold start instead of failing at the 5 s mark.
  const result = await callBackend("/internal/stats", {}, { timeoutMs: 20000, attempts: 2 });
  if (!result.ok)
    return Response.json(
      { ok: false, code: result.code === "WAKING" ? "BACKEND_WAKING" : result.payload.code || "BACKEND_UNREACHABLE", error: result.payload.error || result.hint || "Videl backend is unreachable" },
      { status: result.status, headers: { "Cache-Control": "no-store", ...(result.code === "WAKING" ? { "Retry-After": "5" } : {}) } },
    );
  return Response.json(result.payload, { status: 200, headers: { "Cache-Control": "no-store" } });
}
