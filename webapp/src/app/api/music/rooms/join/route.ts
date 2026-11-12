import { actorHeaders, playerRequired } from "@/lib/player-auth";
import { forward, jsonBody } from "@/lib/game-api";

export const dynamic = "force-dynamic";
const CODE = /^[A-HJ-NP-Z2-9]{8}$/i;

export async function POST(req: Request) {
  const checked = playerRequired(req);
  if ("denied" in checked) return checked.denied;
  if (Number(req.headers.get("content-length") || 0) > 1024)
    return Response.json({ ok: false, error: "That request is too large" }, { status: 413 });
  const input = await req.json().catch(() => null);
  if (!input || typeof input !== "object" || Array.isArray(input))
    return Response.json({ ok: false, error: "An invite code is required" }, { status: 400 });
  const code = typeof input.code === "string" ? input.code.trim().toUpperCase() : "";
  if (!CODE.test(code)) return Response.json({ ok: false, error: "That invite code is not valid" }, { status: 400 });
  const name = typeof input.name === "string" ? input.name.trim().slice(0, 64) : "";
  return forward("/internal/listening-rooms/join", {
    ...jsonBody({ code, name }),
    headers: { "Content-Type": "application/json", ...actorHeaders(checked.player.id) },
  });
}
