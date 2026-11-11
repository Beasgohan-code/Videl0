import { ownerRequired } from "@/lib/auth";
import { findLyrics } from "@/lib/music-lyrics";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const query = new URL(req.url).searchParams.get("q") || "";
  if (!query.trim() || query.length > 120) {
    return Response.json({ ok: false, error: "Enter a song title up to 120 characters." }, { status: 400 });
  }
  try {
    const lyrics = await findLyrics(query);
    return Response.json({ ok: true, lyrics }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false, error: "Lyrics service is temporarily unavailable." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
