import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();

  try {
    const response = await fetch(`${backend}/internal/bot-settings`, {
      headers: { "X-Videl-Internal": secret },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 });
  }
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
