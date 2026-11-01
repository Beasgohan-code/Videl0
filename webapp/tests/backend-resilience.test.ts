import test from "node:test";
import assert from "node:assert/strict";
import { callBackend } from "../src/lib/backend";

function withBackend(testBody: () => Promise<void>) {
  return async () => {
    const oldUrl = process.env.VIDEL_BACKEND_URL;
    const oldSecret = process.env.WEBAPP_SECRET;
    const oldFetch = globalThis.fetch;
    process.env.VIDEL_BACKEND_URL = "https://backend.test";
    process.env.WEBAPP_SECRET = "offline-resilience-test";
    try { await testBody(); }
    finally {
      globalThis.fetch = oldFetch;
      if (oldUrl === undefined) delete process.env.VIDEL_BACKEND_URL; else process.env.VIDEL_BACKEND_URL = oldUrl;
      if (oldSecret === undefined) delete process.env.WEBAPP_SECRET; else process.env.WEBAPP_SECRET = oldSecret;
    }
  };
}

test("backend authorization refusals are surfaced without retrying or exposing credentials", withBackend(async () => {
  const oldFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (_input, init) => {
    calls++;
    assert.equal(new Headers(init?.headers).get("x-videl-internal"), "offline-resilience-test");
    return Response.json({ ok: false, error: "unauthorized" }, { status: 403 });
  };
  const result = await callBackend("/internal/test", {}, { attempts: 3, timeoutMs: 100 });
  assert.equal(calls, 1, "a definitive authorization response is not retried");
  assert.equal(result.status, 403);
  assert.equal(result.code, "REJECTED");
  assert.doesNotMatch(JSON.stringify(result), /offline-resilience-test/);
}));

test("network timeouts and reachability errors are bounded and classified honestly", withBackend(async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    const failure = new Error("simulated timeout");
    failure.name = "TimeoutError";
    throw failure;
  };
  const waking = await callBackend("/internal/test", {}, { timeoutMs: 5, attempts: 1 });
  assert.equal(calls, 1);
  assert.equal(waking.code, "WAKING");
  assert.equal(waking.attempts, 1);
  assert.match(String(waking.payload.error), /starting|retrying/i);

  globalThis.fetch = async () => { throw new Error("connection refused"); };
  const unreachable = await callBackend("/internal/test", {}, { timeoutMs: 5, attempts: 1 });
  assert.equal(unreachable.code, "UNREACHABLE");
  assert.equal(unreachable.attempts, 1);
  assert.doesNotMatch(JSON.stringify(unreachable), /connection refused/);
}));
