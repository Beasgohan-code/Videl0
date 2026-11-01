import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";
const PLAYER_ID = /^[1-9][0-9]{0,19}$/;
const IMAGE_MIME = new Set(["image/jpeg", "image/png", "image/webp"]);

/** Private, bounded Telegram profile-photo proxy; tokens stay on the server. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = String((await context.params).id || "");
  if (!PLAYER_ID.test(id))
    return Response.json({ ok: false, error: "That player id is not valid" }, { status: 400 });
  const answer = await forward(`/internal/arcade/avatar/${id}`, {
    headers: actorHeaders(checked.player.id),
  });
  if (!answer.ok) return answer;
  const payload = (await answer.json()) as { mime?: string; data?: string };
  if (!payload.data || payload.data.length > 550_000)
    return Response.json({ ok: false, error: "That profile photo is unavailable" }, { status: 502 });
  const mime = IMAGE_MIME.has(String(payload.mime)) ? String(payload.mime) : "image/jpeg";
  return new Response(Buffer.from(payload.data, "base64"), {
    status: 200,
    headers: {
      "Content-Type": mime,
      "Cache-Control": "private, max-age=3600",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
