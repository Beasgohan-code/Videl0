import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

const ACTIONS = new Set(["pause", "resume", "skip"]);

/**
 * Pause, resume or skip one occurrence of a repeating series.
 *
 * The backend owns the transition rules (only a pending repeat may change,
 * resuming never replays the backlog, skipping is refused while the dispatcher
 * holds the job). This route validates the shape and forwards.
 */
export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const body = await req.json().catch(() => null);
  const id = (body as { id?: unknown } | null)?.id;
  const action = (body as { action?: unknown } | null)?.action;
  if (typeof id !== "string" || typeof action !== "string" || !ACTIONS.has(action))
    return Response.json(
      { ok: false, error: "A scheduled post ID and one of pause, resume or skip are required" },
      { status: 400 },
    );
  try {
    const response = await fetch(`${backend}/internal/scheduled-posts/series`, {
      method: "POST",
      headers: { "X-Videl-Internal": secret, "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    return Response.json(
      await response.json().catch(() => ({ ok: false, error: "The queue did not answer" })),
      { status: response.status, headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json(
      { ok: false, error: "Series change unconfirmed. Refresh before trying again." },
      { status: 503 },
    );
  }
}
