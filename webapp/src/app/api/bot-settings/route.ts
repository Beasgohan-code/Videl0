import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend, callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();

  const result = await callBackend("/internal/bot-settings", {}, { timeoutMs: 18000, attempts: 2 });
  if (!result.ok)
    return Response.json(
      { ok: false, code: result.code === "WAKING" ? "BACKEND_WAKING" : result.payload.code || "BACKEND_UNREACHABLE", error: result.payload.error || result.hint || "Videl backend is unreachable" },
      { status: result.status, headers: { "Cache-Control": "no-store", ...(result.code === "WAKING" ? { "Retry-After": "5" } : {}) } },
    );
  return Response.json(result.payload, { status: 200, headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();

  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ ok: false, error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    const response = await fetch(`${backend}/internal/bot-settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Videl-Internal": secret },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 });
  }
}
