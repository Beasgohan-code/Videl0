import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function GET(req: Request, context: { params: Promise<{ videoId: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const { videoId } = await context.params;
  if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
    return Response.json({ ok: false, error: "Invalid track ID" }, { status: 400 });
  }
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  let upstream: Response;
  try {
    const headers = new Headers({ "X-Videl-Internal": secret });
    const range = req.headers.get("range");
    const ifRange = req.headers.get("if-range");
    if (range) headers.set("Range", range);
    if (ifRange) headers.set("If-Range", ifRange);
    upstream = await fetch(`${backend}/internal/music/track/${videoId}`, {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(300_000),
    });
  } catch {
    return Response.json({ ok: false, error: "Videl music service is waking or unreachable" }, { status: 503 });
  }
  if (!upstream.ok) {
    const text = await upstream.text().catch(() => "");
    let message = "Track could not be prepared";
    try {
      const payload = JSON.parse(text) as { error?: string };
      if (payload.error) message = payload.error;
    } catch {
      // Do not forward a backend HTML page or diagnostics to the browser.
    }
    return Response.json({ ok: false, error: message }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  }
  const headers = new Headers({
    "Content-Type": upstream.headers.get("content-type") || "audio/mpeg",
    "Content-Disposition": "inline",
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  });
  for (const name of ["content-length", "accept-ranges", "content-range"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
