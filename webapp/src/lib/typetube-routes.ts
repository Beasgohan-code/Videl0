import { ownerRequired } from "@/lib/auth";
import { isSafeTypeTubeAudioUrl, isYouTubeVideoId, MAX_TYPE_TUBE_TRACK_SECONDS, normalizeTypeTubeSearchItem } from "@/lib/typetube-source";

export type TypeTubeBridge = {
  search(query: string, options: { limit: number; timeoutMs: number }): Promise<unknown[]>;
  resolve(query: string): Promise<{
    success: boolean;
    title?: string;
    author?: string;
    uploader?: string;
    durationSeconds?: number;
    bestAudio?: { url?: string };
  }>;
};

const unavailable = (message: string, status = 503) => Response.json(
  { ok: false, error: message },
  { status, headers: { "Cache-Control": "no-store", ...(status === 503 ? { "Retry-After": "10" } : {}) } },
);

export async function typeTubeSearchRoute(req: Request, getClient: () => TypeTubeBridge): Promise<Response> {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const query = (new URL(req.url).searchParams.get("q") || "").trim();
  if (!query || query.length > 120) return unavailable("Enter a search up to 120 characters", 400);
  try {
    const results = await getClient().search(query, { limit: 8, timeoutMs: 10_000 });
    const tracks = results.slice(0, 8).map(normalizeTypeTubeSearchItem).filter((track) => track !== null);
    return Response.json({ ok: true, tracks }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return unavailable("TypeTube search is temporarily unavailable.");
  }
}

export async function typeTubeResolveRoute(req: Request, getClient: () => TypeTubeBridge): Promise<Response> {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const id = new URL(req.url).searchParams.get("id");
  if (!isYouTubeVideoId(id)) return unavailable("Choose a valid YouTube track.", 400);
  try {
    const track = await getClient().resolve(`https://www.youtube.com/watch?v=${id}`);
    const audioUrl = track.bestAudio?.url;
    if (track.success !== true || !isSafeTypeTubeAudioUrl(audioUrl)) {
      return unavailable("TypeTube did not return a supported audio stream.", 502);
    }
    return Response.json({
      ok: true,
      track: {
        video_id: id,
        title: String(track.title || "").slice(0, 200),
        channel: String(track.author || track.uploader || "").slice(0, 120),
        duration_seconds: typeof track.durationSeconds === "number" && Number.isFinite(track.durationSeconds)
          && track.durationSeconds >= 0 && track.durationSeconds <= MAX_TYPE_TUBE_TRACK_SECONDS
          ? Math.floor(track.durationSeconds)
          : 0,
        thumbnail: `https://i.ytimg.com/vi/${id}/hqdefault.jpg`,
        audio_url: audioUrl,
      },
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return unavailable("TypeTube could not resolve this track right now.");
  }
}
