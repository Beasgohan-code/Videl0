import { ownerRequired } from "@/lib/auth";
import { groupCall } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

function federationId(value: string): string | null {
  return /^[A-Za-z0-9_-]{1,32}$/.test(value) ? value : null;
}

/** One federation with its ban list and member groups. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const id = federationId((await context.params).id);
  if (!id) return Response.json({ ok: false, error: "Invalid federation ID" }, { status: 400 });
  return groupCall(`/internal/federation/${encodeURIComponent(id)}`);
}

/**
 * The only federation write exposed here is lifting a ban.
 *
 * Creating federations and issuing bans stays on the bot commands: a ban is a
 * live enforcement action across every member group, and the command path
 * already validates the caller against Telegram.
 */
export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const id = federationId((await context.params).id);
  if (!id) return Response.json({ ok: false, error: "Invalid federation ID" }, { status: 400 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || (body as { action?: unknown }).action !== "unban")
    return Response.json({ ok: false, error: "Only action=unban is supported" }, { status: 400 });
  const userId = (body as { user_id?: unknown }).user_id;
  if (typeof userId !== "number" || !Number.isSafeInteger(userId) || userId <= 0)
    return Response.json({ ok: false, error: "A numeric user ID is required" }, { status: 400 });
  return groupCall(`/internal/federation/${encodeURIComponent(id)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "unban", user_id: userId }),
  });
}
