import test from "node:test";
import assert from "node:assert/strict";
import { clearMediaSource, isCurrentMediaSource, LatestRequestGate, settleLatest } from "../src/lib/latest-request";

test("changing tracks pauses and unloads the previous source before resolution", () => {
  const calls: string[] = [];
  clearMediaSource({
    pause: () => calls.push("pause"),
    removeAttribute: (name: string) => calls.push(`remove:${name}`),
    load: () => calls.push("load"),
  } as unknown as HTMLAudioElement);
  assert.deepEqual(calls, ["pause", "remove:src", "load"]);
});

test("media events are accepted only for the currently selected stream URL", () => {
  const base = "https://studio.example/studio";
  assert.equal(isCurrentMediaSource(
    "https://studio.example/api/music/track/track-b?task_id=b",
    "/api/music/track/track-b?task_id=b",
    base,
  ), true);
  assert.equal(isCurrentMediaSource(
    "https://studio.example/api/music/track/track-a?task_id=a",
    "/api/music/track/track-b?task_id=b",
    base,
  ), false);
  assert.equal(isCurrentMediaSource("", "/api/music/track/track-b", base), false);
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

test("late playback rejection cannot overwrite the latest selected track", async () => {
  const gate = new LatestRequestGate();
  const state = { current: "", playing: false, loading: true, error: "" };
  const first = deferred<void>();
  const second = deferred<void>();

  const firstRun = settleLatest(gate, gate.begin(), () => first.promise, {
    onSuccess: () => { state.playing = true; },
    onError: () => { state.playing = false; state.loading = false; state.error = "A failed"; },
    onFinally: () => { state.loading = false; },
  });
  state.current = "track-b";
  state.playing = false;
  state.loading = true;
  state.error = "";
  const secondRun = settleLatest(gate, gate.begin(), () => second.promise, {
    onSuccess: () => { state.playing = true; },
    onError: () => { state.playing = false; state.loading = false; state.error = "B failed"; },
    onFinally: () => { state.loading = false; },
  });

  second.resolve();
  await secondRun;
  first.reject(new Error("stale A rejection"));
  await firstRun;

  assert.deepEqual(state, { current: "track-b", playing: true, loading: false, error: "" });
});

test("late search response cannot replace latest results or loading/error state", async () => {
  const gate = new LatestRequestGate();
  const state = { results: [] as string[], searching: true, error: "" };
  const first = deferred<string[]>();
  const second = deferred<string[]>();

  const firstRun = settleLatest(gate, gate.begin(), () => first.promise, {
    onSuccess: (results) => { state.results = results; },
    onError: () => { state.error = "A failed"; },
    onFinally: () => { state.searching = false; },
  });
  const secondRun = settleLatest(gate, gate.begin(), () => second.promise, {
    onSuccess: (results) => { state.results = results; },
    onError: () => { state.error = "B failed"; },
    onFinally: () => { state.searching = false; },
  });

  second.resolve(["B result"]);
  await secondRun;
  first.resolve(["A stale result"]);
  await firstRun;

  assert.deepEqual(state, { results: ["B result"], searching: false, error: "" });
});

test("only the latest search owns its error and completion state", async () => {
  const gate = new LatestRequestGate();
  const state = { searching: true, error: "" };
  const first = deferred<string[]>();
  const second = deferred<string[]>();

  const firstRun = settleLatest(gate, gate.begin(), () => first.promise, {
    onSuccess: () => {},
    onError: () => { state.error = "A failed"; },
    onFinally: () => { state.searching = false; },
  });
  const secondRun = settleLatest(gate, gate.begin(), () => second.promise, {
    onSuccess: () => {},
    onError: () => { state.error = "B failed"; },
    onFinally: () => { state.searching = false; },
  });

  first.resolve(["A stale result"]);
  await firstRun;
  assert.deepEqual(state, { searching: true, error: "" });
  second.reject(new Error("latest search failed"));
  await secondRun;
  assert.deepEqual(state, { searching: false, error: "B failed" });
});
