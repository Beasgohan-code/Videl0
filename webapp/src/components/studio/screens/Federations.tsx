"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, Globe2, Loader2, RefreshCw, Search, ShieldOff, Users } from "lucide-react";
import { errorHint } from "@/lib/group-admin";
import { Callout, EmptyState, LoadingState, PageHeader } from "../ui";

type FedChat = { id: number; title: string };
type FedBan = { user: number | null; reason: string; by: number | null; at: string | null };
type Federation = {
  id: string;
  name: string;
  owner: number | null;
  created: string | null;
  chats: FedChat[];
  chat_count: number;
  bans: number;
  admins: number[];
};
type FederationDetail = Omit<Federation, "bans" | "chat_count"> & {
  chats: FedChat[];
  admins: number[];
  bans: FedBan[];
};

function stamp(iso: string | null): string {
  if (!iso) return "date unknown";
  const date = new Date(iso);
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : "date unknown";
}

export default function FederationsScreen() {
  const [list, setList] = useState<Federation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<FederationDetail | null>(null);
  const [query, setQuery] = useState("");
  const [banQuery, setBanQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/federation", { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(errorHint(String(data.error || "Federations could not be loaded"), response.status));
      const rows: Federation[] = Array.isArray(data.federations) ? data.federations : [];
      setList(rows);
      setSelected((current) => (rows.some((row) => row.id === current) ? current : (rows[0]?.id ?? null)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Federations could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/federation/${encodeURIComponent(id)}`, { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(errorHint(String(data.error || "This federation could not be read"), response.status));
      setDetail(data.federation as FederationDetail);
    } catch (e) {
      setDetail(null);
      setError(e instanceof Error ? e.message : "This federation could not be read");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected) {
      setDetail(null);
      void loadDetail(selected);
    }
  }, [selected, loadDetail]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return list;
    return list.filter((row) => `${row.name} ${row.id}`.toLowerCase().includes(needle));
  }, [list, query]);

  const bans = useMemo(() => {
    const needle = banQuery.trim().toLowerCase();
    if (!detail) return [];
    if (!needle) return detail.bans;
    return detail.bans.filter((ban) => `${ban.user ?? ""} ${ban.reason}`.toLowerCase().includes(needle));
  }, [detail, banQuery]);

  async function unban(user: number) {
    if (!selected || saving) return;
    if (!window.confirm(`Lift the federation ban on ${user}? Every member group of this federation stops enforcing it.`))
      return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/federation/${encodeURIComponent(selected)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "unban", user_id: user }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(errorHint(String(data.error || "The ban was not lifted"), response.status));
      setDetail((current) =>
        current ? { ...current, bans: current.bans.filter((ban) => ban.user !== user) } : current,
      );
      setList((rows) =>
        rows.map((row) => (row.id === selected ? { ...row, bans: Math.max(0, row.bans - (data.removed ? 1 : 0)) } : row)),
      );
      setNotice(data.removed ? `Ban lifted for ${user}.` : `No stored ban existed for ${user}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The ban was not lifted");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="ios-page">
      <PageHeader
        eyebrow="Videl · Community"
        title="Federations"
        subtitle="Shared ban lists across groups. Creating a federation and issuing a ban stay on the bot commands."
        actions={
          <button onClick={() => void load()} disabled={loading || saving} className="ios-btn ios-btn-glass text-sm">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden /> Refresh
          </button>
        }
      />

      {error && (
        <Callout tone="warn" className="mt-4" title="That federation change did not go through" icon={<AlertCircle size={18} aria-hidden />}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="min-w-0 flex-1">{error}</span>
            <button onClick={() => setError("")} className="text-xs underline underline-offset-2">Dismiss</button>
          </div>
        </Callout>
      )}
      {notice && !error && (
        <Callout tone="success" className="mt-4" icon={<Check size={16} aria-hidden />}>
          {notice}
        </Callout>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <section className="ios-card p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Your federations</h2>
            <span className="ios-pill">{visible.length}</span>
          </div>
          <label className="sr-only" htmlFor="fed-search">Search federations</label>
          <div className="relative mt-3">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ios-label-tertiary)]" />
            <input
              id="fed-search"
              aria-label="Search federations"
              placeholder="Search by name or ID…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="ios-input pl-9"
            />
          </div>
          <div className="mt-3 space-y-2">
            {loading && <LoadingState label="Loading federations" rows={3} className="p-1" />}
            {!loading && !list.length && (
              <EmptyState
                compact
                icon={<Globe2 size={19} />}
                title="No federation yet"
                hint={<>Create one in a group with <code className="mono">/newfed &lt;name&gt;</code>, then add groups with <code className="mono">/joinfed</code>.</>}
              />
            )}
            {visible.map((row) => (
              <button
                key={row.id}
                onClick={() => setSelected(row.id)}
                disabled={saving}
                className={`w-full rounded-2xl border p-3 text-left transition ${
                  selected === row.id
                    ? "border-white/25 bg-white/[0.08]"
                    : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Globe2 size={16} className="shrink-0 text-[var(--ios-label-tertiary)]" />
                  <span className="min-w-0 flex-1 truncate font-medium">{row.name}</span>
                </span>
                <span className="mt-1 block truncate text-xs text-[var(--ios-label-secondary)]">
                  <code className="break-all">{row.id}</code> · {row.chat_count} group{row.chat_count === 1 ? "" : "s"} · {row.bans} banned
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="ios-card p-4 sm:p-5">
          {!selected ? (
            <EmptyState compact icon={<Globe2 size={19} />} title="Nothing selected" hint="Select a federation to review its groups and bans." />
          ) : detailLoading && !detail ? (
            <LoadingState label="Reading federation" rows={4} className="p-1" />
          ) : !detail ? (
            <EmptyState compact title="This federation could not be read" hint="Refresh to try again; its stored records may still be intact." />
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate font-semibold">{detail.name}</h2>
                  <p className="ios-caption mt-1">
                    <code>{detail.id}</code> · owner {detail.owner ?? "unknown"} · created {stamp(detail.created)}
                  </p>
                </div>
                <span className="ios-pill">{detail.chats.length} groups</span>
              </div>

              <div className="mt-4 rounded-xl bg-white/[0.03] p-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold"><Users size={15} /> Member groups</h3>
                {!detail.chats.length ? (
                  <p className="ios-caption mt-1">No group has joined this federation yet.</p>
                ) : (
                  <ul className="mt-2 space-y-1 text-xs">
                    {detail.chats.map((chat) => (
                      <li key={chat.id} className="flex items-center justify-between gap-2">
                        <span className="truncate">{chat.title}</span>
                        <code className="shrink-0 text-[var(--ios-label-tertiary)]">{chat.id}</code>
                      </li>
                    ))}
                  </ul>
                )}
                {detail.admins.length > 0 && (
                  <p className="ios-caption mt-2">Federation admins: {detail.admins.join(", ")}</p>
                )}
              </div>

              <div className="mt-3 rounded-xl bg-white/[0.03] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">
                    <ShieldOff size={15} /> Federation bans
                    <span className="ios-pill text-[10px]">{detail.bans.length}</span>
                  </h3>
                  <label className="sr-only" htmlFor="ban-search">Search bans</label>
                  <input
                    id="ban-search"
                    aria-label="Search bans"
                    placeholder="Filter by user or reason…"
                    value={banQuery}
                    onChange={(event) => setBanQuery(event.target.value)}
                    className="ios-input w-48 py-1.5 text-xs"
                  />
                </div>
                {!detail.bans.length ? (
                  <p className="ios-caption mt-2">No federation ban is stored.</p>
                ) : bans.length === 0 ? (
                  <p className="ios-caption mt-2">No ban matches this filter.</p>
                ) : (
                  <ul className="mt-2 divide-y divide-white/[0.06]">
                    {bans.map((ban, index) => (
                      <li key={`${ban.user ?? "u"}-${index}`} className="flex items-start justify-between gap-2 py-2 text-xs">
                        <div className="min-w-0">
                          <div className="font-medium"><code>{ban.user ?? "unknown"}</code></div>
                          <div className="truncate text-[var(--ios-label-secondary)]">{ban.reason || "No reason stored"}</div>
                          <div className="ios-caption">
                            {stamp(ban.at)}
                            {ban.by ? ` · by ${ban.by}` : ""}
                          </div>
                        </div>
                        <button
                          disabled={saving || !ban.user}
                          onClick={() => ban.user && void unban(ban.user)}
                          className="ios-btn ios-btn-glass shrink-0 text-[11px] disabled:opacity-40"
                          aria-label={`Lift federation ban on ${ban.user}`}
                        >
                          Lift ban
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <p className="mt-3 text-xs text-[var(--ios-label-tertiary)]">
                Lifting a ban deletes the stored record the bot reads; it does not unban anyone from groups that already
                enforced it. Re-add a member in Telegram if needed.
              </p>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
