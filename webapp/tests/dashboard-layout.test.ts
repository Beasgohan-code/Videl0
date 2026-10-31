import { test } from "node:test";
import assert from "node:assert/strict";
import { moveDashboardItem, normalizeDashboardOrder, setDashboardItemVisible } from "../src/lib/dashboard-layout";

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
