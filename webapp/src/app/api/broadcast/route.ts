import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();

  const body = await req.json().catch(() => null);
  const text = String(body?.text || "").trim();
  const scope = String(body?.scope || "chats").trim();
  if (!["chats", "users", "all"].includes(scope))
    return Response.json(
      { ok: false, error: "Choose a valid broadcast audience" },
      { status: 400 },
    );
  if (!text || text.length > 4096) {
    return Response.json(
      { ok: false, error: "Broadcast text (1–4096 characters) is required" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${backend}/internal/broadcast`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Videl-Internal": secret,
      },
      body: JSON.stringify({ text, scope }),
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
    });
    const payload = await response.json();
    return Response.json(payload, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      {
        ok: false,
        error:
          "Broadcast delivery could not be confirmed. Check Telegram before retrying; some recipients may already have received it.",
      },
      { status: 503 },
    );
  }
}
