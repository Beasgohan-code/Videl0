"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  HeartPulse,
  Loader2,
  Moon,
  RefreshCw,
  Search,
  ShieldCheck,
  Timer,
} from "lucide-react";
import {
  ESCALATION_CHOICES,
  displayTitle,
  errorHint,
  escalationSummary,
  hhmmToMinutes,
  memberLabel,
  quietNow,
  quietSummary,
  zoneLabel,
  type Automation,
  type EscalationAction,
  type Group,
} from "@/lib/group-admin";

const DEFAULT_AUTOMATION: Automation = {
  quiet_hours: { enabled: false, start: "22:00", end: "07:00", tz_offset: 0 },
  escalation: { enabled: true, action: "ban", mute_hours: 6 },
};

/** Offsets offered in the picker; the device zone is added when it differs. */
const ZONES = [-720, -600, -480, -420, -360, -300, -240, -180, -120, -60, 0, 60, 120, 180, 210, 240, 270, 300, 330, 345, 360, 390, 420, 480, 525, 540, 570, 600, 660, 720, 780, 840];

function automationOf(group: Group | null): Automation {
  if (!group?.automation) return DEFAULT_AUTOMATION;
  const quiet = group.automation.quiet_hours ?? DEFAULT_AUTOMATION.quiet_hours;
  const escalation = group.automation.escalation ?? DEFAULT_AUTOMATION.escalation;
  return { quiet_hours: { ...DEFAULT_AUTOMATION.quiet_hours, ...quiet }, escalation: { ...DEFAULT_AUTOMATION.escalation, ...escalation } };
}

export default function AutomationScreen() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<Automation>(DEFAULT_AUTOMATION);
  const [deviceOffset] = useState(() => -new Date().getTimezoneOffset());

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/groups", { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(errorHint(String(data.error || "Groups could not be loaded"), response.status));
      const chats: Group[] = Array.isArray(data.chats) ? data.chats : [];
      setGroups(chats);
      setSelected((current) => (chats.some((group) => group.id === current) ? current : (chats[0]?.id ?? null)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Groups could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = useMemo(() => groups.find((group) => group.id === selected) ?? null, [groups, selected]);

  useEffect(() => {
    setDraft(automationOf(active));
  }, [active]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return groups;
    return groups.filter((group) =>
      `${group.title} ${group.id} ${group.username ?? ""}`.toLowerCase().includes(needle),
    );
  }, [groups, query]);

  const totals = useMemo(
    () => ({
      quiet: groups.filter((group) => automationOf(group).quiet_hours.enabled).length,
      escalating: groups.filter((group) => {
        const escalation = automationOf(group).escalation;
        return escalation.enabled && escalation.action !== "none";
      }).length,
      attention: groups.filter((group) => group.health?.attention).length,
    }),
    [groups],
  );

  const zoneOptions = useMemo(() => {
    const values = ZONES.includes(deviceOffset) ? ZONES : [...ZONES, deviceOffset];
    return [...new Set(values)].sort((a, b) => a - b);
  }, [deviceOffset]);

  function patch(next: { quiet?: Partial<Automation["quiet_hours"]>; escalation?: Partial<Automation["escalation"]> }) {
    setDraft((current) => ({
      quiet_hours: { ...current.quiet_hours, ...(next.quiet ?? {}) },
      escalation: { ...current.escalation, ...(next.escalation ?? {}) },
    }));
  }

  const startMinutes = hhmmToMinutes(draft.quiet_hours.start);
  const endMinutes = hhmmToMinutes(draft.quiet_hours.end);
  const windowProblem =
    draft.quiet_hours.enabled && (startMinutes === null || endMinutes === null)
      ? "Use a valid 24-hour time for both ends of the window."
      : draft.quiet_hours.enabled && startMinutes === endMinutes
        ? "The window cannot start and end at the same minute."
        : "";

  async function save(block: "quiet" | "escalation") {
    if (!active || saving) return;
    if (block === "quiet" && windowProblem) {
      setError(windowProblem);
      return;
    }
    setSaving(block);
    setError("");
    setNotice("");
    try {
      const body =
        block === "quiet"
          ? { action: "automation", quiet_hours: draft.quiet_hours }
          : { action: "automation", escalation: draft.escalation };
      const response = await fetch(`/api/groups/${active.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(
          response.status === 501
            ? "Automation needs the updated bot backend. Redeploy the Render service, then retry."
            : errorHint(String(data.error || "Automation was not saved"), response.status),
        );
      }
      const automation = (data.automation ?? draft) as Automation;
      setGroups((all) => all.map((group) => (group.id === active.id ? { ...group, automation } : group)));
      setDraft(automationOf({ ...active, automation }));
      setNotice(block === "quiet" ? "Quiet hours saved." : "Warning ladder saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Automation was not saved");
    } finally {
      setSaving(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl py-5 sm:py-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ios-caps text-[11px]">Videl · Community</p>
          <h1 className="mt-2 ios-title">Automation</h1>
          <p className="mt-1 ios-subheadline">
            Quiet hours and the warning ladder the bot enforces — saved in MongoDB, applied by the running bot.
          </p>
        </div>
        <button onClick={() => void load()} disabled={loading || saving !== null} className="ios-btn ios-btn-glass text-sm">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </header>

      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {[
          { label: "Quiet hours on", value: totals.quiet, icon: Moon },
          { label: "Warning ladder on", value: totals.escalating, icon: ShieldCheck },
          { label: "Needs attention", value: totals.attention, icon: HeartPulse },
        ].map((stat) => (
          <div key={stat.label} className="ios-card p-3">
            <div className="flex items-center justify-between">
              <div className="text-2xl font-semibold tabular-nums">{stat.value}</div>
              <stat.icon size={18} className="text-[var(--ios-label-tertiary)]" />
            </div>
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

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <section className="ios-card p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Groups</h2>
            <span className="ios-pill">{visible.length} shown</span>
          </div>
          <label className="sr-only" htmlFor="automation-search">Search groups</label>
          <div className="relative mt-4">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ios-label-tertiary)]" />
            <input
              id="automation-search"
              aria-label="Search groups"
              placeholder="Search group name, @username or ID…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="ios-input pl-9"
            />
          </div>
          <div className="mt-3 space-y-2">
            {loading && <p className="ios-caption p-3">Loading served chats…</p>}
            {!loading && !groups.length && (
              <div className="rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">
                No served chats were found. Add the bot to a group and run <code>/start</code>.
              </div>
            )}
            {visible.map((group) => {
              const automation = automationOf(group);
              const isActive = selected === group.id;
              return (
                <button
                  key={group.id}
                  onClick={() => setSelected(group.id)}
                  disabled={saving !== null}
                  className={`w-full rounded-2xl border p-3 text-left transition ${
                    isActive ? "border-white/25 bg-white/[0.08]" : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"
                  }`}
                >
                  <span className="block truncate font-medium">{displayTitle(group)}</span>
                  <span className="mt-0.5 block truncate text-xs text-[var(--ios-label-secondary)]">
                    {memberLabel(group.members)} · {quietSummary(automation.quiet_hours)}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-1">
                    <span className="ios-pill text-[10px]">
                      {quietNow(automation.quiet_hours) ? "quiet now" : automation.quiet_hours.enabled ? "scheduled" : "quiet off"}
                    </span>
                    <span className="ios-pill text-[10px]">{escalationSummary(automation.escalation)}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="ios-card p-4 sm:p-5">
          {!active ? (
            <div className="rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">
              Select a group to configure its automation.
            </div>
          ) : (
            <>
              <h2 className="truncate font-semibold">{displayTitle(active)}</h2>
              {!active.automation && (
                <div className="mt-2 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs text-amber-100">
                  This backend does not report automation settings yet. Defaults are shown for reference; saving needs
                  the updated Render deploy.
                </div>
              )}
              <p className="ios-caption mt-1">
                {active.id} · {memberLabel(active.members)} · {quietNow(draft.quiet_hours) ? "inside the quiet window now" : "outside the quiet window"}
              </p>

              <div className="mt-4 rounded-xl bg-white/[0.03] p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="flex items-center gap-2 text-sm font-semibold"><Moon size={15} /> Quiet hours</h3>
                    <p className="ios-caption mt-1">
                      Member messages are deleted inside the window. Admins and approved members are exempt, and the bot
                      never touches its own messages.
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={draft.quiet_hours.enabled}
                    aria-label={`${draft.quiet_hours.enabled ? "Disable" : "Enable"} quiet hours`}
                    disabled={saving !== null}
                    onClick={() => patch({ quiet: { enabled: !draft.quiet_hours.enabled } })}
                    className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-40 ${
                      draft.quiet_hours.enabled ? "bg-[#30D158]" : "bg-white/15"
                    }`}
                  >
                    <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${draft.quiet_hours.enabled ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  <label className="text-xs">
                    Starts
                    <input
                      type="time"
                      aria-label="Quiet hours start"
                      value={draft.quiet_hours.start}
                      disabled={saving !== null}
                      onChange={(event) => patch({ quiet: { start: event.target.value } })}
                      className="ios-input mt-1 text-sm"
                    />
                  </label>
                  <label className="text-xs">
                    Ends
                    <input
                      type="time"
                      aria-label="Quiet hours end"
                      value={draft.quiet_hours.end}
                      disabled={saving !== null}
                      onChange={(event) => patch({ quiet: { end: event.target.value } })}
                      className="ios-input mt-1 text-sm"
                    />
                  </label>
                </div>
                <label className="mt-2 block text-xs">
                  Timezone
                  <select
                    aria-label="Quiet hours timezone"
                    value={draft.quiet_hours.tz_offset}
                    disabled={saving !== null}
                    onChange={(event) => patch({ quiet: { tz_offset: Number(event.target.value) } })}
                    className="ios-input mt-1 text-sm"
                  >
                    {zoneOptions.map((offset) => (
                      <option key={offset} value={offset}>
                        {zoneLabel(offset)}
                        {offset === deviceOffset ? " · your device" : ""}
                        {offset === 330 ? " · India" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="ios-caption mt-2">{quietSummary(draft.quiet_hours)}</p>
                {windowProblem && <p className="mt-1 text-xs text-amber-200">{windowProblem}</p>}
                <div className="mt-2 flex justify-end">
                  <button
                    onClick={() => void save("quiet")}
                    disabled={saving !== null || Boolean(windowProblem)}
                    className="ios-btn ios-btn-primary text-xs disabled:opacity-40"
                  >
                    {saving === "quiet" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save quiet hours
                  </button>
                </div>
              </div>

              <div className="mt-3 rounded-xl bg-white/[0.03] p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="flex items-center gap-2 text-sm font-semibold"><Timer size={15} /> Warning ladder</h3>
                    <p className="ios-caption mt-1">
                      What happens when a member reaches the warning limit ({active.warn_limit ?? 3}). Warnings themselves
                      are unchanged.
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={draft.escalation.enabled}
                    aria-label={`${draft.escalation.enabled ? "Disable" : "Enable"} the warning ladder`}
                    disabled={saving !== null}
                    onClick={() => patch({ escalation: { enabled: !draft.escalation.enabled } })}
                    className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-40 ${
                      draft.escalation.enabled ? "bg-[#30D158]" : "bg-white/15"
                    }`}
                  >
                    <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${draft.escalation.enabled ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
                <div role="radiogroup" aria-label="Escalation action" className="mt-3 space-y-1.5">
                  {ESCALATION_CHOICES.map((choice) => (
                    <button
                      key={choice.id}
                      role="radio"
                      aria-checked={draft.escalation.action === choice.id}
                      onClick={() => patch({ escalation: { action: choice.id as EscalationAction } })}
                      disabled={saving !== null || !draft.escalation.enabled}
                      className={`w-full rounded-xl border p-2.5 text-left text-xs transition disabled:opacity-40 ${
                        draft.escalation.action === choice.id
                          ? "border-white/25 bg-white/[0.09]"
                          : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05]"
                      }`}
                    >
                      <span className="block font-medium">{choice.label}</span>
                      <span className="block text-[var(--ios-label-secondary)]">{choice.description}</span>
                    </button>
                  ))}
                </div>
                {draft.escalation.action === "mute" && (
                  <label className="mt-2 block text-xs">
                    Mute length (hours)
                    <input
                      type="number"
                      min={1}
                      max={168}
                      aria-label="Mute hours"
                      value={draft.escalation.mute_hours}
                      disabled={saving !== null}
                      onChange={(event) =>
                        patch({ escalation: { mute_hours: Math.max(1, Math.min(168, Number(event.target.value) || 1)) } })
                      }
                      className="ios-input mt-1 text-sm"
                    />
                  </label>
                )}
                <p className="ios-caption mt-2">{escalationSummary(draft.escalation)}</p>
                <div className="mt-2 flex justify-end">
                  <button
                    onClick={() => void save("escalation")}
                    disabled={saving !== null}
                    className="ios-btn ios-btn-primary text-xs disabled:opacity-40"
                  >
                    {saving === "escalation" ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save ladder
                  </button>
                </div>
              </div>

              {active.health && active.health.issues.length > 0 && (
                <div className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs text-amber-100">
                  <h3 className="font-semibold">Needs attention · {active.health.score}/100</h3>
                  <ul className="mt-1 space-y-1">
                    {active.health.issues.map((issue) => (
                      <li key={issue.code}>· {issue.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="mt-3 text-xs text-[var(--ios-label-tertiary)]">
                Changes are written by the bot process and survive restarts. Quiet hours are evaluated against the
                stored offset, so they do not drift with the server clock.
              </p>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
