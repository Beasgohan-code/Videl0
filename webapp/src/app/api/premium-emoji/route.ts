import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Owner-only binary proxy for premium (custom) emoji artwork.
 * The bot token never leaves the backend: the browser only sees this URL.
 */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl(), secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!/^[0-9]{1,20}$/.test(id)) {
    return Response.json({ ok: false, error: "A numeric premium emoji ID is required" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backend}/internal/premium-emoji?id=${id}`, {
      headers: { "X-Videl-Internal": secret },
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) {
      return Response.json({ ok: false, error: "Premium emoji artwork is unavailable" }, { status: response.status });
    }
    const payload = await response.arrayBuffer();
    if (payload.byteLength > 512 * 1024) {
      return Response.json({ ok: false, error: "Premium emoji artwork is too large" }, { status: 413 });
    }
    return new Response(payload, {
      status: 200,
      headers: {
        "Content-Type": response.headers.get("content-type") || "image/webp",
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json({ ok: false, error: "Premium emoji artwork is unavailable" }, { status: 503 });
  }
}
