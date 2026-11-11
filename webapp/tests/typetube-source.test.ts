import test from "node:test";
import assert from "node:assert/strict";
import { isSafeTypeTubeAudioUrl, isYouTubeVideoId, normalizeTypeTubeSearchItem } from "../src/lib/typetube-source";
import { typeTubeResolveRoute, typeTubeSearchRoute } from "../src/lib/typetube-routes";
import { ownerMarker } from "../src/lib/auth";

test("TypeTube search normalization accepts bounded public track metadata only", () => {
  const track = normalizeTypeTubeSearchItem({
    id: "dQw4w9WgXcQ",
    title: "  Never Gonna Give You Up  ",
    duration: 213.9,
    uploader: "Rick Astley",
    arbitrary: "discard me",
    bestAudio: { url: "https://rr1.googlevideo.com/signed-secret" },
  });
  assert.deepEqual(track, {
    video_id: "dQw4w9WgXcQ",
    title: "Never Gonna Give You Up",
    channel: "Rick Astley",
    duration: "3:33",
    thumbnail: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    provider: "typetube",
  });
  assert.equal(normalizeTypeTubeSearchItem({ id: "bad", title: "bad" }), null);
  assert.equal(normalizeTypeTubeSearchItem({ id: "dQw4w9WgXcQ", title: "   " }), null);
  assert.equal(normalizeTypeTubeSearchItem({ id: "dQw4w9WgXcQ", title: "Odd duration", duration: 1e100 })?.duration, "—:—");
  assert.equal(isYouTubeVideoId("dQw4w9WgXcQ"), true);
  assert.equal(isYouTubeVideoId("https://evil.example"), false);
});

test("TypeTube search route is owner-only and requests a bounded result page", async () => {
  const previous = { owner: process.env.OWNER_ID, secret: process.env.WEBAPP_SECRET };
  process.env.OWNER_ID = "987654321";
  process.env.WEBAPP_SECRET = "synthetic-typetube-test-secret";
  let calls = 0;
  const client = {
    async search(query: string, options: { limit: number }) {
      calls += 1;
      assert.equal(query, "ambient");
      assert.equal(options.limit, 8);
      return Array.from({ length: 10 }, (_, index) => ({
        id: `dQw4w9WgXc${String.fromCharCode(81 + index)}`,
        title: `Track ${index}`,
        duration: 60,
        uploader: "Artist",
      }));
    },
    async resolve() { throw new Error("not used"); },
  };
  try {
    const guest = await typeTubeSearchRoute(new Request("https://studio.example/api/music/typetube/search?q=ambient"), () => client);
    assert.equal(guest.status, 401);
    assert.equal(calls, 0);
    const token = ownerMarker();
    assert.ok(token);
    const response = await typeTubeSearchRoute(new Request("https://studio.example/api/music/typetube/search?q=ambient", {
      headers: { cookie: `videl_owner=${token}` },
    }), () => client);
    const payload = await response.json();
    assert.equal(response.status, 200);
    assert.equal(payload.tracks.length, 8);
    assert.equal(payload.tracks[0].provider, "typetube");
    assert.equal(calls, 1);
  } finally {
    if (previous.owner === undefined) delete process.env.OWNER_ID; else process.env.OWNER_ID = previous.owner;
    if (previous.secret === undefined) delete process.env.WEBAPP_SECRET; else process.env.WEBAPP_SECRET = previous.secret;
  }
});

test("TypeTube resolver validates IDs and rejects non-CDN stream URLs", async () => {
  const previous = { owner: process.env.OWNER_ID, secret: process.env.WEBAPP_SECRET };
  process.env.OWNER_ID = "987654321";
  process.env.WEBAPP_SECRET = "synthetic-typetube-test-secret";
  let calls = 0;
  let audioUrl = "https://evil.example/file";
  const client = {
    async search() { return []; },
    async resolve(query: string) {
      calls += 1;
      assert.equal(query, "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
      return { success: true, title: "Track", author: "Artist", durationSeconds: 1e100, bestAudio: { url: audioUrl } };
    },
  };
  try {
    const token = ownerMarker();
    assert.ok(token);
    const badId = await typeTubeResolveRoute(new Request("https://studio.example/api/music/typetube/resolve?id=not-a-video!", {
      headers: { cookie: `videl_owner=${token}` },
    }), () => client);
    assert.equal(badId.status, 400);
    assert.equal(calls, 0);
    const unsafeStream = await typeTubeResolveRoute(new Request("https://studio.example/api/music/typetube/resolve?id=dQw4w9WgXcQ", {
      headers: { cookie: `videl_owner=${token}` },
    }), () => client);
    assert.equal(unsafeStream.status, 502);
    assert.equal(calls, 1);
    audioUrl = "https://rr1---sn.googlevideo.com/audio?expire=123";
    const resolved = await typeTubeResolveRoute(new Request("https://studio.example/api/music/typetube/resolve?id=dQw4w9WgXcQ", {
      headers: { cookie: `videl_owner=${token}` },
    }), () => client);
    const payload = await resolved.json();
    assert.equal(resolved.status, 200);
    assert.equal(payload.track.audio_url, audioUrl);
    assert.equal(payload.track.channel, "Artist");
    assert.equal(payload.track.duration_seconds, 0);
    assert.equal(calls, 2);
  } finally {
    if (previous.owner === undefined) delete process.env.OWNER_ID; else process.env.OWNER_ID = previous.owner;
    if (previous.secret === undefined) delete process.env.WEBAPP_SECRET; else process.env.WEBAPP_SECRET = previous.secret;
  }
});

test("TypeTube stream URLs are restricted to HTTPS Google Video hosts", () => {
  assert.equal(isSafeTypeTubeAudioUrl("https://rr1---sn.googlevideo.com/audio?expire=1"), true);
  for (const value of [
    "http://rr1.googlevideo.com/audio",
    "https://googlevideo.com.evil.example/audio",
    "https://rr1.googlevideo.com:444/audio",
    "https://user:pass@rr1.googlevideo.com/audio",
    "https://example.com/audio",
    "not a URL",
  ]) assert.equal(isSafeTypeTubeAudioUrl(value), false, String(value));
});
