import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";

function chatId(raw: string): number | null {
  const value = Number(raw);
  return Number.isSafeInteger(value) && value < 0 ? value : null;
}

export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = chatId((await context.params).id);
  if (id === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  const audit = new URL(req.url).searchParams.get("audit");
  if (audit === "1") {
    const params = new URL(req.url).searchParams;
    const query = new URLSearchParams({ limit: "40" });
    const before = params.get("before");
    if (before && Number.isFinite(Date.parse(before))) query.set("before", new Date(before).toISOString());
    const kind = params.get("kind");
    if (kind && /^[a-z_]{1,24}$/.test(kind)) query.set("kind", kind);
    const search = params.get("q")?.trim().slice(0, 60);
    if (search) query.set("q", search);
    const actor = params.get("actor");
    if (actor && /^[1-9][0-9]{0,19}$/.test(actor)) query.set("actor", actor);
    for (const field of ["from", "through"]) {
      const raw = params.get(field);
      if (raw && Number.isFinite(Date.parse(raw))) query.set(field, new Date(raw).toISOString());
    }
    return forward(`/internal/manager/chat/${id}/audit?${query}`, {
      headers: actorHeaders(checked.player.id),
    });
  }
  return forward(`/internal/manager/chat/${id}`, {
    headers: actorHeaders(checked.player.id),
  });
}

export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  const id = chatId((await context.params).id);
  if (id === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  if (Number(req.headers.get("content-length") || 0) > 20000)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body) || !("action" in body))
    return Response.json({ ok: false, error: "An action is required" }, { status: 400 });
  return forward(`/internal/manager/chat/${id}`, {
    ...jsonBody(body),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
