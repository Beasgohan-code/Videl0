import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const body = (await req.json().catch(() => null)) as { code?: unknown } | null;
  const code = String(body?.code || "").trim().toUpperCase();
  if (!/^[A-Z2-9]{4,8}$/.test(code))
    return Response.json({ ok: false, error: "That room code is not valid" }, { status: 400 });
  return forward("/internal/arcade/join", {
    ...jsonBody({ code }),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
