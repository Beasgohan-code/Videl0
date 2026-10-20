import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  return Response.json(
    {
      items: [],
      note: "Message history is not stored; only a successful send receipt is returned.",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object")
    return Response.json(
      { ok: false, error: "Invalid JSON body" },
      { status: 400 },
    );
  const chat_id = String(body.chat_id || "").trim();
  const text = String(body.text || "").trim();
  if (!chat_id || !text || text.length > 4096)
    return Response.json(
      {
        ok: false,
        error: "Enter a Telegram chat ID and 1–4096 characters of text",
      },
      { status: 400 },
    );
  try {
    const response = await fetch(`${backend}/internal/send-message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Videl-Internal": secret,
      },
      body: JSON.stringify({ chat_id, text, as_user: body.as_user === true }),
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
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
          "Message delivery could not be confirmed. Check Telegram before retrying to avoid a duplicate.",
      },
      { status: 503 },
    );
  }
}
