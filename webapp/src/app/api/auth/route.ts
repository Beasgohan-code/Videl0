import { NextRequest } from "next/server";
import { ownerMarker, validOwnerCookie } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const initData = typeof body?.initData === "string" ? body.initData : "";
  const loginWidget = body?.login_widget && typeof body.login_widget === "object" ? body.login_widget : null;
  const authPayload = initData && initData.length <= 8192 ? { init_data: initData } : loginWidget ? { login_widget: loginWidget } : null;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!authPayload) return Response.json({ ok: false, error: "Valid Telegram Mini App or Login Widget data is required" }, { status: 400 });
  if (!backend || !secret) return unavailableBackend();
  try {
    const response = await fetch(`${backend}/internal/auth`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Videl-Internal": secret },
      body: JSON.stringify(authPayload),
      cache: "no-store",
      signal: AbortSignal.timeout(7000),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) return Response.json({ ok: false, error: payload.error || "Telegram owner verification failed" }, { status: response.status || 401 });
    const marker = ownerMarker();
    if (!marker) return Response.json({ ok: false, error: "Owner session cannot be issued; WEBAPP_SECRET is missing" }, { status: 503 });
    const res = Response.json({ ok: true, owner: true, user: payload.user });
    res.headers.set("Set-Cookie", `videl_owner=${marker}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400`);
    return res;
  } catch {
    return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 });
  }
}

export async function GET(req: NextRequest) {
  const owner = validOwnerCookie(req);
  return Response.json({ ok: owner, owner }, { headers: { "Cache-Control": "no-store" } });
}
