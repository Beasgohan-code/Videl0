import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Owner-only proxy for a chat's profile photo. Telegram file URLs embed the bot
 * token, so the browser only ever sees this endpoint.
 */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl(), secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const chatId = new URL(req.url).searchParams.get("chat_id") || "";
  if (!/^-?[0-9]{1,20}$/.test(chatId) || chatId === "0") {
    return Response.json({ ok: false, error: "A numeric chat ID is required" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backend}/internal/chat-photo?chat_id=${chatId}`, {
      headers: { "X-Videl-Internal": secret },
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      return Response.json({ ok: false, error: "Chat photo is unavailable" }, { status: response.status });
    }
    const payload = await response.arrayBuffer();
    if (payload.byteLength > 512 * 1024) {
      return Response.json({ ok: false, error: "Chat photo is too large" }, { status: 413 });
    }
    return new Response(payload, {
      status: 200,
      headers: {
        "Content-Type": response.headers.get("content-type") || "image/jpeg",
        "Cache-Control": "private, max-age=21600",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json({ ok: false, error: "Chat photo is unavailable" }, { status: 503 });
  }
}
