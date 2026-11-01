import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  return forward("/internal/arcade/events", { headers: actorHeaders(checked.player.id) });
}

export async function POST(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  if (Number(req.headers.get("content-length") || 0) > 4096)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body))
    return Response.json({ ok: false, error: "Event details are required" }, { status: 400 });
  const input = body as Record<string, unknown>;
  const payload = {
    chat_id: input.chat_id,
    title: String(input.title || "").slice(0, 100),
    description: String(input.description || "").slice(0, 700),
    starts_at: String(input.starts_at || ""),
    music_query: String(input.music_query || "").slice(0, 120),
    game_room: String(input.game_room || "").slice(0, 12),
  };
  return forward("/internal/arcade/events", {
    ...jsonBody(payload),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
