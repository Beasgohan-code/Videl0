import assert from "node:assert/strict";
import test from "node:test";
import { simulateSafety } from "../src/lib/safety-simulation";

test("link locks use Videl's supported URL shapes", () => {
  const result = simulateSafety({ lock_links: true }, [], "Join here: t.me/videl", "text", "member");
  assert.equal(result.blockedBy, "links");
});

test("administrator and approved senders bypass content locks", () => {
  for (const sender of ["admin", "approved"] as const) {
    const result = simulateSafety({ lock_photos: true }, [], "", "photo", sender);
    assert.equal(result.exemptFromLocks, true);
    assert.equal(result.blockedBy, null);
  }
});

test("specific media locks win before the general media lock", () => {
  const result = simulateSafety({ lock_photos: true, lock_media: true }, [], "", "photo", "member");
  assert.equal(result.blockedBy, "photos");
});

test("the longest matching auto-answer wins and commands stay quiet", () => {
  const filters = [
    { keyword: "hello", reply: "Short reply" },
    { keyword: "hello videl", reply: "Specific reply" },
  ];
  assert.equal(simulateSafety({}, filters, "hello Videl!", "text", "member").autoReply, "Specific reply");
  assert.equal(simulateSafety({}, filters, "/hello Videl", "text", "member").autoReply, null);
  assert.equal(simulateSafety({}, filters, "hello Videl", "photo", "member").autoReply, null);
});

test("simulation remains side-effect free when no locks match", () => {
  const result = simulateSafety({}, [], "Just checking", "text", "member");
  assert.deepEqual(result, { exemptFromLocks: false, blockedBy: null, autoReply: null });
});
