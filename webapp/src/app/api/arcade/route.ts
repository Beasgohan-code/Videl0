import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

/** The lobby: games, public rooms, the player's rooms and the leaderboards. */
export async function GET(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  return forward("/internal/arcade", {
    headers: actorHeaders(checked.player.id),
  });
}

/** Open a room. The actor is the signed-in player, never a body field. */
export async function POST(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  if (Number(req.headers.get("content-length") || 0) > 2048)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body))
    return Response.json({ ok: false, error: "Choose a game" }, { status: 400 });
  const payload = {
    game: String((body as Record<string, unknown>).game || ""),
    seats: (body as Record<string, unknown>).seats,
    visibility: (body as Record<string, unknown>).visibility === "public" ? "public" : "private",
    chat_id: (body as Record<string, unknown>).chat_id ?? null,
    title: String((body as Record<string, unknown>).title || "").slice(0, 60),
  };
  return forward("/internal/arcade", {
    ...jsonBody(payload),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
