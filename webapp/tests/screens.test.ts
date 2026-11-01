import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render } from "./dom";

test("the workspace navigation keeps public groups clear and owner tools gated", async () => {
  const { IOSNav, IOSTabBar, navigationGroups } = await import("../src/components/ios/IOSNav");
  assert.deepEqual(navigationGroups.map((group) => group.label), [
    "Overview", "Create", "Community", "Music & Arcade", "Bot management",
  ]);
  assert.ok(navigationGroups.find((group) => group.label === "Community")?.tabs.includes("federations"));
  const html = render(createElement(IOSNav));
  assert.match(html, /Overview/);
  assert.match(html, /Create/);
  assert.match(html, /Music &amp; Arcade/);
  assert.match(html, /Post Studio/);
  const mobileHtml = render(createElement(IOSTabBar));
  assert.match(mobileHtml, /More workspace/);
  assert.doesNotMatch(html, /Federations|Bot management/);
});

test("the owner dashboard labels group and queue totals as loading before data arrives", async () => {
  const { default: OwnerHome } = await import("../src/components/studio/screens/OwnerHome");
  const html = render(createElement(OwnerHome));
  assert.match(html, /Loading group status/);
  assert.match(html, /Loading queue totals/);
  assert.match(html, /not measured API samples/);
  assert.doesNotMatch(html, /0 reports · 0 join requests/);
});

test("the owner dashboard first paint distinguishes pending analytics from empty data", async () => {
  const { default: OwnerHome } = await import("../src/components/studio/screens/OwnerHome");
  const html = render(createElement(OwnerHome));
  assert.match(html, /Loading recent activity/);
  assert.match(html, /Loading group activity/);
  assert.doesNotMatch(html, /Add Videl to a group/);
  assert.doesNotMatch(html, /0 commands/);
});

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
  // A series is scheduled in a named zone, and the DST policy is stated up
  // front rather than discovered on the one day a year it matters.
  assert.match(html, /Timezone/);
  assert.match(html, /daylight-saving/);
  assert.match(html, /Pause holds a series where it stands/);
});

test("a warning row keeps its lapse state out of the count", async () => {
  const { warnCaseSummary } = await import("../src/lib/group-admin");
  assert.equal(warnCaseSummary({ user_id: 7, count: 1, total: 3, reasons: [] }), "1 of 3 still count");
  assert.equal(warnCaseSummary({ user_id: 7, count: 2, reasons: [] }), "2 of 2 still count");
});
