import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Requeue one scheduled post Telegram explicitly rejected.
 *
 * The backend refuses anything that is not `failed`: an accepted post must
 * never be sent twice, and an unconfirmed one has an unknown outcome. This
 * route adds no retry logic of its own so that rule has exactly one home.
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
    const response = await fetch(`${backend}/internal/scheduled-posts/retry`, {
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
    return Response.json({ ok: false, error: "Requeue unconfirmed. Refresh before trying again." }, { status: 503 });
  }
}
