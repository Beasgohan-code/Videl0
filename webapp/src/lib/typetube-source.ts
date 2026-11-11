export const MAX_TYPE_TUBE_TRACK_SECONDS = 24 * 60 * 60;

export type TypeTubeSearchItem = {
  id: string;
  title: string;
  duration: number | null;
  uploader: string | null;
};

export type TypeTubeTrack = {
  video_id: string;
  title: string;
  channel: string;
  duration: string;
  thumbnail: string;
  provider: "typetube";
};

export function isYouTubeVideoId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{11}$/.test(value);
}

export function normalizeTypeTubeSearchItem(value: unknown): TypeTubeTrack | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<TypeTubeSearchItem>;
  if (!isYouTubeVideoId(item.id) || typeof item.title !== "string") return null;
  const title = item.title.trim().slice(0, 200);
  if (!title) return null;
  const seconds = typeof item.duration === "number" && Number.isFinite(item.duration)
      && item.duration >= 0 && item.duration <= MAX_TYPE_TUBE_TRACK_SECONDS
    ? Math.floor(item.duration)
    : null;
  return {
    video_id: item.id,
    title,
    channel: typeof item.uploader === "string" ? item.uploader.trim().slice(0, 120) : "",
    duration: seconds === null ? "—:—" : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`,
    thumbnail: `https://i.ytimg.com/vi/${item.id}/hqdefault.jpg`,
    provider: "typetube",
  };
}

export function isSafeTypeTubeAudioUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 4096) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:"
      && (!url.port || url.port === "443")
      && !url.username
      && !url.password
      && (url.hostname === "googlevideo.com" || url.hostname.endsWith(".googlevideo.com"));
  } catch {
    return false;
  }
}
