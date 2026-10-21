import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";
const PLAYER_ID = /^[1-9][0-9]{0,19}$/;

/** Telegram-signed player card, including per-game W/L/D and rating. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = String((await context.params).id || "");
  if (!PLAYER_ID.test(id))
    return Response.json({ ok: false, error: "That player id is not valid" }, { status: 400 });
  return forward(`/internal/arcade/player/${id}`, {
    headers: actorHeaders(checked.player.id),
  });
}
