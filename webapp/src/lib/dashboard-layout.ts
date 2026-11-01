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

export type DashboardSourceState = "loading" | "ready" | "stale" | "unavailable";

export function dashboardSourceFailure(state: DashboardSourceState): DashboardSourceState {
  return state === "ready" || state === "stale" ? "stale" : "unavailable";
}

export const DASHBOARD_WIDGET_STORAGE_KEY = "videl-owner-home-widgets-v1";
export const DASHBOARD_ACTION_STORAGE_KEY = "videl-owner-home-actions-v1";

export interface DashboardPreferenceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function readDashboardPreferences<T extends string>(
  storage: Pick<DashboardPreferenceStorage, "getItem">,
  widgetDefaults: readonly DashboardWidgetId[],
  actionDefaults: readonly T[],
): { widgets: DashboardWidgetId[]; actions: T[] } {
  try {
    const savedWidgets = storage.getItem(DASHBOARD_WIDGET_STORAGE_KEY);
    const savedActions = storage.getItem(DASHBOARD_ACTION_STORAGE_KEY);
    const widgetAllowed = DASHBOARD_WIDGETS.map(({ id }) => id);
    return {
      widgets: restoreSerializedOrder(savedWidgets, widgetAllowed, widgetDefaults),
      actions: restoreSerializedOrder(savedActions, actionDefaults, actionDefaults),
    };
  } catch {
    return { widgets: [...widgetDefaults], actions: [...actionDefaults] };
  }
}

function restoreSerializedOrder<T extends string>(serialized: string | null, allowed: readonly T[], defaults: readonly T[]): T[] {
  if (serialized === null) return [...defaults];
  try { return restoreDashboardOrder(JSON.parse(serialized), allowed, defaults); }
  catch { return [...defaults]; }
}

export function restoreDashboardOrder<T extends string>(saved: unknown, allowed: readonly T[], defaults: readonly T[]): T[] {
  // Version 1 stored only the visible order. Its omissions are user-hidden items,
  // so do not resurrect them during migration. Version 2 records the known set,
  // allowing genuinely new defaults to be appended without losing visibility choices.
  const envelope = saved && typeof saved === "object" && !Array.isArray(saved)
    ? saved as { version?: unknown; visible?: unknown; known?: unknown }
    : null;
  if (envelope && (envelope.version !== 2 || !Array.isArray(envelope.visible) || !Array.isArray(envelope.known))) return [...defaults];
  if (!envelope && !Array.isArray(saved)) return [...defaults];
  const visible = envelope ? envelope.visible : saved;
  const known = envelope && Array.isArray(envelope.known)
    ? envelope.known.filter((value): value is T => typeof value === "string" && allowed.includes(value as T))
    : [...allowed];
  const savedVisible = normalizeDashboardOrder(visible, allowed, []);
  if (Array.isArray(visible) && visible.length > 0 && savedVisible.length === 0) return [...defaults];
  return [...savedVisible, ...defaults.filter((value) => !known.includes(value) && !savedVisible.includes(value))];
}

export function writeDashboardPreferences<T extends string>(
  storage: Pick<DashboardPreferenceStorage, "setItem">,
  widgets: readonly DashboardWidgetId[],
  actions: readonly T[],
  knownActions: readonly T[] = actions,
): void {
  try {
    storage.setItem(DASHBOARD_WIDGET_STORAGE_KEY, JSON.stringify({ version: 2, visible: widgets, known: DASHBOARD_WIDGETS.map(({ id }) => id) }));
    storage.setItem(DASHBOARD_ACTION_STORAGE_KEY, JSON.stringify({ version: 2, visible: actions, known: knownActions }));
  } catch {
    // Preferences still apply in memory when browser storage is blocked or full.
  }
}

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
