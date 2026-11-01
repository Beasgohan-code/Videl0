import { test } from "node:test";
import assert from "node:assert/strict";
import { dashboardMetricValue, DEFAULT_DASHBOARD_WIDGETS, moveDashboardItem, normalizeDashboardOrder, setDashboardItemVisible } from "../src/lib/dashboard-layout";

test("the default dashboard puts key metrics, attention and actions first", () => {
  assert.deepEqual(DEFAULT_DASHBOARD_WIDGETS.slice(0, 3), ["metrics", "pulse", "actions"]);
});

test("dashboard values distinguish loading and unavailable from a measured zero", () => {
  assert.equal(dashboardMetricValue(undefined, "loading"), "Loading…");
  assert.equal(dashboardMetricValue(undefined, "unavailable"), "Unavailable");
  assert.equal(dashboardMetricValue(0, "available"), "0");
  assert.equal(dashboardMetricValue(undefined, "available"), "—");
  assert.equal(dashboardMetricValue(Number.NaN, "available"), "—");
});

test("dashboard preferences keep only unique supported items and append newly available defaults", () => {
  assert.deepEqual(
    normalizeDashboardOrder(["activity", "unknown", "activity", 4], ["activity", "groups", "metrics"] as const, ["metrics", "groups"] as const),
    ["activity", "metrics", "groups"],
  );
});

test("dashboard items can be reordered and hidden or restored without duplicates", () => {
  const initial = ["metrics", "activity", "groups"] as const;
  assert.deepEqual(moveDashboardItem(initial, "activity", -1), ["activity", "metrics", "groups"]);
  assert.deepEqual(setDashboardItemVisible(initial, "activity", false), ["metrics", "groups"]);
  assert.deepEqual(setDashboardItemVisible(["metrics", "groups"], "activity", true), ["metrics", "groups", "activity"]);
  assert.deepEqual(setDashboardItemVisible(initial, "activity", true), [...initial]);
});
