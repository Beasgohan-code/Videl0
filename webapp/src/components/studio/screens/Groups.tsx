"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStudio } from "../StudioProvider";
import {
  AlertCircle,
  Check,
  ExternalLink,
  Layers,
  Loader2,
  Lock,
  MessageSquare,
  Minus,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldCheck,
  Trash2,
  UserX,
  Users,
} from "lucide-react";
import {
  BLACKLIST_MODES,
  BULK_LIMIT,
  FILTERS,
  PRESET_COPY,
  SETTING_KEYS,
  PRESET_ORDER,
  PROTECTION_GROUPS,
  SORTS,
  applySettings,
  applySettingsToChats,
  bulkSelection,
  displayTitle,
  errorHint,
  flag,
  memberLabel,
  numberValue,
  effectiveGuards,
  protectionSummary,
  textValue,
  toggleSelected,
  visibleGroups,
  type Group,
  type GroupDetail,
  type GroupFilter,
  type GroupSettings,
  type GroupSort,
  type PresetId,
} from "@/lib/group-admin";

type Tab = "protection" | "community" | "moderation" | "members";

const TABS: { id: Tab; label: string }[] = [
  { id: "protection", label: "Protection" },
  { id: "community", label: "Community" },
  { id: "moderation", label: "Moderation" },
  { id: "members", label: "Members" },
];

function Toggle({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-3">
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {description ? <div className="mt-0.5 text-xs text-[var(--ios-label-secondary)]">{description}</div> : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={`${checked ? "Disable" : "Enable"} ${label}`}
        aria-pressed={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-40 ${checked ? "bg-[#30D158]" : "bg-white/15"}`}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${checked ? "translate-x-6" : "translate-x-1"}`}
        />
      </button>
    </div>
  );
}

function PanelNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs leading-relaxed text-amber-100">
      {children}
    </div>
  );
}

export default function GroupsPage({ automation = false }: { automation?: boolean } = {}) {
  const { open, selectGroup } = useStudio();
  const savingRef = useRef(false);
  const detailRequest = useRef(0);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<GroupFilter>("all");
  const [sort, setSort] = useState<GroupSort>("name");
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [detailState, setDetailState] = useState<"idle" | "loading" | "ready" | "unsupported" | "error">("idle");
  const [detailMessage, setDetailMessage] = useState("");
  const [tab, setTab] = useState<Tab>("protection");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [selectMode, setSelectMode] = useState(false);
  const [bulkPreset, setBulkPreset] = useState<PresetId>("balanced");
  const [bulkResult, setBulkResult] = useState("");
  const [welcomeDraft, setWelcomeDraft] = useState("");
  const [goodbyeDraft, setGoodbyeDraft] = useState("");
  const [rulesDraft, setRulesDraft] = useState("");
  const [blacklistWord, setBlacklistWord] = useState("");
  const [warnLimitDraft, setWarnLimitDraft] = useState(3);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/groups", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Group data could not be loaded");
      const chats: Group[] = Array.isArray(data.chats) ? data.chats : [];
      setGroups(chats);
      setSelected((current) => (chats.some((group) => group.id === current) ? current : (chats[0]?.id ?? null)));
      if (data.truncated) setNotice("The bot serves more groups than this page lists. Refresh after the backend prunes inactive chats.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Group data could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = useMemo(() => groups.find((group) => group.id === selected) || null, [groups, selected]);

  const loadDetail = useCallback(async (id: number, { silent = false }: { silent?: boolean } = {}) => {
    const ticket = ++detailRequest.current;
    if (!silent) {
      setDetailState("loading");
      setDetailMessage("");
    }
    try {
      const response = await fetch(`/api/groups/${id}`, { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (ticket !== detailRequest.current) return;
      if (!response.ok || !data.ok) {
        setDetail(null);
        setDetailState(response.status === 501 ? "unsupported" : "error");
        setDetailMessage(
          response.status === 501
            ? "Detailed panels arrive with the next Render deploy. Protection switches already work."
            : errorHint(String(data.error || "Group detail could not be loaded"), response.status),
        );
        return;
      }
      if (!data.chat || !data.settings) {
        // Older backend: the route exists but has no detail payload yet.
        setDetail(null);
        setDetailState("unsupported");
        setDetailMessage("Detailed panels need the updated bot backend. Redeploy Render to load warnings, notes and blacklist data.");
        return;
      }
      setDetail(data as GroupDetail);
      setDetailState("ready");
    } catch (e) {
      if (ticket !== detailRequest.current) return;
      setDetail(null);
      setDetailState("error");
      setDetailMessage(e instanceof Error ? e.message : "Group detail could not be loaded");
    }
  }, []);

  useEffect(() => {
    if (selected === null) {
      setDetail(null);
      setDetailState("idle");
      return;
    }
    setDetail(null);
    void loadDetail(selected);
  }, [selected, loadDetail]);

  useEffect(() => {
    if (!detail) return;
    setWelcomeDraft(textValue(detail.settings, "welcome_message"));
    setGoodbyeDraft(textValue(detail.settings, "goodbye_message"));
    setRulesDraft(textValue(detail.settings, "rules"));
    setWarnLimitDraft(numberValue(detail.settings, "warn_threshold", 3));
  }, [detail]);

  function mergeSettings(patch: GroupSettings) {
    setGroups((all) => all.map((group) => (group.id === selected ? applySettings(group, patch) : group)));
    setDetail((current) => (current ? { ...current, settings: { ...current.settings, ...patch } } : current));
  }

  async function setLock(key: string, enabled: boolean) {
    if (!active || savingRef.current) return;
    savingRef.current = true;
    setSaving(key);
    setError("");
    setNotice("");
    // Flip immediately so the switch never lags behind the tap.
    mergeSettings({ [key]: enabled });
    try {
      const response = await fetch("/api/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: active.id, settings: { [key]: enabled } }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(String(data.error || "Setting update failed"));
      setNotice(enabled ? "Lock enabled and saved." : "Lock disabled and saved.");
    } catch (e) {
      mergeSettings({ [key]: !enabled });
      setError(errorHint(e instanceof Error ? e.message : "Setting update failed"));
    } finally {
      savingRef.current = false;
      setSaving(null);
    }
  }

  async function runAction(body: Record<string, unknown>, options: { refreshDetail?: boolean; success?: string } = {}) {
    if (!active) return false;
    setSaving(String(body.action));
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/groups/${active.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        const hint =
          response.status === 501
            ? "This needs the updated bot backend. Redeploy the Render service, then retry."
            : errorHint(String(data.error || "The change was not saved"), response.status);
        throw new Error(hint);
      }
      if (data.settings && typeof data.settings === "object") mergeSettings(data.settings as GroupSettings);
      setNotice(options.success || "Saved to MongoDB.");
      if (options.refreshDetail) void loadDetail(active.id, { silent: true });
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "The change was not saved");
      return false;
    } finally {
      setSaving(null);
    }
  }

  async function applyBulk(ids: number[], preset: PresetId) {
    if (!ids.length) return;
    const { ids: target, overflow } = bulkSelection(ids);
    setSaving("bulk");
    setError("");
    setBulkResult("");
    try {
      const response = await fetch("/api/groups/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_ids: target, action: "preset", preset }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(String(data.error || "Bulk update failed"));
      const applied = Number(data.updated || 0);
      setBulkResult(`${applied} of ${target.length} groups updated${overflow ? ` · ${overflow} left out` : ""}.`);
      const results = Array.isArray(data.results) ? data.results : [];
      const failures = results.filter((item: { ok?: boolean }) => !item.ok).length;
      if (failures) setError(`${failures} group${failures === 1 ? "" : "s"} could not be changed. Check admin rights in Telegram.`);
      await load();
      if (selected !== null) void loadDetail(selected, { silent: true });
    } catch (e) {
      setError(errorHint(e instanceof Error ? e.message : "Bulk update failed"));
    } finally {
      setSaving(null);
    }
  }

  const visible = useMemo(() => visibleGroups(groups, { query, filter, sort }), [groups, query, filter, sort]);
  const summary = useMemo(
    () => ({
      total: groups.length,
      protected: groups.filter((group) => protectionSummary(group.settings).active > 0).length,
      warns: groups.reduce((total, group) => total + (group.counts?.warns ?? 0), 0),
      unreachable: groups.filter((group) => !group.available).length,
    }),
    [groups],
  );

  const activeSettings = detail?.settings ?? active?.settings ?? {};
  const guardsOn = effectiveGuards(activeSettings);
  const community = detailState === "ready" ? detail?.community : undefined;
  const bulkIds = bulkSelection(picked);

  return (
    <main className="mx-auto max-w-6xl py-5 sm:py-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ios-caps text-[11px]">Videl · Community</p>
          <h1 className="mt-2 ios-title">{automation ? "Automation" : "Group Manager"}</h1>
          <p className="mt-1 ios-subheadline">
            Locks, greetings, warnings and blacklists — read from MongoDB, written through the bot.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => void load()} className="ios-btn ios-btn-glass text-sm" disabled={loading || saving !== null}>
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            onClick={() => {
              setSelectMode((value) => !value);
              setPicked([]);
              setBulkResult("");
            }}
            aria-pressed={selectMode}
            className={`ios-btn text-sm ${selectMode ? "ios-btn-primary" : "ios-btn-glass"}`}
          >
            <Layers size={16} /> {selectMode ? "Done selecting" : "Bulk edit"}
          </button>
        </div>
      </header>

      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: "Served groups", value: summary.total },
          { label: "With locks on", value: summary.protected },
          { label: "Members warned", value: summary.warns },
          { label: "Unreachable", value: summary.unreachable },
        ].map((stat) => (
          <div key={stat.label} className="ios-card p-3">
            <div className="text-2xl font-semibold tabular-nums">{stat.value}</div>
            <div className="ios-caption mt-0.5">{stat.label}</div>
          </div>
        ))}
      </div>

      {error && (
        <div role="status" className="mt-4 flex items-start gap-2 rounded-2xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm text-amber-100">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError("")} className="text-xs underline">Dismiss</button>
        </div>
      )}
      {notice && !error && (
        <div role="status" className="mt-4 flex items-start gap-2 rounded-2xl border border-emerald-300/20 bg-emerald-300/5 p-3 text-sm text-emerald-100">
          <Check size={16} className="mt-0.5 shrink-0" /> {notice}
        </div>
      )}

      {selectMode && (
        <section className="mt-4 ios-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">Bulk protection</h2>
              <p className="ios-caption mt-1">
                {picked.length} selected · up to {BULK_LIMIT} groups per change
                {bulkIds.overflow ? ` · ${bulkIds.overflow} will be left out` : ""}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="sr-only" htmlFor="bulk-preset">Bulk preset</label>
              <select
                id="bulk-preset"
                value={bulkPreset}
                onChange={(event) => setBulkPreset(event.target.value as PresetId)}
                className="ios-input text-sm"
              >
                {PRESET_ORDER.map((id) => (
                  <option key={id} value={id}>{PRESET_COPY[id].label}</option>
                ))}
              </select>
              <button
                onClick={() => void applyBulk(picked, bulkPreset)}
                disabled={!picked.length || saving !== null}
                className="ios-btn ios-btn-primary text-sm disabled:opacity-40"
              >
                {saving === "bulk" ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                Apply to {picked.length || 0}
              </button>
            </div>
          </div>
          {bulkResult && <p className="mt-2 text-xs text-emerald-200">{bulkResult}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={() => setPicked(visible.map((group) => group.id).slice(0, BULK_LIMIT))} className="ios-chip text-xs">
              Select visible ({Math.min(visible.length, BULK_LIMIT)})
            </button>
            <button onClick={() => setPicked([])} className="ios-chip text-xs">Clear selection</button>
          </div>
        </section>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <section className="ios-card p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Served groups</h2>
            <span className="ios-pill">{visible.length} shown</span>
          </div>
          <label className="sr-only" htmlFor="group-search">Search served groups</label>
          <div className="relative mt-4">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ios-label-tertiary)]" />
            <input
              id="group-search"
              aria-label="Search served groups"
              placeholder="Search group name, @username or ID…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="ios-input pl-9"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                onClick={() => setFilter(item.id)}
                aria-pressed={filter === item.id}
                className="ios-chip text-xs"
                aria-selected={filter === item.id}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <label htmlFor="group-sort" className="ios-caption">Sort</label>
            <select
              id="group-sort"
              aria-label="Sort groups"
              value={sort}
              onChange={(event) => setSort(event.target.value as GroupSort)}
              className="ios-input py-1.5 text-xs"
            >
              {SORTS.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
          </div>

          <div className="mt-3 space-y-2">
            {loading && <p className="ios-caption p-3">Loading served chats…</p>}
            {!loading && !groups.length && (
              <div className="rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">
                No served chats were found in MongoDB. Add the bot to a group and run <code>/start</code>.
              </div>
            )}
            {!loading && groups.length > 0 && !visible.length && (
              <p className="p-3 text-sm text-white/50">No groups match this search and filter.</p>
            )}
            {visible.map((group) => {
              const state = protectionSummary(group.settings);
              const isActive = selected === group.id;
              return (
                <div key={group.id} className="flex items-start gap-2">
                  {selectMode && (
                    <input
                      type="checkbox"
                      aria-label={`Select ${displayTitle(group)}`}
                      checked={picked.includes(group.id)}
                      onChange={() => setPicked((current) => toggleSelected(current, group.id))}
                      className="mt-4 h-4 w-4 shrink-0 accent-[#30D158]"
                    />
                  )}
                  <button
                    disabled={saving !== null && !selectMode}
                    onClick={() => {
                      if (selectMode) setPicked((current) => toggleSelected(current, group.id));
                      else setSelected(group.id);
                    }}
                    className={`w-full flex-1 rounded-2xl border p-3 text-left transition ${
                      isActive && !selectMode
                        ? "border-white/25 bg-white/[0.08]"
                        : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/[0.07]">
                        <Shield size={18} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{displayTitle(group)}</span>
                        <span className="mt-1 block truncate text-xs text-[var(--ios-label-secondary)]">
                          {group.id} · {group.type} · {memberLabel(group.members)}
                        </span>
                        <span className="mt-1 flex flex-wrap gap-1">
                          <span className="ios-pill text-[10px]">{state.active} locks</span>
                          {(group.counts?.warns ?? 0) > 0 && (
                            <span className="ios-pill text-[10px]">{group.counts?.warns} warned</span>
                          )}
                          {(group.counts?.blacklist ?? 0) > 0 && (
                            <span className="ios-pill text-[10px]">{group.counts?.blacklist} blocked</span>
                          )}
                        </span>
                      </span>
                      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${group.available ? "bg-[#30D158]" : "bg-[#FF9F0A]"}`} />
                    </span>
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <section className="ios-card p-4 sm:p-5">
          {!active ? (
            <div className="rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">
              Select a served group to review its settings.
            </div>
          ) : (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate font-semibold">{displayTitle(active)}</h2>
                  <p className="ios-caption mt-1">
                    {active.id} · {active.type} · {memberLabel(detail?.chat?.member_count ?? active.members)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    onClick={() => {
                      selectGroup(active.id);
                      open("chat");
                    }}
                    className="ios-btn ios-btn-glass text-xs"
                  >
                    <MessageSquare size={14} /> Moderate messages
                  </button>
                  <a
                    href={`https://t.me/c/${String(active.id).replace(/^-100/, "")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="ios-btn ios-btn-glass text-xs"
                  >
                    <ExternalLink size={14} /> Telegram
                  </a>
                </div>
              </div>

              {!active.available && (
                <PanelNotice>
                  Telegram could not read this chat. Confirm the bot is still a member and can access chat info. Saved
                  settings are still shown exactly as stored.
                </PanelNotice>
              )}
              {detailState === "loading" && (
                <p className="ios-caption mt-3 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Reading group state…</p>
              )}
              {detailState === "unsupported" && <PanelNotice>{detailMessage}</PanelNotice>}
              {detailState === "error" && (
                <div className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs text-amber-100">
                  <span>{detailMessage}</span>
                  <button onClick={() => void loadDetail(active.id)} className="underline">Retry</button>
                </div>
              )}
              {detail && (detail.problems ?? []).length > 0 && <PanelNotice>{(detail.problems ?? []).join(" ")}</PanelNotice>}

              <div role="group" aria-label="Group settings panels" className="mt-4 flex flex-wrap gap-1.5">
                {TABS.map((item) => (
                  <button
                    key={item.id}
                    aria-pressed={tab === item.id}
                    aria-selected={tab === item.id}
                    onClick={() => setTab(item.id)}
                    className="ios-chip text-xs"
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {tab === "protection" && (
                <div className="mt-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="ios-caption">
                      {guardsOn} of {SETTING_KEYS.length} guards on
                    </p>
                    {detail && (
                      <div className="flex flex-wrap gap-1.5">
                        {PRESET_ORDER.map((id) => (
                          <button
                            key={id}
                            aria-label={`Apply ${PRESET_COPY[id].label} preset`}
                            disabled={saving !== null || !detail}
                            onClick={() => void runAction({ action: "preset", preset: id }, { success: `${PRESET_COPY[id].label} preset applied.` })}
                            className="ios-chip text-xs disabled:opacity-40"
                            title={PRESET_COPY[id].description}
                          >
                            {saving === "preset" ? <Loader2 size={12} className="animate-spin" /> : <ShieldCheck size={12} />}
                            {PRESET_COPY[id].label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  {!detail && (
                    <p className="mt-2 text-xs text-[var(--ios-label-tertiary)]">
                      Presets need the updated backend. Individual switches below save right away.
                    </p>
                  )}
                  {PROTECTION_GROUPS.map((group) => (
                    <div key={group.id} className="mt-4">
                      <div className="flex items-baseline justify-between">
                        <h3 className="text-sm font-semibold">{group.title}</h3>
                        <span className="ios-caption">{group.controls.filter((control) => flag(activeSettings, control.key)).length}/{group.controls.length}</span>
                      </div>
                      <p className="ios-caption">{group.description}</p>
                      <div className="mt-1 divide-y divide-white/[0.07]">
                        {group.controls.map((control) => (
                          <Toggle
                            key={control.key}
                            label={control.label}
                            description={control.description}
                            checked={flag(activeSettings, control.key)}
                            disabled={saving !== null}
                            onChange={(next) => void setLock(control.key, next)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                  <p className="mt-3 text-xs text-[var(--ios-label-tertiary)]">
                    The bot needs the Delete messages permission for locks, and Restrict members for captcha and
                    blacklist actions.
                  </p>
                </div>
              )}

              {tab === "community" && (
                <div className="mt-3 space-y-4">
                  {!community ? (
                    <PanelNotice>
                      Greetings, rules and warnings load once the updated bot backend answers. Redeploy Render, then
                      press Retry on the panel above.
                    </PanelNotice>
                  ) : (
                    <>
                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-sm font-semibold">Welcome message</h3>
                          <Toggle
                            label="Welcome message"
                            checked={flag(activeSettings, "welcome_enabled")}
                            disabled={saving !== null}
                            onChange={(next) => void runAction({ action: "welcome", text: welcomeDraft || "Welcome {name} to {title}!", enabled: next })}
                          />
                        </div>
                        <label className="sr-only" htmlFor="welcome-text">Welcome text</label>
                        <textarea
                          id="welcome-text"
                          aria-label="Welcome text"
                          value={welcomeDraft}
                          onChange={(event) => setWelcomeDraft(event.target.value)}
                          rows={3}
                          maxLength={1000}
                          placeholder="Welcome {name} to {title}!"
                          className="ios-textarea mt-2 text-sm"
                        />
                        <div className="mt-2 flex items-center justify-between">
                          <span className="ios-caption">{welcomeDraft.length}/1000 · {`{name} {id} {title} {mention}`}</span>
                          <button
                            disabled={saving !== null}
                            onClick={() => void runAction({ action: "welcome", text: welcomeDraft, enabled: flag(activeSettings, "welcome_enabled") }, { success: "Welcome message saved." })}
                            className="ios-btn ios-btn-primary text-xs"
                          >
                            {saving === "welcome" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save
                          </button>
                        </div>
                      </div>

                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-sm font-semibold">Goodbye message</h3>
                          <Toggle
                            label="Goodbye message"
                            checked={flag(activeSettings, "goodbye_enabled")}
                            disabled={saving !== null}
                            onChange={(next) => void runAction({ action: "goodbye", text: goodbyeDraft || "Goodbye {name}.", enabled: next })}
                          />
                        </div>
                        <label className="sr-only" htmlFor="goodbye-text">Goodbye text</label>
                        <textarea
                          id="goodbye-text"
                          aria-label="Goodbye text"
                          value={goodbyeDraft}
                          onChange={(event) => setGoodbyeDraft(event.target.value)}
                          rows={2}
                          maxLength={1000}
                          placeholder="Goodbye {name}."
                          className="ios-textarea mt-2 text-sm"
                        />
                        <div className="mt-2 flex justify-end">
                          <button
                            disabled={saving !== null}
                            onClick={() => void runAction({ action: "goodbye", text: goodbyeDraft, enabled: flag(activeSettings, "goodbye_enabled") }, { success: "Goodbye message saved." })}
                            className="ios-btn ios-btn-glass text-xs"
                          >
                            {saving === "goodbye" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save
                          </button>
                        </div>
                      </div>

                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="text-sm font-semibold">Published rules</h3>
                        <p className="ios-caption mt-1">Shown by <code>/rules</code> in the group.</p>
                        <label className="sr-only" htmlFor="rules-text">Group rules</label>
                        <textarea
                          id="rules-text"
                          aria-label="Group rules"
                          value={rulesDraft}
                          onChange={(event) => setRulesDraft(event.target.value)}
                          rows={4}
                          maxLength={2000}
                          placeholder="1. Be civil. 2. No spam."
                          className="ios-textarea mt-2 text-sm"
                        />
                        <div className="mt-2 flex justify-end gap-2">
                          <button
                            disabled={saving !== null || !rulesDraft}
                            onClick={() => void runAction({ action: "rules", text: "" }, { success: "Rules cleared." })}
                            className="ios-btn ios-btn-glass text-xs disabled:opacity-40"
                          >
                            Clear
                          </button>
                          <button
                            disabled={saving !== null}
                            onClick={() => void runAction({ action: "rules", text: rulesDraft }, { success: "Rules published." })}
                            className="ios-btn ios-btn-primary text-xs"
                          >
                            {saving === "rules" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Publish
                          </button>
                        </div>
                      </div>

                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="text-sm font-semibold">Captcha</h3>
                        <p className="ios-caption mt-1">
                          {flag(activeSettings, "captcha_enabled")
                            ? "New members must solve a challenge before posting."
                            : "New members can post immediately."}
                        </p>
                        <div className="mt-2 flex justify-end">
                          <button
                            disabled={saving !== null}
                            onClick={() => void runAction({ action: "protect", settings: { captcha_enabled: !flag(activeSettings, "captcha_enabled") } }, { success: "Join captcha updated." })}
                            className="ios-btn ios-btn-glass text-xs"
                          >
                            {flag(activeSettings, "captcha_enabled") ? "Disable captcha" : "Enable captcha"}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {tab === "moderation" && (
                <div className="mt-3 space-y-4">
                  {!community ? (
                    <PanelNotice>Warnings, blacklist words and saved notes load from the bot backend.</PanelNotice>
                  ) : (
                    <>
                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="text-sm font-semibold">Warning limit</h3>
                        <p className="ios-caption mt-1">Members are banned when they reach this many warnings.</p>
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            aria-label="Decrease warning limit"
                            onClick={() => setWarnLimitDraft((value) => Math.max(1, value - 1))}
                            className="ios-btn ios-btn-glass h-8 w-8 p-0"
                          >
                            <Minus size={14} />
                          </button>
                          <input
                            aria-label="Warning limit"
                            type="number"
                            min={1}
                            max={10}
                            value={warnLimitDraft}
                            onChange={(event) => setWarnLimitDraft(Math.max(1, Math.min(10, Number(event.target.value) || 1)))}
                            className="ios-input w-20 text-center text-sm"
                          />
                          <button
                            aria-label="Increase warning limit"
                            onClick={() => setWarnLimitDraft((value) => Math.min(10, value + 1))}
                            className="ios-btn ios-btn-glass h-8 w-8 p-0"
                          >
                            <Plus size={14} />
                          </button>
                          <button
                            disabled={saving !== null || warnLimitDraft === numberValue(activeSettings, "warn_threshold", 3)}
                            onClick={() => void runAction({ action: "warn_limit", limit: warnLimitDraft }, { success: `Warning limit set to ${warnLimitDraft}.` })}
                            className="ios-btn ios-btn-primary ml-auto text-xs disabled:opacity-40"
                          >
                            {saving === "warn_limit" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save
                          </button>
                        </div>
                      </div>

                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="text-sm font-semibold">Blacklist</h3>
                        <p className="ios-caption mt-1">
                          Exact words or phrases. The action below decides what happens when one appears.
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <label className="sr-only" htmlFor="blacklist-mode">Blacklist action</label>
                          <select
                            id="blacklist-mode"
                            aria-label="Blacklist action"
                            value={textValue(activeSettings, "blacklist_mode") || "del"}
                            disabled={saving !== null}
                            onChange={(event) => void runAction({ action: "blacklist_mode", mode: event.target.value }, { success: "Blacklist action updated." })}
                            className="ios-input text-sm"
                          >
                            {BLACKLIST_MODES.map((mode) => (
                              <option key={mode.id} value={mode.id}>{mode.label} — {mode.description}</option>
                            ))}
                          </select>
                        </div>
                        <form
                          className="mt-2 flex gap-2"
                          onSubmit={async (event) => {
                            event.preventDefault();
                            const word = blacklistWord.trim();
                            if (!word) return;
                            const saved = await runAction(
                              { action: "blacklist_add", trigger: word },
                              { refreshDetail: true, success: `“${word}” blocked.` },
                            );
                            if (saved) setBlacklistWord("");
                          }}
                        >
                          <label className="sr-only" htmlFor="blacklist-word">Blacklist word</label>
                          <input
                            id="blacklist-word"
                            aria-label="Blacklist word"
                            value={blacklistWord}
                            onChange={(event) => setBlacklistWord(event.target.value)}
                            maxLength={64}
                            placeholder="Word or phrase"
                            className="ios-input flex-1 text-sm"
                          />
                          <button type="submit" disabled={saving !== null || !blacklistWord.trim()} className="ios-btn ios-btn-primary text-xs disabled:opacity-40">
                            <Plus size={14} /> Add
                          </button>
                        </form>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {community.blacklist.length === 0 && <p className="ios-caption">No blacklisted words yet.</p>}
                          {community.blacklist.map((item) => (
                            <button
                              key={item.trigger}
                              aria-label={`Remove ${item.trigger}`}
                              disabled={saving !== null}
                              onClick={() => void runAction({ action: "blacklist_remove", trigger: item.trigger }, { refreshDetail: true, success: `“${item.trigger}” removed.` })}
                              className="ios-chip text-xs"
                            >
                              {item.trigger} <Trash2 size={11} />
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-xl bg-white/[0.03] p-3">
                          <h3 className="text-sm font-semibold">Saved notes <span className="ios-pill ml-1 text-[10px]">{community.notes.length}</span></h3>
                          <p className="ios-caption mt-1">Recalled with <code>#name</code> or <code>/get name</code>.</p>
                          <ul className="mt-2 space-y-1">
                            {community.notes.length === 0 && <li className="ios-caption">No notes saved.</li>}
                            {community.notes.map((note) => (
                              <li key={note.name} className="flex items-center justify-between gap-2 text-xs">
                                <span className="truncate"><code>#{note.name}</code> · {note.type}</span>
                                <button
                                  aria-label={`Delete note ${note.name}`}
                                  disabled={saving !== null}
                                  onClick={() => void runAction({ action: "note_delete", name: note.name }, { refreshDetail: true, success: `Note ${note.name} deleted.` })}
                                  className="text-white/40 hover:text-red-300"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="rounded-xl bg-white/[0.03] p-3">
                          <h3 className="text-sm font-semibold">Auto-answers <span className="ios-pill ml-1 text-[10px]">{community.filters.length}</span></h3>
                          <p className="ios-caption mt-1">Added with <code>/filter word reply</code>.</p>
                          <ul className="mt-2 space-y-1">
                            {community.filters.length === 0 && <li className="ios-caption">No filters saved.</li>}
                            {community.filters.map((item) => (
                              <li key={item.keyword} className="flex items-center justify-between gap-2 text-xs">
                                <span className="truncate" title={item.reply}><code>{item.keyword}</code> → {item.reply}</span>
                                <button
                                  aria-label={`Delete filter ${item.keyword}`}
                                  disabled={saving !== null}
                                  onClick={() => void runAction({ action: "filter_delete", keyword: item.keyword }, { refreshDetail: true, success: `Filter ${item.keyword} deleted.` })}
                                  className="text-white/40 hover:text-red-300"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {tab === "members" && (
                <div className="mt-3 space-y-3">
                  {!community ? (
                    <PanelNotice>Warnings and approvals are read from MongoDB once the updated backend answers.</PanelNotice>
                  ) : (
                    <>
                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="flex items-center gap-2 text-sm font-semibold">
                          <UserX size={15} /> Warnings
                          <span className="ios-pill text-[10px]">{community.warns.length}</span>
                        </h3>
                        <p className="ios-caption mt-1">Limit {community.warn_limit}. Clearing a record can unban a member who hit the limit.</p>
                        {community.warns.length === 0 && <p className="ios-caption mt-2">No member has warnings in this group.</p>}
                        <ul className="mt-2 divide-y divide-white/[0.06]">
                          {community.warns.map((warn) => (
                            <li key={warn.user_id} className="flex items-start justify-between gap-2 py-2 text-xs">
                              <div className="min-w-0">
                                <div className="font-medium">
                                  <code>{warn.user_id}</code> · {warn.count}/{community.warn_limit}
                                </div>
                                <div className="mt-0.5 truncate text-[var(--ios-label-secondary)]" title={warn.reasons.join(" · ")}>
                                  {warn.reasons.length ? warn.reasons.slice(-2).join(" · ") : "No reasons stored"}
                                </div>
                              </div>
                              <button
                                aria-label={`Clear warnings for ${warn.user_id}`}
                                disabled={saving !== null}
                                onClick={() => void runAction({ action: "warn_reset", user_id: warn.user_id }, { refreshDetail: true, success: `Warnings cleared for ${warn.user_id}.` })}
                                className="ios-btn ios-btn-glass shrink-0 text-[11px]"
                              >
                                Clear
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="rounded-xl bg-white/[0.03] p-3">
                        <h3 className="flex items-center gap-2 text-sm font-semibold">
                          <ShieldCheck size={15} /> Approved members
                          <span className="ios-pill text-[10px]">{community.approved.length}</span>
                        </h3>
                        <p className="ios-caption mt-1">Approved members bypass locks, anti-spam, captcha and blacklist actions.</p>
                        {community.approved.length === 0 && <p className="ios-caption mt-2">Nobody is approved in this group yet.</p>}
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {community.approved.map((userId) => (
                            <button
                              key={userId}
                              aria-label={`Remove approval for ${userId}`}
                              disabled={saving !== null}
                              onClick={() => void runAction({ action: "approved_remove", user_id: userId }, { refreshDetail: true, success: `Approval removed for ${userId}.` })}
                              className="ios-chip text-xs"
                            >
                              {userId} <Trash2 size={11} />
                            </button>
                          ))}
                        </div>
                      </div>

                      {community.disabled_commands.length > 0 && (
                        <div className="rounded-xl bg-white/[0.03] p-3">
                          <h3 className="text-sm font-semibold">Disabled commands</h3>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {community.disabled_commands.map((command) => (
                              <span key={command} className="ios-pill text-[10px]">/{command}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>

      <p className="mt-4 flex items-center gap-2 ios-caption">
        <Users size={14} /> Counts come from MongoDB and Telegram — no sample groups or invented activity values are
        rendered. Admins and approved members bypass every lock.
      </p>
      <p className="mt-1 flex items-center gap-2 ios-caption">
        <Lock size={13} /> Changes are written by the bot process, so they survive restarts and apply to the live group.
      </p>
    </main>
  );
}
