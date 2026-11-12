import test from "node:test";
import assert from "node:assert/strict";
import { appendPlaylistTracks, makePlaylist, MAX_PLAYLIST_TRACKS, MAX_SAVED_PLAYLISTS, normalizePlaylists } from "../src/lib/music-playlists";

const track = (id: string, title = id) => ({ video_id: id, title, channel: "Artist", duration: "3:00", thumbnail: "" });

test("playlist creation trims names and bounds saved tracks", () => {
  const tracks = Array.from({ length: MAX_PLAYLIST_TRACKS + 4 }, (_, i) => track(`id_${String(i).padStart(8, "0")}`));
  const playlist = makePlaylist("  Road   Trip ", tracks, "playlist-1", 10);
  assert.equal(playlist?.name, "Road Trip");
  assert.equal(playlist?.tracks.length, MAX_PLAYLIST_TRACKS);
  assert.equal(playlist?.updatedAt, 10);
});

test("malformed local storage rows and unsafe track IDs are discarded", () => {
  const playlists = normalizePlaylists([
    null,
    { id: "ok", name: " Mix ", tracks: [track("abcdefg1234"), track("bad")], updatedAt: 1 },
  ]);
  assert.equal(playlists.length, 1);
  assert.equal(playlists[0].name, "Mix");
  assert.equal(playlists[0].tracks.length, 1);
});

test("playlist list and queue append are bounded without truncating existing queue", () => {
  const rows = Array.from({ length: MAX_SAVED_PLAYLISTS + 3 }, (_, i) => ({ id: `p${i}`, name: `P${i}`, tracks: [] }));
  assert.equal(normalizePlaylists(rows).length, MAX_SAVED_PLAYLISTS);
  const queue = [track("existng_001")];
  const added = appendPlaylistTracks(queue, Array.from({ length: 5 }, (_, i) => track(`add${String(i).padStart(8, "0")}`)), 3);
  assert.deepEqual(added.map((item) => item.video_id), ["existng_001", "add00000000", "add00000001"]);
  assert.deepEqual(queue.map((item) => item.video_id), ["existng_001"]);
});
