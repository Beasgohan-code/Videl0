import { ownerRequired } from "@/lib/auth";
import { groupCall, isActionBody, parseChatId } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

/** One group's settings, community lists and permission state. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const chatId = parseChatId((await context.params).id);
  if (chatId === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  return groupCall(`/internal/chat/${chatId}`);
}

/** Typed writes: presets, warn limit, greetings, blacklist, notes, approvals. */
export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const chatId = parseChatId((await context.params).id);
  if (chatId === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  const body = await req.json().catch(() => null);
  if (!isActionBody(body))
    return Response.json({ ok: false, error: "An action is required" }, { status: 400 });
  return groupCall(`/internal/chat/${chatId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
