"use client";
import { useCallback, useEffect, useState } from "react";
import { downloadCsv } from "@/lib/csv";
import Link from "next/link";
import { Activity, BarChart3, MessageSquare, RefreshCw } from "lucide-react";
import { Callout, EmptyState, LoadingState, PageHeader, SectionHead, Skeleton } from "../ui";

type SeriesPoint = { time: string; commands: number };
type Analytics = {
  ok?: boolean;
  window_hours?: number;
  total_commands?: number;
  active_users?: number;
  series?: SeriesPoint[];
  top_chats?: { id: string; commands: number }[];
  top_commands?: { command: string; count: number }[];
  truncated?: boolean;
  error?: string;
};
type Stats = {
  users?: number;
  chats?: number;
  plays?: number;
  database?: string;
  error?: string;
};

export default function AnalyticsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [sr, ar] = await Promise.all([
        fetch("/api/stats", { cache: "no-store" }),
        fetch("/api/analytics", { cache: "no-store" }),
      ]);
      const [s, a] = await Promise.all([sr.json(), ar.json()]);
      if (!sr.ok) throw new Error(s.error || "Statistics unavailable");
      if (!ar.ok) throw new Error(a.error || "Analytics unavailable");
      setStats(s.stats);
      setAnalytics(a);
    } catch (e: any) {
      setError(e.message || "Unable to load analytics");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 60000);
    return () => clearInterval(id);
  }, [load]);
  function exportReport() {
    if (!analytics || !stats) return;
    downloadCsv(
      `videl-analytics-${new Date().toISOString().slice(0, 10)}.csv`,
      [
        ["type", "label", "count"],
        ["total", "users", stats.users],
        ["total", "chats", stats.chats],
        ["total", "music plays", stats.plays],
        ["window_hours", "window", analytics.window_hours],
        ...[
          ...(analytics.series || []).map((x) => ["hour", x.time, x.commands]),
          ...(analytics.top_commands || []).map((x) => [
            "command",
            x.command,
            x.count,
          ]),
          ...(analytics.top_chats || []).map((x) => ["chat", x.id, x.commands]),
        ],
      ],
    );
  }
  const max = Math.max(1, ...(analytics?.series || []).map((x) => x.commands));
  const tiles = [
    ["Registered users", stats?.users],
    ["Served chats", stats?.chats],
    ["Music plays", stats?.plays],
    ["Commands · 24h", analytics?.total_commands],
  ] as const;
  return (
    <main className="ios-page">
      <PageHeader
        eyebrow="Videl · Telemetry"
        title="Analytics"
        subtitle="Observed command activity from MongoDB · rolling 24-hour window."
        actions={
          <>
            <button
              onClick={() => void load()}
              disabled={loading}
              className="ios-btn ios-btn-glass text-sm"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden />
              Refresh
            </button>
            <button
              disabled={loading || !analytics || !stats || Boolean(error)}
              onClick={exportReport}
              className="ios-btn ios-btn-glass text-sm"
            >
              Download CSV
            </button>
          </>
        }
      />
      {error && (
        <Callout
          tone="warn"
          className="mt-4"
          title="Some numbers could not be refreshed"
        >
          {error} Unavailable data is shown as a dash, never as zero activity.
        </Callout>
      )}
      <section className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Totals">
        {tiles.map(([label, value]) => (
          <div key={String(label)} className="ios-card p-4 sm:p-5">
            <div className="ios-caps text-[10px]">{label}</div>
            {loading && !analytics ? (
              <Skeleton className="mt-3 h-7 w-16" />
            ) : (
              <div className="ios-metric mt-2 text-2xl font-semibold">
                {typeof value === "number" ? value.toLocaleString() : "—"}
              </div>
            )}
          </div>
        ))}
      </section>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <section className="ios-card p-4 sm:p-5">
          <SectionHead title={<span className="inline-flex items-center gap-2"><Activity size={17} aria-hidden /> Commands per hour</span>} hint="Real command events; activity is recorded after this release." />
          {loading && !analytics ? (
            <LoadingState label="Loading command activity" rows={5} className="mt-6" />
          ) : error && !analytics ? (
            <EmptyState
              compact
              icon={<Activity size={19} />}
              title="Activity could not be loaded"
              hint="Refresh to retry. Missing data is not the same as zero activity."
              action={<button onClick={() => void load()} className="ios-btn ios-btn-glass text-xs">Try again</button>}
            />
          ) : !analytics?.total_commands ? (
            <EmptyState
              compact
              icon={<Activity size={19} />}
              title="No commands in the last 24 hours"
              hint="The chart fills as the bot processes commands. Historical data starts at the first recorded event."
            />
          ) : (
            <div className="mt-5 flex h-56 items-end gap-1.5 sm:gap-2" role="img" aria-label="Command counts per hour">
              {analytics.series?.map((point, i) => (
                <div key={`${point.time}-${i}`} className="group relative flex h-full min-w-0 flex-1 flex-col justify-end">
                  <div
                    title={`${point.time}: ${point.commands} commands`}
                    className="w-full rounded-t-md bg-blue-400/75 transition hover:bg-blue-300"
                    style={{ height: `${Math.max(point.commands ? 4 : 0, (point.commands / max) * 100)}%` }}
                  />
                  <span className="mt-2 text-center text-[9px] text-[var(--ios-label-tertiary)]">
                    {i % 4 === 0 ? point.time : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
          {analytics?.truncated && (
            <p className="ios-caption mt-3 text-amber-200/85">
              Chart counts use the most recent 20,000 events; the overall total is exact.
            </p>
          )}
        </section>
        <section className="ios-card p-4 sm:p-5">
          <SectionHead title={<span className="inline-flex items-center gap-2"><BarChart3 size={17} aria-hidden /> Most-used commands</span>} />
          <div className="mt-4 space-y-2">
            {analytics?.top_commands?.length ? (
              analytics.top_commands.map((row) => {
                const peak = Math.max(...(analytics.top_commands || []).map((entry) => entry.count), 1);
                const share = analytics.total_commands ? Math.round((row.count / analytics.total_commands) * 100) : null;
                return (
                  <div key={row.command} className="relative overflow-hidden rounded-xl bg-white/[0.035] px-3 py-2.5">
                    <span aria-hidden className="absolute inset-y-0 left-0 bg-indigo-400/[0.14]" style={{ width: `${Math.max(4, (row.count / peak) * 100)}%` }} />
                    <div className="relative flex items-center justify-between gap-3">
                      <code className="mono truncate">/{row.command}</code>
                      <span className="ios-metric shrink-0 text-sm">
                        {row.count.toLocaleString()}
                        {share !== null && <span className="ml-2 text-[10px] text-[var(--ios-label-tertiary)]">{share}%</span>}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyState compact icon={<BarChart3 size={19} />} title="No command activity yet" hint="Commands appear here once the bot records them." />
            )}
          </div>
        </section>
      </div>
      <section className="ios-card ios-section p-4 sm:p-5">
        <SectionHead title="Most active chats" hint="Ranked by commands processed, not message volume." />
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {analytics?.top_chats?.length ? (
            analytics.top_chats.map((chat) => (
              <div key={chat.id} className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.035] px-3 py-3">
                <code className="mono truncate text-xs">{chat.id}</code>
                <span className="ios-metric shrink-0 text-sm">
                  {chat.commands.toLocaleString()} <span className="ios-metric-unit">commands</span>
                </span>
              </div>
            ))
          ) : (
            <div className="sm:col-span-2">
              <EmptyState compact icon={<MessageSquare size={19} />} title="No chat activity yet" hint="A chat appears once it sends the bot a command." />
            </div>
          )}
        </div>
      </section>
      <div className="ios-caption ios-section flex flex-wrap items-center justify-between gap-2">
        <span>MongoDB status: {stats?.database || "not reported"}</span>
        <span>Only command name, chat ID and user ID are stored; no message text.</span>
        <Link href="/" className="text-white underline decoration-white/25 underline-offset-4">
          Control room →
        </Link>
      </div>
    </main>
  );
}
