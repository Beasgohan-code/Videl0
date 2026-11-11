export type PlaylistTrack = {
  video_id: string;
  title: string;
  channel: string;
  duration: string;
  thumbnail: string;
  provider?: "videl" | "typetube";
};
export type SavedPlaylist = { id: string; name: string; updatedAt: number; tracks: PlaylistTrack[] };

export const MAX_SAVED_PLAYLISTS = 20;
export const MAX_PLAYLIST_TRACKS = 50;
export const MAX_BROWSER_QUEUE = 100;

export function normalizePlaylists(value: unknown): SavedPlaylist[] {
  if (!Array.isArray(value)) return [];
  const normalized: SavedPlaylist[] = [];
  for (const row of value.slice(0, MAX_SAVED_PLAYLISTS)) {
    if (!row || typeof row !== "object") continue;
    const item = row as Partial<SavedPlaylist>;
    if (typeof item.id !== "string" || !item.id || typeof item.name !== "string") continue;
    const tracks = Array.isArray(item.tracks) ? item.tracks.slice(0, MAX_PLAYLIST_TRACKS).flatMap((candidate) => {
      if (!candidate || typeof candidate !== "object") return [];
      const track = candidate as Partial<PlaylistTrack>;
      if (typeof track.video_id !== "string" || !/^[A-Za-z0-9_-]{11}$/.test(track.video_id) || typeof track.title !== "string") return [];
      return [{
        video_id: track.video_id,
        title: track.title.slice(0, 200),
        channel: typeof track.channel === "string" ? track.channel.slice(0, 120) : "",
        duration: typeof track.duration === "string" ? track.duration.slice(0, 24) : "",
        thumbnail: typeof track.thumbnail === "string" ? track.thumbnail.slice(0, 500) : "",
        provider: track.provider === "typetube" ? "typetube" as const : "videl" as const,
      }];
    }) : [];
    normalized.push({
      id: item.id.slice(0, 80),
      name: item.name.trim().slice(0, 40) || "Saved playlist",
      updatedAt: Number.isFinite(item.updatedAt) ? Number(item.updatedAt) : 0,
      tracks,
    });
  }
  return normalized;
}

export function makePlaylist(name: string, tracks: PlaylistTrack[], id: string, updatedAt = Date.now()): SavedPlaylist | null {
  const safeName = name.trim().replace(/\s+/g, " ").slice(0, 40);
  const safeTracks = normalizePlaylists([{ id, name: safeName, tracks }])[0]?.tracks || [];
  if (!safeName || !safeTracks.length || !id) return null;
  return { id: id.slice(0, 80), name: safeName, updatedAt, tracks: safeTracks };
}

export function appendPlaylistTracks(queue: PlaylistTrack[], tracks: PlaylistTrack[], limit = MAX_BROWSER_QUEUE): PlaylistTrack[] {
  const slots = Math.max(0, Math.min(MAX_BROWSER_QUEUE, Math.floor(limit)) - queue.length);
  return [...queue, ...tracks.slice(0, slots)];
}
