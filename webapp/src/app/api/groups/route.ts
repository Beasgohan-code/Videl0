import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend, callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/chats", {}, { timeoutMs: 20000, attempts: 2 });
  if (!result.ok)
    return Response.json(
      { ok: false, code: result.code === "WAKING" ? "BACKEND_WAKING" : result.payload.code || "BACKEND_UNREACHABLE", error: result.payload.error || result.hint || "Group list unavailable" },
      { status: result.status, headers: { "Cache-Control": "no-store", ...(result.code === "WAKING" ? { "Retry-After": "5" } : {}) } },
    );
  return Response.json(result.payload, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl(); const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const body = await req.json().catch(() => null);
  const chatId = Number(body?.chat_id);
  const settings = body?.settings;
  if (!Number.isSafeInteger(chatId) || !settings || typeof settings !== "object" || Array.isArray(settings)) return Response.json({ ok: false, error: "Invalid group settings request" }, { status: 400 });
  try {
    const response = await fetch(`${backend}/internal/chat-settings`, { method: "POST", headers: { "Content-Type": "application/json", "X-Videl-Internal": secret }, body: JSON.stringify({ chat_id: chatId, settings }), cache: "no-store", signal: AbortSignal.timeout(5000) });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false, error: "Videl backend is unreachable" }, { status: 503 });
  }
}
