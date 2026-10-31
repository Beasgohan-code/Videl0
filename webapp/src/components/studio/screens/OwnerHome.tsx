"use client";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Users,
  FileText,
  Clock3,
  Shield,
  Send,
  Zap,
  Settings2,
  MessageCircle,
  Crown,
  Activity,
  Music2,
} from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio, Section } from "@/components/studio/StudioProvider";
import { Callout, EmptyState, PageHeader, Skeleton } from "../ui";
import { useScreenMotion } from "../useScreenMotion";
type Metrics = {
  users?: number;
  chats?: number;
  plays?: number;
  uptime?: number;
};
type Analytics = {
  total_commands?: number;
  active_users?: number;
  series?: { time: string; commands: number }[];
  recent_events?: { command: string; chat_id: string; at: string | null }[];
  top_chats?: { id: string; commands: number }[];
};
type PulseGroup = {
  id: number | string;
  title: string;
  available?: boolean;
  bot_admin?: boolean;
  counts?: { reports?: number; pending_joins?: number };
  health?: { attention?: boolean; issues?: string[] };
};
type GroupsPulse = {
  chats?: PulseGroup[];
  total?: number;
  summary?: { attention?: number; unreachable?: number };
};
type OnboardingPulse = {
  totals?: { joins?: number; challenged?: number; verified?: number; timed_out?: number };
  groups_with_joins?: number;
};
const actions: {
  tab: Section;
  label: string;
  icon: typeof Send;
  color: string;
}[] = [
  {
    tab: "music",
    label: "Open Videl Music",
    icon: Music2,
    color: "from-emerald-400 to-teal-600",
  },
  {
    tab: "post",
    label: "Create Post",
    icon: FileText,
    color: "from-fuchsia-500 to-violet-600",
  },
  {
    tab: "groups",
    label: "Manage Groups",
    icon: Users,
    color: "from-indigo-500 to-blue-600",
  },
  {
    tab: "chat",
    label: "Bot inbox",
    icon: MessageCircle,
    color: "from-blue-500 to-indigo-600",
  },
  {
    tab: "broadcast",
    label: "Broadcast",
    icon: Send,
    color: "from-cyan-500 to-blue-600",
  },
  {
    tab: "automation",
    label: "Automation",
    icon: Zap,
    color: "from-violet-500 to-purple-700",
  },
  {
    tab: "settings",
    label: "Bot Settings",
    icon: Settings2,
    color: "from-blue-500 to-violet-600",
  },
];
export default function Home() {
  const rootRef = useRef<HTMLElement>(null);
  useScreenMotion(rootRef, "owner-home");
  const telegram = useTelegram();
  const { open, tab } = useStudio();
  const [refreshTick, refresh] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [measured, setMeasured] = useState<string | null>(null);
  const [stats, setStats] = useState<Metrics | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [groupsPulse, setGroupsPulse] = useState<GroupsPulse | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingPulse | null>(null);
  const [health, setHealth] = useState<{
    status?: string;
    bot_status?: string;
    uptime?: number;
    degraded?: boolean;
    degraded_reasons?: string[];
    bot_error?: string | null;
  } | null>(null);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (tab !== "home") return;
    let active = true,
      inFlight = false;
    const controller = new AbortController();
    async function read(path: string) {
      const response = await fetch(path, {
        cache: "no-store",
        signal: AbortSignal.any([
          controller.signal,
          AbortSignal.timeout(15000),
        ]),
      });
      const data = await response.json();
      if (!response.ok || data.ok === false)
        throw new Error(data.error || "Live service unavailable");
      return data;
    }
    async function load() {
      if (inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      setRefreshing(true);
      await Promise.allSettled([
        read("/api/summary")
          .then((data) => {
            if (active) {
              setStats(data.stats);
              setMeasured(data.measured_at || null);
              setError("");
            }
          })
          .catch((error) => {
            if (active)
              setError(
                error instanceof Error
                  ? error.message
                  : "Live totals unavailable",
              );
          }),
        (telegram.authenticated
          ? read("/api/analytics")
          : Promise.resolve(null)
        )
          .then((data) => {
            if (active) setAnalytics(data);
          })
          .catch(() => {
            if (active) setAnalytics(null);
          }),
        (telegram.authenticated
          ? read("/api/groups?limit=100")
          : Promise.resolve(null)
        )
          .then((data) => {
            if (active) setGroupsPulse(data);
          })
          .catch(() => {
            if (active) setGroupsPulse(null);
          }),
        (telegram.authenticated ? read("/api/onboarding") : Promise.resolve(null))
          .then((data) => { if (active) setOnboarding(data); })
          .catch(() => { if (active) setOnboarding(null); }),
        read("/api/health")
          .then((data) => {
            if (active) setHealth(data);
          })
          .catch(() => {
            if (active) setHealth(null);
          }),
      ]);
      if (active) {
        setLoaded(true);
        setRefreshing(false);
      }
      inFlight = false;
    }
    void load();
    const timer = setInterval(() => void load(), 30000);
    const visible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [telegram.authenticated, refreshTick, tab]);
  const count = (n?: number) =>
    typeof n === "number" ? n.toLocaleString() : "—";
  const online = health?.status === "ok" && health.bot_status === "online";
  // "Reachable" is not "working": name the part that is down, during the outage
  // itself rather than only in Settings.
  const degraded = health?.status === "ok" && !online;
  const degradedReason = [
    ...(health?.degraded_reasons ?? []),
    ...(health?.bot_error ? [`Last start error: ${health.bot_error}`] : []),
  ].join(" · ");
  const uptimeSeconds = stats?.uptime ?? health?.uptime;
  const uptime =
    typeof uptimeSeconds === "number"
      ? `${Math.floor(uptimeSeconds / 3600)}h ${Math.floor((uptimeSeconds % 3600) / 60)}m`
      : "—";
  const name = telegram.user?.first_name || "Creator";
  const pulseGroupsList = groupsPulse?.chats ?? [];
  const attentionGroups = pulseGroupsList.filter(
    (group) => group.health?.attention || group.available === false || group.bot_admin === false,
  );
  const openReports = pulseGroupsList.reduce((sum, group) => sum + (group.counts?.reports ?? 0), 0);
  const pendingJoins = pulseGroupsList.reduce((sum, group) => sum + (group.counts?.pending_joins ?? 0), 0);
  const onboardingTotals = onboarding?.totals;
  const verificationRate = (onboardingTotals?.challenged ?? 0) > 0
    ? Math.round(((onboardingTotals?.verified ?? 0) / (onboardingTotals?.challenged ?? 1)) * 100)
    : null;
  const peakHour = analytics?.series?.reduce<{ time: string; commands: number } | null>(
    (peak, point) => (!peak || point.commands > peak.commands ? point : peak),
    null,
  );
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";
  return (
    <main ref={rootRef} className="ios-page ios-page-wide owner-home-page">
      <PageHeader
        eyebrow="Your community, connected"
        title={`${greeting}, ${name}! 👑`}
        subtitle="Here’s what’s happening with your bot and groups today."
        actions={
          <span
            title={degradedReason || undefined}
            role="status"
            className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs ${online ? "border-emerald-400/20 bg-emerald-400/5 text-emerald-300" : degraded ? "border-amber-300/20 bg-amber-300/5 text-amber-200" : "border-indigo-300/15 bg-indigo-300/5 text-indigo-200/60"}`}
          >
            <span
              aria-hidden
              className={`h-1.5 w-1.5 rounded-full ${online ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : degraded ? "bg-amber-300" : "bg-indigo-300/50"}`}
            />
            {online
              ? "Bot online"
              : degraded
                ? "Bot offline · panel up"
                : loaded
                  ? "Connection not confirmed"
                  : "Connecting…"}
          </span>
        }
      />
      <section data-screen-intro className="studio-hero relative mt-6 overflow-hidden rounded-3xl border border-indigo-400/25 p-6 sm:p-8">
        <img
          src="/studio-night.png"
          alt="Anime creator overlooking a neon violet city at night"
          className="absolute inset-0 h-full w-full object-cover object-[65%_40%]"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0a102a] via-[#0a102a]/90 to-[#0a102a]/5" />
        <div className="relative z-10 max-w-xl">
          <span className="ios-caps inline-flex items-center gap-2 rounded-full border border-indigo-300/20 bg-indigo-500/15 px-3 py-1 text-[11px] font-semibold text-indigo-200">
            <Crown size={12} /> Videl Studio
          </span>
          <h2 className="mt-5 text-3xl font-bold leading-tight tracking-tight sm:text-[42px]">
            Your Bot. Your Groups.
            <br />
            <span className="bg-gradient-to-r from-blue-300 via-indigo-300 to-fuchsia-300 bg-clip-text text-transparent">
              Your Community.
            </span>
          </h2>
          <p className="mt-4 max-w-sm text-sm leading-6 text-indigo-100/60">
            Manage, chat, post, automate — all in one powerful Telegram
            workspace.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button onClick={() => open("post")} className="ios-btn ios-btn-primary text-sm">
              Create something <ArrowUpRight size={16} />
            </button>
            <button onClick={() => open("guide")} className="ios-btn ios-btn-glass text-sm">
              Browse commands
            </button>
          </div>
        </div>
        <span className="absolute bottom-6 right-6 hidden text-right text-xs italic leading-5 text-white/70 md:block">
          Built for creators.
          <br />
          Made for your community.
        </span>
      </section>
      <section
        aria-label="Community metrics"
        className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4"
      >
        {[
          {
            label: "Groups",
            value: count(stats?.chats),
            icon: Users,
            color: "text-fuchsia-300 bg-fuchsia-400/10",
          },
          {
            label: "Users",
            value: count(stats?.users),
            icon: Users,
            color: "text-blue-300 bg-blue-400/10",
          },
          {
            label: "Music Plays",
            value: count(stats?.plays),
            icon: Activity,
            color: "text-cyan-300 bg-cyan-400/10",
          },
          {
            label: "Uptime",
            value: uptime,
            icon: Clock3,
            color: "text-emerald-300 bg-emerald-400/10",
          },
        ].map((m) => (
          <div
            key={m.label}
            className="ios-card flex items-center gap-4 p-4 sm:p-5"
            data-screen-stagger
          >
            <span
              aria-hidden
              className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${m.color}`}
            >
              <m.icon size={21} />
            </span>
            <div className="min-w-0">
              {loaded ? (
                <p className="ios-metric text-xl font-bold sm:text-2xl">{m.value}</p>
              ) : (
                <Skeleton className="h-6 w-14 sm:h-7" />
              )}
              <p className="mt-1 ios-caption truncate">{m.label}</p>
            </div>
          </div>
        ))}
      </section>
      {measured && (
        <p className="mt-3 text-[10px] text-indigo-100/40">
          {error
            ? "Last successful database snapshot"
            : "Live bot database totals"}{" "}
          · refreshed {new Date(measured).toLocaleTimeString()} · updates every
          30 seconds{" "}
          <button
            disabled={refreshing}
            onClick={() => refresh((n) => n + 1)}
            className="ml-2 underline underline-offset-2 disabled:opacity-40"
          >
            {refreshing ? "Refreshing…" : "Refresh now"}
          </button>
        </p>
      )}
      {error && (
        <Callout
          tone="warn"
          className="mt-4 items-center justify-between"
          title={error}
          live
        >
          <div className="flex flex-wrap items-center gap-3">
            <span>
              {stats
                ? "Showing the last successful snapshot, not current totals."
                : "Live totals are not available right now."}
            </span>
            <button
              disabled={refreshing}
              className="underline underline-offset-4 disabled:opacity-40"
              onClick={() => refresh((n) => n + 1)}
            >
              {refreshing ? "Reconnecting…" : "Retry connection"}
            </button>
          </div>
        </Callout>
      )}
      <section data-screen-stagger className="ios-card mt-5 overflow-hidden p-5" aria-label="Community Pulse">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="ios-caps text-[10px] text-indigo-300">Community Pulse · last 24 hours</p>
            <h2 className="mt-1 text-base font-semibold">What needs your attention?</h2>
          </div>
          <button onClick={() => open("groups")} className="ios-btn ios-btn-glass text-xs">
            Review groups <ArrowUpRight size={14} />
          </button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-indigo-300/10 bg-indigo-400/[0.035] p-3">
            <p className="text-[10px] text-indigo-100/45">Commands used</p>
            <p className="mt-1 text-xl font-bold">{count(analytics?.total_commands)}</p>
            <p className="mt-1 text-[10px] text-indigo-100/35">{count(analytics?.active_users)} active users</p>
          </div>
          <div className="rounded-xl border border-indigo-300/10 bg-indigo-400/[0.035] p-3">
            <p className="text-[10px] text-indigo-100/45">Busiest hour</p>
            <p className="mt-1 text-xl font-bold">{peakHour?.time ?? "—"}</p>
            <p className="mt-1 text-[10px] text-indigo-100/35">{peakHour ? `${count(peakHour.commands)} commands` : "Hourly activity"}</p>
          </div>
          <div className="rounded-xl border border-amber-300/10 bg-amber-300/[0.035] p-3">
            <p className="text-[10px] text-indigo-100/45">Groups to review</p>
            <p className="mt-1 text-xl font-bold">{count(groupsPulse?.summary?.attention ?? attentionGroups.length)}</p>
            <p className="mt-1 text-[10px] text-indigo-100/35">Bot access or protection needs checking</p>
          </div>
          <div className="rounded-xl border border-indigo-300/10 bg-indigo-400/[0.035] p-3">
            <p className="text-[10px] text-indigo-100/45">Open community queue</p>
            <p className="mt-1 text-xl font-bold">{count(openReports + pendingJoins)}</p>
            <p className="mt-1 text-[10px] text-indigo-100/35">{count(openReports)} reports · {count(pendingJoins)} join requests</p>
          </div>
        </div>
        {attentionGroups.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-indigo-300/10 pt-3">
            <span className="text-[10px] text-indigo-100/45">Review first:</span>
            {attentionGroups.slice(0, 3).map((group) => (
              <button key={group.id} onClick={() => open("groups")} className="max-w-full truncate rounded-full border border-amber-300/15 bg-amber-300/5 px-3 py-1 text-[10px] text-amber-100/80">
                {group.title}
              </button>
            ))}
            {attentionGroups.length > 3 && <span className="text-[10px] text-indigo-100/45">+{attentionGroups.length - 3} more</span>}
          </div>
        )}
        {groupsPulse?.total !== undefined && groupsPulse.total > pulseGroupsList.length && (
          <p className="mt-3 text-[10px] text-indigo-100/35">Queue and group checks summarize {pulseGroupsList.length} of {groupsPulse.total} groups.</p>
        )}
      </section>
      <section data-screen-stagger className="ios-card mt-5 p-5" aria-label="New-member onboarding insights">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="ios-caps text-[10px] text-cyan-200">New-member onboarding · 7 days</p>
            <h2 className="mt-1 text-base font-semibold">Are new members getting through?</h2>
          </div>
          <span className="rounded-full border border-cyan-300/10 bg-cyan-300/5 px-3 py-1.5 text-[10px] text-cyan-100/60">Aggregate counts only · no member IDs stored</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-5">
          {[
            ["Joined", count(onboardingTotals?.joins)],
            ["Challenges issued", count(onboardingTotals?.challenged)],
            ["Verified", count(onboardingTotals?.verified)],
            ["Timed out", count(onboardingTotals?.timed_out)],
            ["Challenge completion", verificationRate === null ? "—" : `${verificationRate}%`],
          ].map(([label, value]) => <div key={label} className="rounded-xl border border-cyan-300/10 bg-cyan-300/[0.025] p-3"><p className="text-[10px] text-indigo-100/45">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>)}
        </div>
        <p className="mt-3 text-[10px] text-indigo-100/35">{count(onboarding?.groups_with_joins)} groups had new joins. Completion is verified ÷ challenges issued; members who joined while verification was off are not included in that rate.</p>
      </section>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <section className="ios-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Recent Activity</h2>
            <button
              onClick={() => open("analytics")}
              className="text-[11px] text-indigo-300"
            >
              View all ↗
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {analytics?.recent_events?.length ? (
              analytics.recent_events.slice(0, 5).map((event, i) => (
                <div
                  key={`${event.at}-${i}`}
                  className="flex items-center gap-3 rounded-xl border border-indigo-300/5 bg-indigo-400/[0.035] px-3 py-3"
                >
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-400/10 text-indigo-300">
                    <Activity size={17} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium">/{event.command}</p>
                    <p className="mt-1 truncate text-[10px] text-indigo-100/35">
                      {event.chat_id} ·{" "}
                      {event.at
                        ? new Date(event.at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Time unavailable"}
                    </p>
                  </div>
                  <span className="rounded-md bg-indigo-400/10 px-2 py-1 text-[9px] text-indigo-200">
                    Command
                  </span>
                </div>
              ))
            ) : (
              <EmptyState
                compact
                icon={<Activity size={20} />}
                title="Your activity starts here"
                hint={
                  stats
                    ? "Real command events appear as your community uses Videl."
                    : "Sign in to load your community’s recent activity."
                }
                action={
                  <button
                    onClick={() => open("analytics")}
                    className="ios-btn ios-btn-glass text-xs"
                  >
                    Open analytics
                  </button>
                }
              />
            )}
          </div>
        </section>
        <section className="ios-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Top Groups</h2>
            <button onClick={() => open("groups")} className="text-indigo-300">
              <ArrowUpRight size={16} />
            </button>
          </div>
          <p className="mt-2 text-[10px] text-indigo-100/35">
            Command activity · last 24 hours
          </p>
          <div className="mt-4 space-y-2">
            {analytics?.top_chats?.length ? (
              analytics.top_chats.slice(0, 5).map((chat, i) => (
                <div
                  key={chat.id}
                  className="flex items-center gap-3 rounded-xl border border-indigo-300/5 px-3 py-3"
                >
                  <span
                    className={`grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br ${i % 2 ? "from-fuchsia-500/30 to-indigo-600/30" : "from-blue-500/30 to-cyan-600/20"} text-xs text-indigo-200`}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{chat.id}</p>
                    <p className="mt-1 text-[10px] text-indigo-100/35">
                      {chat.commands.toLocaleString()} commands
                    </p>
                  </div>
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-indigo-400/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-blue-500 to-fuchsia-500"
                      style={{
                        width: `${Math.max(5, (chat.commands / (analytics.top_chats?.[0]?.commands || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                compact
                icon={<Shield size={20} />}
                title="A home for your communities"
                hint="Add Videl to a group and its command activity will rank here."
                action={
                  <button
                    className="ios-btn ios-btn-glass text-xs"
                    onClick={() => open("groups")}
                  >
                    Open Group Manager
                  </button>
                }
              />
            )}
          </div>
        </section>
      </div>
      <section className="ios-card mt-5 p-5">
        <h2 className="text-sm font-semibold">Quick Actions</h2>
        <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
          {actions.map((action) => (
            <button
              key={action.tab}
              onClick={() => open(action.tab)}
              className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border border-white/10 bg-gradient-to-br ${action.color} px-2 py-4 shadow-lg transition active:translate-y-0`}
            >
              <action.icon size={21} aria-hidden />
              <span className="text-[10px] font-medium">{action.label}</span>
            </button>
          ))}
        </div>
      </section>
      <footer className="mt-6 flex flex-wrap justify-between gap-2 text-[10px] text-indigo-200/30">
        <span>Videl 👑 · Your community, your way.</span>
        <span>Built for Telegram · Music powered by Eldian Network</span>
      </footer>
    </main>
  );
}
