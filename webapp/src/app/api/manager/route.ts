import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";

/** Groups this Telegram account currently administers. */
export async function GET(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const refresh = new URL(req.url).searchParams.get("refresh") === "1" ? "?refresh=1" : "";
  return forward(`/internal/manager/groups${refresh}`, {
    headers: actorHeaders(checked.player.id),
  });
}
