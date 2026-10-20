import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";
import { groupError, isSettingPatch, parseChatId } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

/** The served-group list, with settings, warning totals and cached profile data. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/chats", {}, { timeoutMs: 20000, attempts: 2 });
  if (!result.ok) return groupError(result);
  return Response.json(result.payload, { headers: { "Cache-Control": "no-store" } });
}

/**
 * Protection toggles.
 *
 * This stays on `/internal/chat-settings` so the original six locks keep
 * working against a backend that has not been redeployed yet; newer locks are
 * accepted by the same route once the updated Flask build is live.
 */
export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const body = await req.json().catch(() => null);
  const chatId = parseChatId((body as { chat_id?: unknown } | null)?.chat_id);
  const settings = (body as { settings?: unknown } | null)?.settings;
  if (chatId === null || !isSettingPatch(settings))
    return Response.json({ ok: false, error: "Invalid group settings request" }, { status: 400 });
  const result = await callBackend(
    "/internal/chat-settings",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, settings }),
    },
    { timeoutMs: 15000, attempts: 2 },
  );
  if (!result.ok) return groupError(result);
  return Response.json(result.payload, { headers: { "Cache-Control": "no-store" } });
}
