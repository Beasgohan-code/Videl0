import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward } from "@/lib/game-api";

export const dynamic = "force-dynamic";

const ID = /^[A-Za-z0-9_-]{8,32}$/;

/**
 * One voice note, played back by a member of its room.
 *
 * The browser never names a path into storage: the id is opaque, and the
 * backend re-checks that the caller is seated in the room the clip belongs to.
 * Audio is `no-store` — a recording is nobody's cache entry.
 */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = String((await context.params).id || "");
  if (!ID.test(id))
    return Response.json({ ok: false, error: "That voice note is not valid" }, { status: 400 });
  const answer = await forward(`/internal/arcade/clip/${id}`, {
    headers: actorHeaders(checked.player.id),
  });
  if (!answer.ok) return answer;
  const body = (await answer.json()) as { data?: string; mime?: string; seconds?: number };
  if (!body.data) return Response.json({ ok: false, error: "That voice note is empty" }, { status: 404 });
  const bytes = Buffer.from(body.data, "base64");
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": body.mime || "audio/webm",
      "Content-Length": String(bytes.byteLength),
      "Cache-Control": "private, no-store",
    },
  });
}
