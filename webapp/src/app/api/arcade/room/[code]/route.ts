import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

const CODE = /^[A-Z2-9]{4,8}$/;

function roomPath(raw: string) {
  const code = String(raw || "").toUpperCase();
  return CODE.test(code) ? code : null;
}

export async function GET(req: Request, context: { params: Promise<{ code: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const code = roomPath((await context.params).code);
  if (!code) return Response.json({ ok: false, error: "That room code is not valid" }, { status: 400 });
  const after = Number(new URL(req.url).searchParams.get("after") || 0);
  return forward(`/internal/arcade/room/${code}?after=${Number.isSafeInteger(after) && after > 0 ? after : 0}`, {
    headers: actorHeaders(checked.player.id),
  });
}

export async function POST(req: Request, context: { params: Promise<{ code: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const code = roomPath((await context.params).code);
  if (!code) return Response.json({ ok: false, error: "That room code is not valid" }, { status: 400 });
  // A voice note is the one action that legitimately carries a body; every
  // other action is a few hundred bytes and should stay that way.
  const ceiling = 560_000;
  if (Number(req.headers.get("content-length") || 0) > ceiling)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body))
    return Response.json({ ok: false, error: "An action is required" }, { status: 400 });
  const record = body as Record<string, unknown>;
  const action = String(record.action || "move");
  if (!["move", "start", "leave", "kick", "rematch", "chat", "seen", "rtc", "resign", "draw", "voice", "clip"].includes(action))
    return Response.json({ ok: false, error: "Unknown room action" }, { status: 400 });
  const payload: Record<string, unknown> = { action };
  if (action === "move") payload.move = record.move ?? record;
  if (action === "chat") payload.text = String(record.text || "").slice(0, 401);
  if (action === "kick") payload.user = record.user;
  if (action === "draw") payload.accept = record.accept === true;
  if (action === "voice") payload.on = record.on !== false;
  if (action === "clip") {
    const data = record.data;
    if (typeof data !== "string" || !data || data.length > 480_000)
      return Response.json({ ok: false, error: "That recording is too large" }, { status: 413 });
    payload.data = data;
    payload.mime = String(record.mime || "audio/webm");
    payload.seconds = Number(record.seconds);
  }
  if (action === "rtc") {
    // Only the four WebRTC verbs cross this door, and only as a small object:
    // the backend re-checks both, but a browser should not be able to post a
    // megabyte at the relay in the first place.
    const kind = String(record.kind || "");
    if (!["offer", "answer", "ice", "bye"].includes(kind))
      return Response.json({ ok: false, error: "Unknown voice signal" }, { status: 400 });
    const data = record.data;
    if (!data || typeof data !== "object" || Array.isArray(data))
      return Response.json({ ok: false, error: "A voice signal needs a payload" }, { status: 400 });
    if (JSON.stringify(data).length > 2600)
      return Response.json({ ok: false, error: "That voice signal is too large" }, { status: 413 });
    payload.kind = kind;
    payload.to = Number(record.to);
    payload.data = data;
  }
  return forward(`/internal/arcade/room/${code}`, {
    ...jsonBody(payload),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
