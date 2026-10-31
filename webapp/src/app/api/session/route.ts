import { callBackend, unavailableBackend } from "@/lib/backend";
import { readJsonLimited } from "@/lib/request-body";
import {
  clearedPlayerCookies,
  crossSite,
  playerCookies,
  playerRequired,
  type Player,
} from "@/lib/player-auth";

export const dynamic = "force-dynamic";

/** Who is signed in, as far as this browser's cookie says. */
export async function GET(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked)
    return Response.json(
      { ok: false, player: null },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  return Response.json(
    { ok: true, player: checked.player },
    { headers: { "Cache-Control": "no-store" } },
  );
}

/** Verify a Mini App or Login Widget payload and mint the player cookie. */
export async function POST(req: Request) {
  if (crossSite(req))
    return Response.json(
      { ok: false, error: "Cross-site authentication is not allowed" },
      { status: 403 },
    );
  const parsed = await readJsonLimited(req, 16384);
  if (!parsed.ok)
    return Response.json(
      { ok: false, error: parsed.status === 413 ? "That request is too large" : "A valid JSON request is required" },
      { status: parsed.status },
    );
  const body = parsed.value as
    | { initData?: unknown; login_widget?: unknown }
    | null;
  const initData =
    typeof body?.initData === "string" && body.initData.length <= 8192
      ? body.initData
      : "";
  const widget =
    body?.login_widget && typeof body.login_widget === "object"
      ? body.login_widget
      : null;
  if (!initData && !widget)
    return Response.json(
      { ok: false, error: "Telegram sign-in data is required" },
      { status: 400 },
    );
  const result = await callBackend(
    "/internal/identity",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(initData ? { init_data: initData } : { login_widget: widget }),
    },
    { timeoutMs: 20000, attempts: 2 },
  );
  if (!result.ok) {
    if (result.code === "NOT_CONFIGURED") return unavailableBackend();
    return Response.json(
      {
        ok: false,
        error:
          result.code === "WAKING"
            ? "The bot backend is starting. Wait a moment and sign in again."
            : (result.payload.error as string) || "Telegram could not confirm who you are.",
      },
      { status: result.code === "WAKING" ? 503 : result.status || 401 },
    );
  }
  const player = result.payload.player as Player | undefined;
  if (!player?.id)
    return Response.json(
      { ok: false, error: "Telegram did not return an account" },
      { status: 502 },
    );
  const cookies = playerCookies(player);
  if (!cookies.length)
    return Response.json(
      { ok: false, error: "Player sessions cannot be issued; WEBAPP_SECRET is missing" },
      { status: 503 },
    );
  const response = Response.json({ ok: true, player });
  for (const cookie of cookies) response.headers.append("Set-Cookie", cookie);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function DELETE(req: Request) {
  if (crossSite(req)) return Response.json({ ok: false }, { status: 403 });
  const response = Response.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  for (const cookie of clearedPlayerCookies())
    response.headers.append("Set-Cookie", cookie);
  return response;
}
