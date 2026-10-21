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
  if (Number(req.headers.get("content-length") || 0) > 4096)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body))
    return Response.json({ ok: false, error: "An action is required" }, { status: 400 });
  const record = body as Record<string, unknown>;
  const action = String(record.action || "move");
  if (!["move", "start", "leave", "kick", "rematch", "chat", "seen"].includes(action))
    return Response.json({ ok: false, error: "Unknown room action" }, { status: 400 });
  const payload: Record<string, unknown> = { action };
  if (action === "move") payload.move = record.move ?? record;
  if (action === "chat") payload.text = String(record.text || "").slice(0, 401);
  if (action === "kick") payload.user = record.user;
  return forward(`/internal/arcade/room/${code}`, {
    ...jsonBody(payload),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
