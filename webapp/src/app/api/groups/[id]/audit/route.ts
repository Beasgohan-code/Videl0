import { ownerRequired } from "@/lib/auth";
import { groupCall, parseChatId } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

/**
 * Change history for one group.
 *
 * The backend owns retention and the kind vocabulary; this route only forwards
 * a validated cursor so a stale page cannot ask for an unbounded read.
 */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const chatId = parseChatId((await context.params).id);
  if (chatId === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });

  const url = new URL(req.url);
  const query = new URLSearchParams();
  const kind = url.searchParams.get("kind");
  if (kind && /^[a-z_]{1,24}$/.test(kind)) query.set("kind", kind);
  const limit = url.searchParams.get("limit");
  if (limit && /^[0-9]{1,3}$/.test(limit)) query.set("limit", limit);
  const before = url.searchParams.get("before");
  if (before && !Number.isNaN(Date.parse(before))) query.set("before", new Date(before).toISOString());
  // Two rows can share a millisecond; the id makes the page boundary exact.
  const beforeId = url.searchParams.get("before_id");
  if (beforeId && /^[0-9a-f]{24}$/i.test(beforeId)) query.set("before_id", beforeId);
  // Search only ever runs over stored action/detail text, never message bodies.
  const search = url.searchParams.get("q");
  if (search && search.trim()) query.set("q", search.trim().slice(0, 60));
  const actor = url.searchParams.get("actor");
  if (actor && /^[0-9]{1,20}$/.test(actor)) query.set("actor", actor);

  const suffix = query.toString();
  return groupCall(`/internal/chat/${chatId}/audit${suffix ? `?${suffix}` : ""}`);
}
