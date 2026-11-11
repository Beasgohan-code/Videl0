import test from "node:test";
import assert from "node:assert/strict";
import { activeSyncedLyricIndex, cleanLyricsQuery, findLyrics, normalizeLyrics, parseSyncedLyrics } from "../src/lib/music-lyrics";

test("lyrics query cleanup strips noisy tags and stays bounded", () => {
  assert.equal(cleanLyricsQuery("Song Name (Official Video) [HD]"), "Song Name");
  assert.equal(cleanLyricsQuery("x".repeat(140)).length, 120);
  assert.equal(cleanLyricsQuery("(official video)"), "");
});

test("normalization accepts bounded plain lyrics and ignores malformed provider rows", () => {
  const lyrics = normalizeLyrics([
    null,
    { trackName: "Song", artistName: "Artist", plainLyrics: "short" },
    { trackName: "S".repeat(140), artistName: "A", plainLyrics: "la ".repeat(4000), syncedLyrics: "[00:01] line" },
  ], "Fallback");
  assert.ok(lyrics);
  assert.equal(lyrics.title.length, 120);
  assert.equal(lyrics.lyrics.length, 3500);
  assert.equal(lyrics.synced, true);
});

test("synced lyric timestamps parse multiple tags, sort, and select the active line", () => {
  const lines = parseSyncedLyrics("[00:03.50]Later\n[00:01.2][00:02.25]Repeated line\n[offset:100]");
  assert.deepEqual(lines, [
    { time: 1.2, text: "Repeated line" },
    { time: 2.25, text: "Repeated line" },
    { time: 3.5, text: "Later" },
  ]);
  assert.equal(activeSyncedLyricIndex(lines, 0.9), -1);
  assert.equal(activeSyncedLyricIndex(lines, 2.4), 1);
  assert.equal(activeSyncedLyricIndex(lines, 10), 2);
});

test("provider fetch uses only fixed LRCLIB endpoint and returns no result for empty data", async () => {
  let requested = "";
  const result = await findLyrics("Song (Official Audio)", async (input) => {
    requested = String(input);
    return new Response(JSON.stringify([]), { status: 200 });
  });
  assert.equal(new URL(requested).origin, "https://lrclib.net");
  assert.equal(new URL(requested).pathname, "/api/search");
  assert.equal(new URL(requested).searchParams.get("q"), "Song");
  assert.equal(result, null);
});
