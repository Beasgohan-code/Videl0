import { NextRequest } from "next/server";
import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const denied = ownerRequired(req); if (denied) return denied;
  const backend = backendUrl(); const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object") return Response.json({ ok: false, error: "Invalid JSON body" }, { status: 400 });
  const chat_id = String(body.chat_id || "").trim(); const text = String(body.text || "").trim();
  const media_url = body.media_url ? String(body.media_url).trim() : "";
  if (!chat_id || (!text && !media_url)) return Response.json({ ok: false, error: "A channel ID and post text or media are required" }, { status: 400 });
  try {
    const response = await fetch(`${backend}/internal/channel-post`, { method: "POST", headers: { "Content-Type": "application/json", "X-Videl-Internal": secret }, body: JSON.stringify({ chat_id, text, parse_mode: body.parse_mode, media_url, buttons: body.buttons }), cache: "no-store", signal: AbortSignal.timeout(20000) });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 }); }
}

export async function GET(req: Request) {
  const denied = ownerRequired(req); if (denied) return denied;
  return Response.json({ ok: true, usage: "POST {chat_id, text, parse_mode?, media_url?, buttons?}" }, { headers: { "Cache-Control": "no-store" } });
}
