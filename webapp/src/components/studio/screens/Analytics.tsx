"use client";
import { useCallback, useEffect, useState } from "react";
import { downloadCsv } from "@/lib/csv";
import Link from "next/link";
import { Activity, BarChart3, RefreshCw } from "lucide-react";

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
  return (
    <main className="mx-auto max-w-6xl py-5 sm:py-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="ios-caption2">VIDEL · TELEMETRY</p>
          <h1 className="mt-2 ios-title">Analytics</h1>
          <p className="mt-1 ios-subheadline">
            Observed command activity from MongoDB · rolling 24-hour window.
          </p>
        </div>
        <button
          onClick={() => void load()}
          disabled={loading}
          className="ios-btn ios-btn-glass text-sm"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />{" "}
          Refresh
        </button>
      </header>
      <button
        disabled={loading || !analytics || !stats || Boolean(error)}
        onClick={exportReport}
        className="ios-btn ios-btn-glass mt-3 text-xs disabled:opacity-40"
      >
        Download observed analytics · CSV
      </button>
      {error && (
        <div
          role="alert"
          className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm text-amber-100"
        >
          {error}
        </div>
      )}
      <section className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Registered users", stats?.users],
          ["Served chats", stats?.chats],
          ["Music plays", stats?.plays],
          ["Commands · 24h", analytics?.total_commands],
        ].map(([label, value]) => (
          <div key={String(label)} className="ios-card p-4 sm:p-5">
            <div className="ios-caption2">{label}</div>
            <div className="mt-2 text-2xl font-semibold">
              {typeof value === "number" ? value.toLocaleString() : "—"}
            </div>
          </div>
        ))}
      </section>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <section className="ios-card p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <Activity size={17} />
            <h2 className="font-semibold">Commands per hour</h2>
          </div>
          <p className="mt-1 ios-caption">
            Real command events; activity is recorded after this release.
          </p>
          {loading && !analytics ? (
            <div className="mt-8 text-sm text-[var(--ios-label-secondary)]">
              Loading data…
            </div>
          ) : error && !analytics ? (
            <p className="mt-5 text-sm text-amber-200">
              Activity could not be loaded. Refresh to retry; unavailable data
              is not zero activity.
            </p>
          ) : !analytics?.total_commands ? (
            <div className="mt-5 rounded-xl bg-white/[0.03] p-5 text-sm text-[var(--ios-label-secondary)]">
              No commands have been recorded in the last 24 hours. Historical
              data starts as the bot processes commands.
            </div>
          ) : (
            <div className="mt-5 flex h-56 items-end gap-1.5 sm:gap-2">
              {analytics.series?.map((point, i) => (
                <div
                  key={`${point.time}-${i}`}
                  className="group relative flex h-full min-w-0 flex-1 flex-col justify-end"
                >
                  <div
                    title={`${point.time}: ${point.commands} commands`}
                    className="w-full rounded-t-md bg-blue-400/75 transition hover:bg-blue-300"
                    style={{
                      height: `${Math.max(point.commands ? 4 : 0, (point.commands / max) * 100)}%`,
                    }}
                  />
                  <span className="mt-2 text-center text-[9px] text-[var(--ios-label-tertiary)]">
                    {i % 4 === 0 ? point.time : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
          {analytics?.truncated && (
            <p className="mt-3 text-xs text-amber-200">
              Chart counts are based on the most recent 20,000 events; overall
              total is exact.
            </p>
          )}
        </section>
        <section className="ios-card p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <BarChart3 size={17} />
            <h2 className="font-semibold">Most-used commands</h2>
          </div>
          <div className="mt-4 space-y-2">
            {analytics?.top_commands?.length ? (
              analytics.top_commands.map((row) => (
                <div
                  key={row.command}
                  className="flex items-center justify-between rounded-xl bg-white/[0.035] px-3 py-2.5"
                >
                  <code>/{row.command}</code>
                  <span className="text-sm tabular-nums">
                    {row.count.toLocaleString()}
                  </span>
                </div>
              ))
            ) : (
              <p className="ios-caption">
                No command activity is available yet.
              </p>
            )}
          </div>
        </section>
      </div>
      <section className="mt-4 ios-card p-4 sm:p-5">
        <h2 className="font-semibold">Most active chats</h2>
        <p className="mt-1 ios-caption">
          Ranked by commands processed, not message volume.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {analytics?.top_chats?.length ? (
            analytics.top_chats.map((chat) => (
              <div
                key={chat.id}
                className="flex items-center justify-between rounded-xl bg-white/[0.035] px-3 py-3"
              >
                <code className="text-xs">{chat.id}</code>
                <span className="text-sm">
                  {chat.commands.toLocaleString()} commands
                </span>
              </div>
            ))
          ) : (
            <p className="ios-caption">No chat activity is available yet.</p>
          )}
        </div>
      </section>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 ios-caption">
        <span>MongoDB status: {stats?.database || "not reported"}</span>
        <span>
          Only command name, chat ID and user ID are stored; no message text.
        </span>
        <Link href="/" className="text-white">
          Control room →
        </Link>
      </div>
    </main>
  );
}
