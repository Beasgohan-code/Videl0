import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";

/** Update only the signed-in player's own public-profile visibility. */
export async function PATCH(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const body = await req.json().catch(() => null);
  if (!body || typeof body.profile_private !== "boolean")
    return Response.json({ ok: false, error: "Choose a valid profile visibility" }, { status: 400 });
  return forward("/internal/arcade/me", {
    method: "PATCH",
    headers: actorHeaders(checked.player.id),
    body: JSON.stringify({ profile_private: body.profile_private }),
  });
}
