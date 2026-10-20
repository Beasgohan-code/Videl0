import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render } from "./dom";

test("the backend strip starts quiet instead of assuming an outage", async () => {
  // Server rendering runs no effect, so this is the first paint: the strip must
  // not claim the backend is down before it has asked.
  const { BackendStatus } = await import("../src/components/studio/BackendStatus");
  const html = render(createElement(BackendStatus));
  assert.equal(typeof html, "string");
  assert.ok(!/down|unreachable/i.test(html), "no outage claim before a probe");
});

test("the release panel renders without inventing a backend revision", async () => {
  const { default: Settings } = await import("../src/components/studio/screens/Settings");
  const html = render(createElement(Settings));
  assert.match(html, /Release check/);
  assert.match(html, /Bot backend/);
  assert.ok(!/undefined/.test(html), "no undefined leaks into the panel");
});

test("scheduled publishing renders its queue states", async () => {
  const { ScheduledPosts } = await import("../src/components/studio/ScheduledPosts");
  const html = render(
    createElement(ScheduledPosts, {
      chatId: "-1001",
      text: "hello",
      mediaUrl: "",
      buttons: [],
      hasLocalImage: false,
      reviewed: true,
      disabled: false,
    }),
  );
  assert.match(html, /Scheduled publishing/);
  assert.match(html, /Schedule reviewed post/);
  // Copying a finished post creates a new job, so the promise is stated up front.
  assert.match(html, /A finished post can be copied as a new post/);
  // Repeating is offered as part of the queue, with the series rule stated.
  assert.match(html, /Every day/);
  assert.match(html, /cancelling it stops the series/);
});
