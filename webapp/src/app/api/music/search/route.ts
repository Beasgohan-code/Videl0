import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const url = new URL(req.url);
  const query = (url.searchParams.get("q") || "").trim();
  if (!query || query.length > 120) {
    return Response.json({ ok: false, error: "Enter a search up to 120 characters" }, { status: 400 });
  }
  const result = await callBackend(`/internal/music/search?q=${encodeURIComponent(query)}&limit=8`, {}, { timeoutMs: 24000, attempts: 1 });
  return Response.json(result.payload, {
    status: result.status,
    headers: { "Cache-Control": "no-store" },
  });
}
