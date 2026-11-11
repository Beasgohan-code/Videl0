import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";
const CODE = /^[A-HJ-NP-Z2-9]{8}$/i;
const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

type Context = { params: Promise<{ code: string }> };

async function safeCode(context: Context) {
  const code = (await context.params).code.toUpperCase();
  return CODE.test(code) ? code : null;
}

export async function GET(req: Request, context: Context) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const code = await safeCode(context);
  if (!code) return Response.json({ ok: false, error: "That invite code is not valid" }, { status: 400 });
  return forward(`/internal/listening-rooms/${code}`, { headers: actorHeaders(checked.player.id) });
}

export async function POST(req: Request, context: Context) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const code = await safeCode(context);
  if (!code) return Response.json({ ok: false, error: "That invite code is not valid" }, { status: 400 });
  if (Number(req.headers.get("content-length") || 0) > 16_384)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const input = await req.json().catch(() => null);
  if (!input || typeof input !== "object" || Array.isArray(input))
    return Response.json({ ok: false, error: "A room action is required" }, { status: 400 });
  const action = input.action;
  let payload: Record<string, unknown>;
  if (action === "leave" || action === "close") payload = { action };
  else if (action === "queue") {
    if (!Array.isArray(input.queue) || input.queue.length > 100)
      return Response.json({ ok: false, error: "A room queue can contain at most 100 tracks" }, { status: 400 });
    const queue = input.queue.map((entry: Record<string, unknown>) => ({
      video_id: typeof entry?.video_id === "string" ? entry.video_id : "",
      title: typeof entry?.title === "string" ? entry.title.slice(0, 200) : "",
      channel: typeof entry?.channel === "string" ? entry.channel.slice(0, 120) : "",
      duration: typeof entry?.duration === "string" ? entry.duration.slice(0, 24) : "",
      provider: entry?.provider === "typetube" ? "typetube" : "videl",
    }));
    payload = { action, queue };
  } else if (action === "playback") {
    if (typeof input.track_id !== "string" || !VIDEO_ID.test(input.track_id)
      || typeof input.playing !== "boolean"
      || !Number.isFinite(input.position) || !Number.isFinite(input.duration))
      return Response.json({ ok: false, error: "That playback update is not valid" }, { status: 400 });
    payload = {
      action,
      track_id: input.track_id,
      playing: input.playing,
      position: Math.max(0, Math.min(86_400, input.position)),
      duration: Math.max(0, Math.min(86_400, input.duration)),
    };
  } else return Response.json({ ok: false, error: "Unknown room action" }, { status: 400 });
  return forward(`/internal/listening-rooms/${code}`, {
    ...jsonBody(payload),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
