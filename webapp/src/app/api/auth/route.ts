import { NextRequest } from "next/server";
import { ownerMarker, validOwnerCookie, crossSiteRequest } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend, callBackend } from "@/lib/backend";

import { OWNER_ID } from "@/lib/access";
import { readJsonLimited } from "@/lib/request-body";

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
  const parsed = await readJsonLimited(req, 16384);
  if (!parsed.ok)
    return Response.json({ ok: false, error: parsed.status === 413 ? "That request is too large" : "A valid JSON request is required" }, { status: parsed.status });
  const body = parsed.value as Record<string, unknown> | null;
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
    // Render cold starts can take far longer than Telegram's own latency; two
    // attempts with a long budget avoid a false "backend unreachable" on login.
    const result = await callBackend(
      "/internal/auth",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(authPayload) },
      { timeoutMs: 20000, attempts: 2 },
    );
    const payload = (result.payload || {}) as { ok?: boolean; error?: string; user?: { id?: number | string } };
    if (!result.ok)
      return denied(
        result.code === "WAKING"
          ? "The bot backend is starting (Render cold start). Wait a few seconds and sign in again."
          : result.code === "REJECTED"
            ? "The backend rejected the shared secret. Set the same WEBAPP_SECRET in Vercel and Render, then redeploy both."
            : payload.error || "Telegram owner verification failed",
        result.code === "WAKING" ? 503 : result.status === 200 ? 401 : result.status,
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
