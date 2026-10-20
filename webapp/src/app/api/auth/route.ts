import { NextRequest } from "next/server";
import { ownerMarker, validOwnerCookie, crossSiteRequest } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

import { OWNER_ID } from "@/lib/access";

export const dynamic = "force-dynamic";

function denied(error: string, status: number) {
  const response = Response.json(
    { ok: false, owner: false, error },
    { status, headers: { "Cache-Control": "no-store" } },
  );
  if (status === 401 || status === 403) {
    response.headers.append(
      "Set-Cookie",
      "videl_owner=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0",
    );
    response.headers.append(
      "Set-Cookie",
      "videl_owner_embedded=; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=0",
    );
  }
  return response;
}

export async function POST(req: NextRequest) {
  if (crossSiteRequest(req))
    return Response.json(
      { ok: false, error: "Cross-site authentication blocked" },
      { status: 403 },
    );
  if (Number(req.headers.get("content-length") || 0) > 16384)
    return Response.json({ ok: false }, { status: 413 });
  const body = await req.json().catch(() => null);
  const initData = typeof body?.initData === "string" ? body.initData : "";
  const loginWidget =
    body?.login_widget && typeof body.login_widget === "object"
      ? body.login_widget
      : null;
  const authPayload =
    initData && initData.length <= 8192
      ? { init_data: initData }
      : loginWidget
        ? { login_widget: loginWidget }
        : null;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!authPayload)
    return Response.json(
      {
        ok: false,
        error: "Valid Telegram Mini App or Login Widget data is required",
      },
      { status: 400 },
    );
  if (!backend || !secret) return unavailableBackend();
  try {
    const response = await fetch(`${backend}/internal/auth`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Videl-Internal": secret,
      },
      body: JSON.stringify(authPayload),
      cache: "no-store",
      signal: AbortSignal.timeout(7000),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok)
      return denied(
        payload.error || "Telegram owner verification failed",
        response.ok ? 401 : response.status,
      );
    if (String(payload.user?.id) !== OWNER_ID)
      return denied(
        "This account does not have owner access. Post Studio is available without signing in.",
        403,
      );
    const marker = ownerMarker();
    if (!marker)
      return Response.json(
        {
          ok: false,
          error: "Owner session cannot be issued; WEBAPP_SECRET is missing",
        },
        { status: 503 },
      );
    const res = Response.json({ ok: true, owner: true, user: payload.user });
    res.headers.set(
      "Set-Cookie",
      `videl_owner=${marker}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=86400`,
    );
    res.headers.append(
      "Set-Cookie",
      `videl_owner_embedded=${marker}; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=86400`,
    );
    res.headers.set("Cache-Control", "no-store");
    return res;
  } catch {
    return Response.json(
      { ok: false, error: "Videl backend is unreachable" },
      { status: 503 },
    );
  }
}

export async function GET(req: NextRequest) {
  const owner = validOwnerCookie(req);
  return Response.json(
    { ok: owner, owner },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function DELETE(req: NextRequest) {
  if (crossSiteRequest(req))
    return Response.json({ ok: false }, { status: 403 });
  const response = Response.json(
    { ok: true },
    { headers: { "Cache-Control": "no-store" } },
  );
  response.headers.set(
    "Set-Cookie",
    "videl_owner=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0",
  );
  response.headers.append(
    "Set-Cookie",
    "videl_owner_embedded=; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=0",
  );
  return response;
}
