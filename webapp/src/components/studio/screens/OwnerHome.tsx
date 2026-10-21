"use client";
import { useEffect, useState } from "react";
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
} from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio, Section } from "@/components/studio/StudioProvider";
type Metrics = {
  users?: number;
  chats?: number;
  plays?: number;
  uptime?: number;
};
type Analytics = {
  recent_events?: { command: string; chat_id: string; at: string | null }[];
  top_chats?: { id: string; commands: number }[];
};
const actions: {
  tab: Section;
  label: string;
  icon: typeof Send;
  color: string;
}[] = [
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
  const telegram = useTelegram();
  const { open, tab } = useStudio();
  const [refreshTick, refresh] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [measured, setMeasured] = useState<string | null>(null);
  const [stats, setStats] = useState<Metrics | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
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
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";
  return (
    <main className="mx-auto max-w-7xl py-6 sm:py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="ios-caps text-[11px] text-indigo-300/60">
            Your community, connected
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
            {greeting}, {name}! <span className="text-amber-300">👑</span>
          </h1>
          <p className="mt-2 text-sm text-indigo-100/45">
            Here’s what’s happening with your bot and groups today.
          </p>
        </div>
        <span
          title={degradedReason || undefined}
          className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs ${online ? "border-emerald-400/20 bg-emerald-400/5 text-emerald-300" : degraded ? "border-amber-300/20 bg-amber-300/5 text-amber-200" : "border-indigo-300/15 bg-indigo-300/5 text-indigo-200/60"}`}
        >
          <span
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
      </header>
      <section className="studio-hero relative overflow-hidden rounded-3xl border border-indigo-400/25 p-6 sm:p-8">
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
          >
            <span
              className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${m.color}`}
            >
              <m.icon size={21} />
            </span>
            <div>
              <p className="text-xl font-bold tracking-tight sm:text-2xl">
                {m.value}
              </p>
              <p className="mt-1 text-xs text-indigo-100/45">{m.label}</p>
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
        <div
          role="status"
          className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-300/15 bg-indigo-400/5 px-4 py-3 text-xs text-indigo-200/70"
        >
          {error}
          {stats &&
            " · Showing the last successful snapshot, not current totals."}
          <button
            disabled={refreshing}
            className="text-indigo-200 underline underline-offset-4 disabled:opacity-40"
            onClick={() => refresh((n) => n + 1)}
          >
            {refreshing ? "Reconnecting…" : "Retry connection"}
          </button>
        </div>
      )}
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
              <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center">
                <Activity size={28} className="text-indigo-300/25" />
                <p className="text-sm text-indigo-100/50">
                  Your activity starts here
                </p>
                <p className="max-w-60 text-xs leading-5 text-indigo-100/30">
                  {stats
                    ? "Real command events appear as your community uses Videl."
                    : "Sign in to load your community’s recent activity."}
                </p>
              </div>
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
              <div className="flex min-h-44 flex-col items-center justify-center gap-3 text-center">
                <Shield size={28} className="text-indigo-300/25" />
                <p className="text-sm text-indigo-100/50">
                  A home for your communities
                </p>
                <button
                  className="text-xs text-indigo-300"
                  onClick={() => open("groups")}
                >
                  Open Group Manager →
                </button>
              </div>
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
              className={`flex min-h-20 flex-col items-center justify-center gap-2 rounded-xl border border-white/10 bg-gradient-to-br ${action.color} px-2 py-4 shadow-lg transition hover:-translate-y-1 hover:brightness-110`}
            >
              <action.icon size={21} />
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
