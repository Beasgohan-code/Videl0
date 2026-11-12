export type TimedLyricLine = { time: number; text: string };
export type LyricsResult = { title: string; artist: string; lyrics: string; synced: boolean; syncedLines: TimedLyricLine[] };

export function parseSyncedLyrics(value: unknown): TimedLyricLine[] {
  if (typeof value !== "string") return [];
  const rows: TimedLyricLine[] = [];
  for (const rawLine of value.slice(0, 3500).split(/\r?\n/)) {
    const timestamps = [...rawLine.matchAll(/\[(\d{1,}):(\d{2})(?:\.(\d{1,3}))?\]/g)];
    const text = rawLine.replace(/\[(\d{1,}):(\d{2})(?:\.(\d{1,3}))?\]/g, "").trim();
    if (!text) continue;
    for (const match of timestamps) {
      const minutes = Number(match[1]);
      const seconds = Number(match[2]);
      const millis = Number((match[3] || "0").padEnd(3, "0"));
      if (!Number.isFinite(minutes) || seconds > 59) continue;
      rows.push({ time: minutes * 60 + seconds + millis / 1000, text: text.slice(0, 240) });
      if (rows.length >= 200) return rows.sort((a, b) => a.time - b.time);
    }
  }
  return rows.sort((a, b) => a.time - b.time);
}

export function activeSyncedLyricIndex(lines: TimedLyricLine[], position: number): number {
  let active = -1;
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].time > position) break;
    active = index;
  }
  return active;
}

type ProviderItem = {
  trackName?: unknown;
  artistName?: unknown;
  plainLyrics?: unknown;
  syncedLyrics?: unknown;
};

export function cleanLyricsQuery(value: unknown): string {
  return String(value ?? "")
    .replace(/[([{].*?[)\]}]/g, " ")
    .replace(/\b(official|video|audio|lyrics|hd|hq|4k|mv|visualiser|visualizer)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

export function normalizeLyrics(payload: unknown, query: string): LyricsResult | null {
  if (!Array.isArray(payload)) return null;
  for (const candidate of payload as ProviderItem[]) {
    if (!candidate || typeof candidate !== "object") continue;
    const lyrics = typeof candidate.plainLyrics === "string" ? candidate.plainLyrics.trim().slice(0, 3500) : "";
    if (lyrics.length < 20) continue;
    const syncedLines = parseSyncedLyrics(candidate.syncedLyrics);
    return {
      title: typeof candidate.trackName === "string" ? candidate.trackName.slice(0, 120) : query,
      artist: typeof candidate.artistName === "string" ? candidate.artistName.slice(0, 120) : "Unknown artist",
      lyrics,
      synced: syncedLines.length > 0,
      syncedLines,
    };
  }
  return null;
}

export async function findLyrics(
  rawQuery: unknown,
  fetcher: typeof fetch = fetch,
): Promise<LyricsResult | null> {
  const query = cleanLyricsQuery(rawQuery);
  if (!query) return null;
  const endpoint = new URL("https://lrclib.net/api/search");
  endpoint.searchParams.set("q", query);
  const response = await fetcher(endpoint, {
    headers: { "User-Agent": "VidelMusicStudio/1.0" },
    signal: AbortSignal.timeout(8_000),
    cache: "no-store",
  });
  if (!response.ok) return null;
  return normalizeLyrics(await response.json(), query);
}
