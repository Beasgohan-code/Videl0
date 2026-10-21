import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Queue a fresh copy of a post that has already finished.
 *
 * A copy is a new job, so it never resends the original: the backend refuses a
 * job that is still pending or in flight, and leaves the source row untouched.
 * The time is the owner's explicit choice, never inferred from the original.
 */
export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || typeof (body as { id?: unknown }).id !== "string")
    return Response.json({ ok: false, error: "A scheduled post ID is required" }, { status: 400 });
  const scheduleAt = (body as { schedule_at?: unknown }).schedule_at;
  try {
    const response = await fetch(`${backend}/internal/scheduled-posts/duplicate`, {
      method: "POST",
      headers: { "X-Videl-Internal": secret, "Content-Type": "application/json" },
      body: JSON.stringify({
        id: (body as { id: string }).id,
        ...(typeof scheduleAt === "string" ? { schedule_at: scheduleAt } : {}),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    return Response.json(await response.json().catch(() => ({ ok: false, error: "The queue did not answer" })), {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ ok: false, error: "Copy unconfirmed. Refresh before trying again." }, { status: 503 });
  }
}
