export const DASHBOARD_WIDGETS = [
  { id: "metrics", label: "Community metrics" },
  { id: "pulse", label: "Community pulse" },
  { id: "actions", label: "Quick actions" },
  { id: "health", label: "System and API health" },
  { id: "onboarding", label: "New-member insights" },
  { id: "scheduled", label: "Scheduled broadcasts" },
  { id: "automation", label: "Automation runs" },
  { id: "activity", label: "Recent activity" },
  { id: "groups", label: "Top groups" },
] as const;

export type DashboardWidgetId = (typeof DASHBOARD_WIDGETS)[number]["id"];
export const DEFAULT_DASHBOARD_WIDGETS: DashboardWidgetId[] = DASHBOARD_WIDGETS.map(({ id }) => id);

export type DashboardValueState = "loading" | "unavailable" | "available";

/** Never turn a missing/unavailable measurement into a plausible-looking zero. */
export function dashboardMetricValue(value: number | undefined, state: DashboardValueState): string {
  if (state === "loading") return "Loading…";
  if (state === "unavailable") return "Unavailable";
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "—";
}

export function normalizeDashboardOrder<T extends string>(
  saved: unknown,
  allowed: readonly T[],
  fallback: readonly T[],
): T[] {
  if (!Array.isArray(saved)) return [...fallback];
  const valid = saved.filter((value): value is T => typeof value === "string" && allowed.includes(value as T));
  return [...new Set(valid), ...fallback.filter((value) => !valid.includes(value))];
}

export function moveDashboardItem<T extends string>(items: readonly T[], item: T, direction: -1 | 1): T[] {
  const from = items.indexOf(item);
  const to = from + direction;
  if (from < 0 || to < 0 || to >= items.length) return [...items];
  const result = [...items];
  [result[from], result[to]] = [result[to], result[from]];
  return result;
}

export function setDashboardItemVisible<T extends string>(items: readonly T[], item: T, visible: boolean): T[] {
  if (visible) return items.includes(item) ? [...items] : [...items, item];
  return items.filter((value) => value !== item);
}
