import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/onboarding-analytics", {}, { timeoutMs: 12000, attempts: 2 });
  if (!result.ok)
    return Response.json({ ok: false, error: result.payload.error || result.hint || "Onboarding totals are unavailable" }, {
      status: result.status, headers: { "Cache-Control": "no-store" },
    });
  return Response.json(result.payload, { headers: { "Cache-Control": "no-store" } });
}
