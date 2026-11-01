import { test } from "node:test";
import assert from "node:assert/strict";
import { dashboardMetricValue, DEFAULT_DASHBOARD_WIDGETS, DASHBOARD_WIDGET_STORAGE_KEY, DASHBOARD_ACTION_STORAGE_KEY, dashboardSourceFailure, moveDashboardItem, normalizeDashboardOrder, readDashboardPreferences, restoreDashboardOrder, setDashboardItemVisible, writeDashboardPreferences } from "../src/lib/dashboard-layout";

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

test("saved dashboard preferences survive reloads and newer defaults", () => {
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
  };
  const defaults = [...DEFAULT_DASHBOARD_WIDGETS];
  const actions = ["post", "groups", "analytics"] as const;
  const initial = readDashboardPreferences(storage, defaults, actions);
  assert.deepEqual(initial.widgets, defaults);
  assert.deepEqual(initial.actions, actions);

  const customWidgets = moveDashboardItem(setDashboardItemVisible(initial.widgets, "scheduled", false), "pulse", 1);
  const customActions = moveDashboardItem(initial.actions, "analytics", -1);
  writeDashboardPreferences(storage, customWidgets, customActions);
  assert.ok(values.has(DASHBOARD_WIDGET_STORAGE_KEY));
  assert.ok(values.has(DASHBOARD_ACTION_STORAGE_KEY));

  const nextDefaults = ["metrics", "pulse", "actions", "health", "activity", "groups", "scheduled", "automation", "onboarding"] as const;
  const restored = readDashboardPreferences(storage, nextDefaults, actions);
  assert.deepEqual(restored.widgets, customWidgets);
  assert.deepEqual(restored.actions, customActions);
});

test("versioned layouts preserve hidden items but append newly introduced defaults", () => {
  const allowed = ["groups", "metrics", "new-widget"] as const;
  const saved = { version: 2, visible: ["groups"], known: ["groups", "metrics"] };
  assert.deepEqual(restoreDashboardOrder(saved, allowed, ["metrics", "groups", "new-widget"]), ["groups", "new-widget"]);
  assert.deepEqual(restoreDashboardOrder(["groups"], allowed, ["groups", "metrics", "new-widget"]), ["groups"]);
  assert.deepEqual(restoreDashboardOrder({ version: 99 }, allowed, allowed), allowed);
  assert.deepEqual(restoreDashboardOrder({ version: 2 }, allowed, allowed), allowed);
  assert.deepEqual(restoreDashboardOrder(null, allowed, allowed), allowed);
  assert.deepEqual(restoreDashboardOrder(["removed-widget"], allowed, allowed), allowed);
});

test("invalid, outdated, and inaccessible saved layouts fall back safely", () => {
  const values = new Map<string, string>([
    [DASHBOARD_WIDGET_STORAGE_KEY, JSON.stringify(["groups", "removed-widget", "groups", 3])],
    [DASHBOARD_ACTION_STORAGE_KEY, "{"],
  ]);
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
  };
  const actions = ["post", "groups"] as const;
  const recovered = readDashboardPreferences(storage, DEFAULT_DASHBOARD_WIDGETS, actions);
  assert.deepEqual(recovered.widgets, ["groups"], "legacy omissions remain hidden while removed IDs are discarded");
  assert.deepEqual(recovered.actions, actions);
  assert.deepEqual(readDashboardPreferences({ getItem: () => { throw new Error("blocked"); } }, DEFAULT_DASHBOARD_WIDGETS, actions), {
    widgets: DEFAULT_DASHBOARD_WIDGETS,
    actions,
  });
  assert.doesNotThrow(() => writeDashboardPreferences({ setItem: () => { throw new Error("quota"); } }, DEFAULT_DASHBOARD_WIDGETS, actions));
});

test("refresh failures distinguish stale data from never-loaded data", () => {
  assert.equal(dashboardSourceFailure("loading"), "unavailable");
  assert.equal(dashboardSourceFailure("unavailable"), "unavailable");
  assert.equal(dashboardSourceFailure("ready"), "stale");
  assert.equal(dashboardSourceFailure("stale"), "stale");
});

test("dashboard items can be reordered and hidden or restored without duplicates", () => {
  const initial = ["metrics", "activity", "groups"] as const;
  assert.deepEqual(moveDashboardItem(initial, "activity", -1), ["activity", "metrics", "groups"]);
  assert.deepEqual(setDashboardItemVisible(initial, "activity", false), ["metrics", "groups"]);
  assert.deepEqual(setDashboardItemVisible(["metrics", "groups"], "activity", true), ["metrics", "groups", "activity"]);
  assert.deepEqual(setDashboardItemVisible(initial, "activity", true), [...initial]);
});
