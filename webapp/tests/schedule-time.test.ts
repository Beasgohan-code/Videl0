import test from "node:test";
import assert from "node:assert/strict";
import {
  describeInZone,
  nextSeriesRun,
  timezoneOptions,
  wallTimeOf,
  zonedWallToUtc,
} from "../src/lib/schedule-time";

const UTC = (value: string) => new Date(value).toISOString();

test("a wall clock is read in the chosen zone, not on the device", () => {
  assert.deepEqual(zonedWallToUtc("2026-10-25T09:00", "Asia/Kolkata"), {
    iso: UTC("2026-10-25T03:30:00Z"),
    shifted: false,
  });
  assert.deepEqual(zonedWallToUtc("2026-12-01T09:00", "Europe/London"), {
    iso: UTC("2026-12-01T09:00:00Z"),
    shifted: false,
  });
  assert.deepEqual(zonedWallToUtc("2026-07-01T09:00", "Europe/London"), {
    iso: UTC("2026-07-01T08:00:00Z"),
    shifted: false,
  });
});

test("a spring-forward gap moves to the first real minute", () => {
  const result = zonedWallToUtc("2027-03-14T02:30", "America/New_York");
  assert.equal(result?.iso, UTC("2027-03-14T07:00:00Z"));
  assert.equal(result?.shifted, true);
  assert.equal(wallTimeOf(result!.iso, "America/New_York"), "03:00");
});

test("a repeated wall clock during fall-back resolves to one instant", () => {
  const first = zonedWallToUtc("2026-11-01T01:30", "America/New_York");
  const second = zonedWallToUtc("2026-11-01T01:30", "America/New_York");
  assert.equal(first?.iso, UTC("2026-11-01T05:30:00Z"));
  assert.equal(first?.shifted, false);
  assert.equal(second?.iso, first?.iso);
});

test("an unknown zone or malformed clock is refused instead of guessed", () => {
  assert.equal(zonedWallToUtc("2026-10-25T09:00", "Mars/Olympus"), null);
  assert.equal(zonedWallToUtc("2026-02-30T09:00", "UTC"), null);
  assert.equal(zonedWallToUtc("tomorrow at nine", "UTC"), null);
});

test("the next run is strictly in the future and keeps the wall clock", () => {
  const now = Date.parse("2026-10-21T12:00:00Z");
  const daily = nextSeriesRun("2026-10-21T09:00", "Asia/Kolkata", "daily", now);
  assert.equal(daily?.iso, UTC("2026-10-22T03:30:00Z"));
  const weekly = nextSeriesRun("2026-10-21T09:00", "Asia/Kolkata", "weekly", now);
  assert.equal(weekly?.iso, UTC("2026-10-28T03:30:00Z"));
});

test("display names the zone so the owner is never guessing", () => {
  const text = describeInZone("2026-10-25T03:30:00Z", "Asia/Kolkata", "en-GB");
  assert.match(text, /09:00/);
  assert.match(text, /IST|GMT\+5:30/);
});

test("supported zones always include the preferred one and UTC", () => {
  const zones = timezoneOptions("Asia/Kolkata");
  assert.ok(zones.includes("UTC"));
  assert.equal(zones.filter((zone) => zone === "Asia/Kolkata").length, 1);
});
