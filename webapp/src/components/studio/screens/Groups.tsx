"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ExternalLink, RefreshCw, Shield, ShieldCheck, Users } from "lucide-react";

type Group = { id: number; title: string; type: string; members: number | null; available: boolean; settings: Record<string, boolean> };
const controls = [
  { key: "antispam", label: "Anti-Spam", description: "Delete bursts above 6 messages per user in 8 seconds" },
  { key: "welcome_enabled", label: "Welcome message", description: "Greet new members using your saved welcome text" },
  { key: "lock_forwards", label: "Block forwards", description: "Delete forwarded messages from non-admin members" },
  { key: "lock_links", label: "Block links", description: "Delete messages containing links" },
  { key: "lock_media", label: "Block media", description: "Delete photo, video and document messages" },
  { key: "lock_stickers", label: "Block stickers", description: "Delete sticker messages" },
] as const;

export default function GroupsPage({ automation = false }: { automation?: boolean } = {}) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/groups", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Group data could not be loaded");
      setGroups(data.chats || []);
      setSelected(current => current ?? data.chats?.[0]?.id ?? null);
      if (data.truncated) setError("Showing the first 25 groups; the bot has additional served groups.");
    } catch (e: any) { setError(e.message || "Group data could not be loaded"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const active = groups.find(group => group.id === selected) || null;
  async function setLock(key: string, enabled: boolean) {
    if (!active) return;
    setSaving(key); setError("");
    try {
      const response = await fetch("/api/groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chat_id: active.id, settings: { [key]: enabled } }) });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Setting update failed");
      setGroups(all => all.map(group => group.id === active.id ? { ...group, settings: { ...group.settings, [key]: enabled } } : group));
    } catch (e: any) { setError(e.message || "Setting update failed"); }
    finally { setSaving(null); }
  }

  return <main className="mx-auto max-w-6xl py-5 sm:py-8">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="ios-caption2">VIDEL · COMMUNITY</p><h1 className="mt-2 ios-title">{automation ? "Automation" : "Group Manager"}</h1><p className="mt-1 ios-subheadline">Welcome flows and protection rules, saved to your community.</p></div>
      <button onClick={() => void load()} className="ios-btn ios-btn-glass text-sm" disabled={loading}><RefreshCw size={16} className={loading ? "animate-spin" : ""}/> Refresh</button>
    </header>
    {error && <div role="status" className="mt-4 flex items-start gap-2 rounded-2xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm text-amber-100"><AlertCircle size={18} className="shrink-0"/>{error}</div>}
    <div className="mt-6 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="ios-card p-4 sm:p-5">
        <div className="flex items-center justify-between"><h2 className="font-semibold">Served groups</h2><span className="ios-pill">{groups.length} loaded</span></div>
        <div className="mt-3 space-y-2">
          {loading && <p className="ios-caption p-3">Loading actual Telegram chats…</p>}
          {!loading && !groups.length && <div className="rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">No served chats were found in MongoDB. Add the bot to a group and run <code>/start</code>.</div>}
          {groups.map(group => <button key={group.id} onClick={() => setSelected(group.id)} className={`w-full rounded-2xl border p-3 text-left transition ${selected === group.id ? "border-white/25 bg-white/[0.08]" : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"}`}>
            <span className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/[0.07]"><Shield size={18}/></span><span className="min-w-0 flex-1"><span className="block truncate font-medium">{group.title}</span><span className="mt-1 block truncate text-xs text-[var(--ios-label-secondary)]">{group.id} · {group.type}{group.members !== null ? ` · ${group.members} members` : ""}</span></span><span className={`h-2.5 w-2.5 rounded-full ${group.available ? "bg-[#30D158]" : "bg-[#FF9F0A]"}`} /></span>
          </button>)}
        </div>
      </section>

      <section className="ios-card p-4 sm:p-5">
        <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/[0.07]"><ShieldCheck size={19}/></span><div><h2 className="font-semibold">Protection settings</h2><p className="ios-caption">Saved directly to MongoDB</p></div></div>
        {!active ? <div className="mt-5 rounded-xl bg-white/[0.03] p-4 text-sm text-[var(--ios-label-secondary)]">Select a served group to review its settings.</div> : <>
          <div className="mt-4 rounded-xl bg-white/[0.035] p-3"><div className="font-medium">{active.title}</div><div className="mt-1 text-xs text-[var(--ios-label-secondary)]">{active.id}</div></div>
          {!active.available && <p className="mt-3 text-sm text-amber-200">Telegram could not retrieve this chat. Confirm the bot is still a member and has permission to access chat info.</p>}
          <div className="mt-4 divide-y divide-white/[0.07]">
            {controls.map(control => {
              const enabled = Boolean(active.settings?.[control.key]);
              return <div key={control.key} className="flex items-center justify-between gap-3 py-4"><div><div className="text-sm font-medium">{control.label}</div><div className="mt-1 text-xs text-[var(--ios-label-secondary)]">{control.description}</div></div><button type="button" aria-label={`${enabled ? "Disable" : "Enable"} ${control.label}`} aria-pressed={enabled} disabled={saving !== null || !active.available} onClick={() => void setLock(control.key, !enabled)} className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-40 ${enabled ? "bg-[#30D158]" : "bg-white/15"}`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${enabled ? "translate-x-6" : "translate-x-1"}`}/></button></div>;
            })}
          </div>
          <p className="mt-3 text-xs text-[var(--ios-label-tertiary)]">The bot needs delete-message permission for lock actions to take effect.</p>
          <div className="mt-4 flex flex-wrap gap-2"><Link href="/" className="ios-btn ios-btn-glass text-sm">Open control room</Link><a href={`https://t.me/c/${String(active.id).replace(/^-100/, "")}`} target="_blank" rel="noreferrer" className="ios-btn ios-btn-glass text-sm"><ExternalLink size={15}/> Open chat</a></div>
        </>}
      </section>
    </div>
    <p className="mt-4 flex items-center gap-2 ios-caption"><Users size={14}/> Member counts are fetched from Telegram only when available. No sample groups or activity values are rendered.</p>
  </main>;
}
