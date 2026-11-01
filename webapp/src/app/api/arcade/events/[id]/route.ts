import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";
const EVENT_CODE = /^[A-HJ-NP-Z2-9]{8}$/;

export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = (await context.params).id.toUpperCase();
  if (!EVENT_CODE.test(id)) return Response.json({ ok: false, error: "That event link is not valid" }, { status: 400 });
  return forward(`/internal/arcade/events/${id}`, { headers: actorHeaders(checked.player.id) });
}

export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  if (Number(req.headers.get("content-length") || 0) > 4096)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const id = (await context.params).id.toUpperCase();
  if (!EVENT_CODE.test(id)) return Response.json({ ok: false, error: "That event link is not valid" }, { status: 400 });
  const body = await req.json().catch(() => null);
  const record = body && typeof body === "object" && !Array.isArray(body)
    ? body as Record<string, unknown>
    : {};
  const action = String(record.action || "");
  const status = String(record.status || "");
  if (action === "edit") {
    const payload = {
      action,
      title: String(record.title || "").slice(0, 100),
      description: String(record.description || "").slice(0, 700),
      starts_at: String(record.starts_at || ""),
      music_query: String(record.music_query || "").slice(0, 120),
      game_room: String(record.game_room || "").slice(0, 12),
    };
    if (!payload.title || !payload.starts_at)
      return Response.json({ ok: false, error: "Event title and start time are required" }, { status: 400 });
    return forward(`/internal/arcade/events/${id}`, {
      ...jsonBody(payload),
      headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
    });
  }
  if (action !== "cancel" && !["going", "maybe", "not_going"].includes(status))
    return Response.json({ ok: false, error: "Choose an RSVP, edit, or cancel the event" }, { status: 400 });
  return forward(`/internal/arcade/events/${id}`, {
    ...jsonBody(action === "cancel" ? { action } : { status }),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
