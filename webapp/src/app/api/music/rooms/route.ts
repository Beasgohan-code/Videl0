import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  if (Number(req.headers.get("content-length") || 0) > 1024)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const input = await req.json().catch(() => null);
  if (!input || typeof input !== "object" || Array.isArray(input))
    return Response.json({ ok: false, error: "A room name is required" }, { status: 400 });
  const name = typeof input.name === "string" ? input.name.trim().slice(0, 64) : "";
  return forward("/internal/listening-rooms", {
    ...jsonBody({ name }),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
