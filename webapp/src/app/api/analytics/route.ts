import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const denied = ownerRequired(req); if (denied) return denied;
  const backend = backendUrl(); const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  try {
    const response = await fetch(`${backend}/internal/analytics`, { headers: { "X-Videl-Internal": secret }, cache: "no-store", signal: AbortSignal.timeout(8000) });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 }); }
}
