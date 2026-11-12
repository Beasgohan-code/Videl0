import test from "node:test";
import assert from "node:assert/strict";
import { moveQueuedTrack } from "../src/lib/music-queue";

test("moving a queued track reorders a copy without mutating the original", () => {
  const tracks = ["first", "second", "third"];
  const moved = moveQueuedTrack(tracks, 2, 0);
  assert.deepEqual(moved, ["third", "first", "second"]);
  assert.deepEqual(tracks, ["first", "second", "third"]);
  assert.notEqual(moved, tracks);
});

test("queue movement refuses invalid, identical, and out-of-range positions", () => {
  const tracks = ["only"];
  for (const [from, to] of [[0, 0], [-1, 0], [0, 1], [0.5, 0]] as const) {
    assert.equal(moveQueuedTrack(tracks, from, to), tracks);
  }
});
