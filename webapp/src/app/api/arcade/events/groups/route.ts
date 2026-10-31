import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  return forward("/internal/arcade/event-groups", { headers: actorHeaders(checked.player.id) });
}
