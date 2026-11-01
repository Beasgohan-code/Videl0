"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePlayerSession } from "@/lib/player";
import { CaseTimeline } from "@/components/studio/CaseTimeline";
import { EscalationSettings } from "@/components/studio/EscalationSettings";
import type { Escalation, MemberCase } from "@/lib/group-admin";
import { BOT_COMMANDS } from "@/lib/commands";
import { auditCsv } from "@/lib/audit-export";
import { ArrowUpRight, Bell, Check, ChevronRight, Clock3, Download, LockKeyhole, MessageCircle, RefreshCw, Search, Shield, Users, X } from "lucide-react";

type Group = { id: number; title: string; members?: number | null; type?: string; bot_admin?: boolean | null };
type GroupDetail = {
  chat: { id: number; title: string; member_count?: number | null; type?: string; available?: boolean; bot?: { is_admin?: boolean } };
  settings: Record<string, unknown>;
  revision?: number;
  presets?: Record<string, { label?: string; settings?: Record<string, boolean> }>;
  community?: {
    disabled_commands?: string[]; warns?: Array<{ user_id?: number; count?: number }>;
    approved?: number[]; warn_limit?: number; blacklist?: Array<{ trigger: string; mode?: string }>;
    notes?: Array<{ name: string; type?: string }>; filters?: Array<{ keyword: string; reply?: string }>;
  };
  automation?: {
    quiet_hours?: Record<string, unknown>; escalation?: Escalation;
    protection?: Record<string, unknown>;
  };
  inbox?: { reports?: Array<{ id: string; target?: number; text?: string; reporter?: number }>; join_requests?: Array<{ user_id: number; name?: string; username?: string }> };
  cases?: MemberCase[];
  members?: Array<{ user_id: number; name?: string; username?: string; status?: string }>;
  members_available?: boolean;
  rights?: Record<string, boolean>;
  setup_checklist?: Array<{ id: string; label: string; complete: boolean; detail: string }>;
  scope?: string;
};
type Tab = "home" | "safety" | "community" | "members" | "inbox" | "cases" | "commands" | "activity";
const tabs: Array<{ id: Tab; label: string; icon: typeof Shield }> = [
  { id: "home", label: "Overview", icon: MessageCircle }, { id: "safety", label: "Protection", icon: Shield },
  { id: "community", label: "Community", icon: Users }, { id: "members", label: "Members", icon: Users }, { id: "inbox", label: "Inbox", icon: Bell },
  { id: "cases", label: "Cases", icon: Clock3 }, { id: "commands", label: "Commands", icon: LockKeyhole }, { id: "activity", label: "Activity", icon: Clock3 },
];
const prettify = (key: string) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
function rightsGuidance(id: string): string | null {
  if (id === "bot_admin") return "In Telegram, open the group → Manage Group → Administrators → Add Administrator or select Videl, then grant the required rights. An existing group admin must make this change.";
  if (id === "delete_messages") return "In Telegram, open the group → Manage Group → Administrators → Videl, then enable Delete Messages. A group admin must save the change.";
  if (id === "restrict_members") return "In Telegram, open the group → Manage Group → Administrators → Videl, then enable Restrict Members. A group admin must save the change.";
  return null;
}
function openExternalInvite(raw: string) {
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.hostname !== "t.me") return;
    const webApp = (window as Window & { Telegram?: { WebApp?: { openLink?: (href: string, options?: { try_instant_view?: boolean }) => void } } }).Telegram?.WebApp;
    if (webApp?.openLink) webApp.openLink(url.href, { try_instant_view: false });
    else window.open(url.href, "_blank", "noopener,noreferrer");
  } catch { /* Do not open malformed invite links. */ }
}

export default function AdminGroups() {
  const session = usePlayerSession();
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const selectedRef = useRef<number | null>(null);
  const detailRequest = useRef(0);
  const auditRequest = useRef(0);
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, unknown>>>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditKind, setAuditKind] = useState("");
  const [auditQuery, setAuditQuery] = useState("");
  const [auditActor, setAuditActor] = useState("");
  const [auditFrom, setAuditFrom] = useState("");
  const [auditThrough, setAuditThrough] = useState("");
  const [auditFilter, setAuditFilter] = useState({ kind: "", query: "", actor: "", from: "", through: "" });
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<Tab>("home");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [memberId, setMemberId] = useState("");
  const [muteMinutes, setMuteMinutes] = useState("60");
  const [ruleText, setRuleText] = useState("");
  const [welcomeText, setWelcomeText] = useState("");
  const [goodbyeText, setGoodbyeText] = useState("");
  const [blacklistTerm, setBlacklistTerm] = useState("");
  const [noteName, setNoteName] = useState("");
  const [noteText, setNoteText] = useState("");
  const [filterKeyword, setFilterKeyword] = useState("");
  const [filterReply, setFilterReply] = useState("");
  const [warnLimit, setWarnLimit] = useState("3");
  const [commandQuery, setCommandQuery] = useState("");
  const [invite, setInvite] = useState("");

  const loadGroups = useCallback(async (refresh = false) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/manager${refresh ? "?refresh=1" : ""}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Your administered groups could not be loaded.");
      const rows = Array.isArray(data.groups) ? data.groups as Group[] : [];
      setGroups(rows);
      if (selectedRef.current !== null && !rows.some((row) => row.id === selectedRef.current)) {
        selectedRef.current = null; setSelected(null); setDetail(null);
      }
      if (!rows.length) setNotice(refresh ? "Telegram checked a limited batch. If you manage many groups, refresh again to scan more." : "No verified groups yet. Refresh to check groups Videl currently serves.");
      else setNotice("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not load groups."); }
    finally { setLoading(false); }
  }, []);

  const loadDetail = useCallback(async (id: number) => {
    const request = ++detailRequest.current;
    setDetailLoading(true); setError("");
    try {
      const response = await fetch(`/api/manager/${id}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "This group is no longer available to your account.");
      if (request !== detailRequest.current || selectedRef.current !== id) return;
      setDetail(data as GroupDetail);
      setRuleText(String(data.settings?.rules || ""));
      setWelcomeText(String(data.settings?.welcome_message || ""));
      setGoodbyeText(String(data.settings?.goodbye_message || ""));
      setWarnLimit(String(data.community?.warn_limit || 3));
    } catch (failure) {
      if (request === detailRequest.current) { setError(failure instanceof Error ? failure.message : "Could not open this group."); setDetail(null); }
    } finally { if (request === detailRequest.current) setDetailLoading(false); }
  }, []);

  const loadAudit = useCallback(async (id: number, filters: { kind: string; query: string; actor: string; from: string; through: string }) => {
    const request = ++auditRequest.current;
    setAuditLoading(true);
    try {
      const params = new URLSearchParams({ audit: "1" });
      if (filters.kind) params.set("kind", filters.kind);
      if (filters.query.trim()) params.set("q", filters.query.trim().slice(0, 60));
      if (/^[1-9][0-9]{0,19}$/.test(filters.actor)) params.set("actor", filters.actor);
      if (filters.from) params.set("from", `${filters.from}T00:00:00.000Z`);
      if (filters.through) params.set("through", `${filters.through}T23:59:59.999Z`);
      const response = await fetch(`/api/manager/${id}?${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "The audit history could not be loaded.");
      if (request === auditRequest.current && selectedRef.current === id) setAudit(Array.isArray(data.events) ? data.events.slice(0, 40) : []);
    } catch (failure) {
      if (request === auditRequest.current) setError(failure instanceof Error ? failure.message : "The audit history could not be loaded.");
    } finally { if (request === auditRequest.current) setAuditLoading(false); }
  }, []);

  useEffect(() => { if (session.player) void loadGroups(); }, [session.player, loadGroups]);
  useEffect(() => { if (selected !== null) void loadDetail(selected); else { detailRequest.current++; setDetail(null); setDetailLoading(false); } }, [selected, tab, loadDetail]);
  useEffect(() => { if (selected !== null && tab === "activity") void loadAudit(selected, auditFilter); else { auditRequest.current++; setAudit([]); setAuditLoading(false); } }, [selected, tab, auditFilter, loadAudit]);

  const sendAction = useCallback(async (payload: Record<string, unknown>): Promise<boolean> => {
    if (selected === null) return false;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/manager/${selected}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, ...(detail?.revision !== undefined ? { revision: detail.revision } : {}) }) });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Telegram did not confirm this change.");
      setNotice("Saved and verified with Telegram.");
      if (payload.action === "invite_link") setInvite(String(data.invite_link || ""));
      await loadDetail(selected);
      await loadGroups();
      return true;
    } catch (failure) { setError(failure instanceof Error ? failure.message : "The change could not be confirmed. Refresh before retrying."); return false; }
    finally { setSaving(false); }
  }, [selected, detail?.revision, tab, loadDetail, loadGroups]);

  const visibleGroups = useMemo(() => groups.filter((group) => `${group.title} ${group.id}`.toLowerCase().includes(query.trim().toLowerCase())), [groups, query]);
  const canRestrict = Boolean(detail?.rights?.can_restrict_members);
  const canInvite = Boolean(detail?.rights?.can_invite_users);
  const quiet = detail?.automation?.quiet_hours || {};
  const escalation = detail?.automation?.escalation || {};
  const quietStart = typeof quiet.start === "string" ? quiet.start : "22:00";
  const quietEnd = typeof quiet.end === "string" ? quiet.end : "07:00";

  if (session.player === undefined) return <div className="mx-auto max-w-5xl p-6 text-indigo-100/60">Checking your Telegram session…</div>;
  if (!session.player) return <main className="mx-auto max-w-3xl px-4 py-12"><div className="rounded-[2rem] border border-indigo-300/15 bg-[#11142a] p-7 shadow-2xl sm:p-10"><div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-indigo-400/15 text-indigo-200"><Users /></div><p className="text-xs font-semibold uppercase tracking-[.2em] text-indigo-300">Videl · Group admin</p><h1 className="mt-3 text-3xl font-semibold text-white">Your groups, your controls.</h1><p className="mt-3 max-w-xl leading-7 text-indigo-100/60">Sign in securely with Telegram to see only groups where Telegram confirms you are an administrator. This workspace never unlocks owner fleet or backup controls.</p>{session.error && <p className="mt-4 rounded-xl bg-rose-500/10 p-3 text-sm text-rose-200">{session.error}</p>}<button onClick={() => void session.signIn()} className="mt-6 rounded-xl bg-indigo-400 px-5 py-3 font-semibold text-[#12152b]">Continue with Telegram</button></div></main>;

  return <main className="mx-auto max-w-[1450px] px-3 pb-12 pt-5 sm:px-6">
    <header className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><p className="text-[11px] font-semibold uppercase tracking-[.2em] text-indigo-300">Videl · Telegram group manager</p><h1 className="mt-1 text-2xl font-semibold text-white sm:text-3xl">Your groups</h1><p className="mt-1 text-sm text-indigo-100/50">Group-by-group controls · verified as {session.player.name || `user ${session.player.id}`}</p></div><div className="flex gap-2"><button onClick={() => void loadGroups(true)} disabled={loading} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white disabled:opacity-50"><RefreshCw size={15} className={loading ? "animate-spin" : ""}/> Refresh Telegram</button><button onClick={() => void session.signOut()} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-indigo-100/60">Sign out</button></div></header>
    {(error || notice) && <div role={error ? "alert" : "status"} className={`mb-4 rounded-xl border p-3 text-sm ${error ? "border-rose-300/20 bg-rose-500/10 text-rose-200" : "border-indigo-300/15 bg-indigo-300/5 text-indigo-100/75"}`}>{error || notice}</div>}
    <div className="grid min-h-[680px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-white/10 bg-[#101329]">
        <div className="border-b border-white/5 p-4"><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold text-white">Administered groups</h2><p className="mt-0.5 text-xs text-indigo-100/40">{groups.length} verified</p></div><Users size={18} className="text-indigo-300"/></div><label className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2"><Search size={15} className="text-indigo-100/35"/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find by name or ID" aria-label="Find a group by name or ID" className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-indigo-100/30"/></label></div>
        <div className="max-h-[590px] overflow-auto p-2">{visibleGroups.map((group) => <button key={group.id} onClick={() => { const changed = selectedRef.current !== group.id; selectedRef.current = group.id; setSelected(group.id); if (changed) setDetail(null); setTab("home"); setInvite(""); }} className={`mb-1 flex w-full items-center gap-3 rounded-xl p-3 text-left transition ${selected === group.id ? "bg-indigo-400/15 ring-1 ring-indigo-300/20" : "hover:bg-white/5"}`}><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo-300/20 to-cyan-300/10 font-bold text-indigo-100">{group.title.slice(0,1).toUpperCase()}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{group.title}</p><p className="mt-0.5 text-xs text-indigo-100/40">{group.members ? `${group.members} members` : "Telegram group"}{group.bot_admin === false ? " · Bot needs admin" : group.bot_admin === true ? " · Bot admin" : ""}</p></div><ChevronRight size={15} className="text-indigo-100/35"/></button>)}{!loading && !visibleGroups.length && <p className="p-4 text-sm leading-6 text-indigo-100/40">No verified groups found. Add Videl to a group and use Refresh Telegram.</p>}</div>
        <div className="border-t border-white/5 p-3 text-[11px] leading-5 text-indigo-100/35">Telegram does not expose a complete member directory to bots. Member tools below accept a user ID and verify it live.</div>
      </aside>
      <section className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-[#101329]">
        {!selected || !detail ? <div className="grid min-h-[500px] place-items-center p-6 text-center"><div><div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-indigo-300/10 text-indigo-200"><MessageCircle/></div><h2 className="mt-4 text-xl font-semibold text-white">{detailLoading ? "Loading group details…" : "Select one of your groups"}</h2><p className="mt-2 max-w-md text-sm leading-6 text-indigo-100/45">Controls are scoped to that group and your current Telegram administrator rights.</p></div></div> : <>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 p-4 sm:p-5"><div className="flex items-center gap-3"><div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-indigo-400/25 to-cyan-300/10 text-lg font-bold text-white">{detail.chat.title.slice(0,1).toUpperCase()}</div><div><h2 className="font-semibold text-white">{detail.chat.title}</h2><p className="mt-0.5 text-xs text-indigo-100/45">{detail.chat.member_count ? `${detail.chat.member_count} members · ` : ""}Telegram-verified admin session</p></div></div><button onClick={() => void loadDetail(selected)} disabled={detailLoading} className="rounded-lg p-2 text-indigo-100/60 hover:bg-white/5" aria-label="Refresh group"><RefreshCw size={16} className={detailLoading ? "animate-spin" : ""}/></button></div>
          <nav className="flex gap-1 overflow-x-auto border-b border-white/5 p-2">{tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-pressed={tab === id} onClick={() => setTab(id)} className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${tab === id ? "bg-indigo-400/15 text-indigo-100" : "text-indigo-100/45 hover:bg-white/5"}`}><Icon size={14}/>{label}</button>)}</nav>
          <div className="space-y-4 p-4 sm:p-6">
            {tab === "home" && <><div className="grid gap-3 sm:grid-cols-3"><Metric label="Group" value={detail.chat.type || "Group"}/><Metric label="Members" value={String(detail.chat.member_count ?? "—")}/><Metric label="Your access" value="Administrator"/></div><Card title="Quick actions" subtitle="Only actions allowed by your current Telegram permissions are enabled."><div className="flex flex-wrap gap-2"><button disabled={!canInvite || saving} onClick={() => void sendAction({ action: "invite_link" })} className="action-button"><ArrowUpRight size={15}/> Create invite link</button><button onClick={() => setTab("safety")} className="action-button"><Shield size={15}/> Protection settings</button><button onClick={() => setTab("inbox")} className="action-button"><Bell size={15}/> Review group inbox</button></div>{!canInvite && <p className="mt-3 text-xs text-amber-200/70">Invite links need the Telegram “Invite users” right.</p>}{invite && <button type="button" onClick={() => openExternalInvite(invite)} className="mt-3 block w-full break-all rounded-xl bg-emerald-400/10 p-3 text-left text-sm text-emerald-200">Open invite in browser ↗<span className="mt-1 block text-xs opacity-65">{invite}</span></button>}</Card><Card title="Group health & setup" subtitle="Live setup checks for this group. Telegram changes must be made by a group administrator; Videl will never promote itself."><div className="mb-3 grid gap-2 sm:grid-cols-3"><Metric label="Telegram group" value={detail.chat.available === false ? "Unavailable" : "Reachable"}/><Metric label="Active switches" value={String(Object.values(detail.settings).filter((value) => value === true).length)}/><Metric label="Pending work" value={String((detail.inbox?.join_requests?.length || 0) + (detail.inbox?.reports?.length || 0))}/></div><div className="divide-y divide-white/5">{(detail.setup_checklist || []).map((item) => { const guidance = !item.complete ? rightsGuidance(item.id) : null; return <div key={item.id} className="py-3"><div className="flex items-start gap-3"><span aria-hidden="true" className={item.complete ? "text-emerald-300" : "text-amber-200"}>{item.complete ? "✓" : "!"}</span><div><p className="text-sm font-medium text-white">{item.label} · {item.complete ? "Ready" : "Needs attention"}</p><p className="mt-1 text-xs leading-5 text-indigo-100/45">{item.detail}</p>{guidance && <details className="mt-2 text-xs text-indigo-200"><summary className="cursor-pointer">How to fix this in Telegram</summary><p className="mt-2 max-w-2xl leading-5 text-indigo-100/50">{guidance}</p></details>}</div></div></div>; })}</div></Card><Card title="Presets" subtitle="Apply a built-in protection preset to this group."><div className="flex flex-wrap gap-2">{Object.entries(detail.presets || {}).map(([name, preset]) => <button key={name} disabled={saving} onClick={() => void sendAction({ action: "preset", preset: name })} className="action-button">{preset.label || prettify(name)}</button>)}</div></Card></>}
            {tab === "safety" && <>
              <Card title="Protection switches" subtitle="Every setting is written to this group only. The server rechecks your rights and revision."><div className="grid gap-2 sm:grid-cols-2">{Object.entries(detail.settings).filter(([, value]) => typeof value === "boolean").map(([key, value]) => <label key={key} className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[.025] p-3"><span className="text-sm text-indigo-50/80">{prettify(key)}</span><input type="checkbox" checked={Boolean(value)} disabled={saving} onChange={(event) => void sendAction({ action: "settings", settings: { [key]: event.target.checked } })} className="h-4 w-4 accent-indigo-400"/></label>)}</div></Card>
              <Card title="Group rules" subtitle="Update the rules shown by Videl in this group."><textarea value={ruleText} onChange={(event) => setRuleText(event.target.value)} maxLength={2000} rows={4} aria-label="Group rules" className="ios-input w-full resize-y text-sm" placeholder="Write group rules…"/><button disabled={saving} onClick={() => void sendAction({ action: "rules", text: ruleText })} className="action-button mt-3"><Check size={15}/> Save rules</button></Card>
              <div className="grid gap-4 xl:grid-cols-2"><GreetingCard title="Welcome message" value={welcomeText} enabled={Boolean(detail.settings.welcome_enabled)} disabled={saving} onText={setWelcomeText} onSave={(enabled) => void sendAction({ action: "welcome", text: welcomeText, enabled })}/><GreetingCard title="Goodbye message" value={goodbyeText} enabled={Boolean(detail.settings.goodbye_enabled)} disabled={saving} onText={setGoodbyeText} onSave={(enabled) => void sendAction({ action: "goodbye", text: goodbyeText, enabled })}/></div>
              <Card title="Quiet hours" subtitle="Schedule calmer group notifications using a fixed UTC offset."><div className="flex flex-wrap items-end gap-3"><label className="text-xs text-indigo-100/50">Start<input type="time" value={quietStart} className="ios-input mt-1 block" onChange={(event) => void sendAction({ action: "automation", quiet_hours: { start: event.target.value, end: quietEnd, enabled: Boolean(quiet.enabled), tz_offset: Number(quiet.tz_offset || 0) } })}/></label><label className="text-xs text-indigo-100/50">End<input type="time" value={quietEnd} className="ios-input mt-1 block" onChange={(event) => void sendAction({ action: "automation", quiet_hours: { start: quietStart, end: event.target.value, enabled: Boolean(quiet.enabled), tz_offset: Number(quiet.tz_offset || 0) } })}/></label><label className="text-xs text-indigo-100/50">UTC offset (minutes)<input type="number" min={-840} max={840} step={15} defaultValue={Number(quiet.tz_offset || 0)} className="ios-input mt-1 block w-36" onBlur={(event) => void sendAction({ action: "automation", quiet_hours: { enabled: Boolean(quiet.enabled), start: quietStart, end: quietEnd, tz_offset: Number(event.target.value || 0) } })}/></label><label className="flex items-center gap-2 pb-3 text-sm text-indigo-50/75"><input type="checkbox" checked={Boolean(quiet.enabled)} disabled={saving} onChange={(event) => void sendAction({ action: "automation", quiet_hours: { enabled: event.target.checked, start: quietStart, end: quietEnd, tz_offset: Number(quiet.tz_offset || 0) } })} className="accent-indigo-400"/> Enabled</label></div></Card>
              <Card title="Warning escalation ladder" subtitle="Choose the sequence applied at each warning threshold, with optional admin review before severe actions."><EscalationSettings value={detail.automation?.escalation} disabled={saving} onChange={(patch) => void sendAction({ action: "automation", escalation: patch })}/></Card>
            </>}
            {tab === "community" && <>
              <Card title="Warnings" subtitle="Set this group’s warning limit and review current member totals."><div className="flex flex-wrap items-end gap-3"><label className="text-xs text-indigo-100/50">Warnings before escalation<input type="number" min={1} max={10} value={warnLimit} onChange={(event) => setWarnLimit(event.target.value)} className="ios-input mt-1 block w-40"/></label><button disabled={saving} onClick={() => void sendAction({ action: "warn_limit", limit: Number(warnLimit) })} className="action-button">Save limit</button></div><div className="mt-3 divide-y divide-white/5">{(detail.community?.warns || []).map((warn) => <div key={warn.user_id} className="flex items-center justify-between py-2 text-sm text-indigo-100/70"><span>User {warn.user_id} · {warn.count || 0} warning(s)</span><button disabled={saving} onClick={() => void sendAction({ action: "warn_reset", user_id: warn.user_id })} className="text-xs text-rose-200">Reset</button></div>)}</div></Card>
              <div className="grid gap-4 xl:grid-cols-2"><Card title="Saved notes" subtitle="Create simple text notes or remove existing group notes."><form onSubmit={(event) => { event.preventDefault(); void sendAction({ action: "note_create", name: noteName, text: noteText }); setNoteText(""); }} className="space-y-2"><input required pattern="[A-Za-z0-9_]{1,32}" value={noteName} onChange={(event) => setNoteName(event.target.value)} aria-label="Saved note name" className="ios-input w-full text-sm" placeholder="Note name (letters, numbers, _)"/><textarea required maxLength={2000} value={noteText} onChange={(event) => setNoteText(event.target.value)} aria-label="Saved note text" className="ios-input w-full text-sm" rows={3} placeholder="Note text"/><button disabled={saving} className="action-button"><Check size={14}/> Save note</button></form><div className="mt-3 divide-y divide-white/5">{(detail.community?.notes || []).map((note) => <div key={note.name} className="flex items-center justify-between py-2 text-sm text-indigo-100/70"><span>#{note.name} · {note.type}</span><button disabled={saving} onClick={() => void sendAction({ action: "note_delete", name: note.name })} className="text-xs text-rose-200">Delete</button></div>)}</div></Card>
                <Card title="Automatic filters" subtitle="Add or remove a keyword and its simple text reply."><form onSubmit={(event) => { event.preventDefault(); void sendAction({ action: "filter_create", keyword: filterKeyword, reply: filterReply }); setFilterReply(""); }} className="space-y-2"><input required maxLength={64} value={filterKeyword} onChange={(event) => setFilterKeyword(event.target.value)} aria-label="Automatic filter keyword" className="ios-input w-full text-sm" placeholder="Keyword"/><textarea required maxLength={400} value={filterReply} onChange={(event) => setFilterReply(event.target.value)} aria-label="Automatic filter reply" className="ios-input w-full text-sm" rows={3} placeholder="Automatic reply"/><button disabled={saving} className="action-button"><Check size={14}/> Save filter</button></form><div className="mt-3 divide-y divide-white/5">{(detail.community?.filters || []).map((filter) => <div key={filter.keyword} className="flex items-center justify-between gap-2 py-2 text-sm text-indigo-100/70"><span className="min-w-0 truncate">{filter.keyword} · {filter.reply}</span><button disabled={saving} onClick={() => void sendAction({ action: "filter_delete", keyword: filter.keyword })} className="text-xs text-rose-200">Delete</button></div>)}</div></Card></div>
              <Card title="Word blacklist & approvals" subtitle="Manage group-specific triggers, how to handle matches, and approved-member exceptions."><label className="mb-3 block max-w-xs text-xs text-indigo-100/50">Blacklist action<select value={String(detail.settings.blacklist_mode || "del")} disabled={saving} onChange={(event) => void sendAction({ action: "blacklist_mode", mode: event.target.value })} className="ios-input mt-1 block w-full"><option value="off">Off</option><option value="del">Delete message</option><option value="warn">Warn member</option><option value="mute">Mute member</option><option value="kick">Kick member</option><option value="ban">Ban member</option></select></label><form onSubmit={(event) => { event.preventDefault(); void sendAction({ action: "blacklist_add", trigger: blacklistTerm, mode: "del" }); setBlacklistTerm(""); }} className="mb-3 flex gap-2"><input required maxLength={64} value={blacklistTerm} onChange={(event) => setBlacklistTerm(event.target.value)} aria-label="Word or phrase to block" className="ios-input min-w-0 flex-1 text-sm" placeholder="Word or phrase to block"/><button disabled={saving} className="action-button">Add</button></form><div className="grid gap-4 sm:grid-cols-2"><div>{(detail.community?.blacklist || []).map((row) => <div key={row.trigger} className="flex items-center justify-between border-t border-white/5 py-2 text-sm text-indigo-100/70"><span>{row.trigger} · {row.mode}</span><button disabled={saving} onClick={() => void sendAction({ action: "blacklist_remove", trigger: row.trigger })} className="text-xs text-rose-200">Remove</button></div>)}</div><div>{(detail.community?.approved || []).map((id) => <div key={id} className="flex items-center justify-between border-t border-white/5 py-2 text-sm text-indigo-100/70"><span>Approved user {id}</span><button disabled={saving} onClick={() => void sendAction({ action: "approved_remove", user_id: id })} className="text-xs text-rose-200">Remove</button></div>)}</div></div></Card>
            </>}
            {tab === "members" && <> <Card title="Group admins" subtitle="Telegram permits bots to list administrators, not all group members.">{detail.members_available === false ? <p className="text-sm text-amber-100/60">Telegram could not return the admin list. Refresh and check that Videl is in the group.</p> : <div className="divide-y divide-white/5">{(detail.members || []).map((member) => <div key={member.user_id} className="flex items-center justify-between gap-3 py-3"><div><p className="text-sm text-white">{member.name || `User ${member.user_id}`} {member.username ? <span className="text-indigo-100/40">@{member.username}</span> : null}</p><p className="text-xs text-indigo-100/35">{member.status} · ID {member.user_id}</p></div><Shield size={15} className="text-indigo-300"/></div>)}</div>}</Card><Card title="Moderate by Telegram ID" subtitle="The bot checks the target’s current status and your live restriction permission. Admins and the owner are protected."><form onSubmit={(event) => event.preventDefault()} className="grid gap-3 sm:grid-cols-[1fr_140px_1fr] sm:items-end"><label className="text-xs text-indigo-100/50">Member user ID<input value={memberId} onChange={(event) => setMemberId(event.target.value)} inputMode="numeric" required className="ios-input mt-1 w-full text-sm" placeholder="e.g. 123456789"/></label><label className="text-xs text-indigo-100/50">Mute minutes<input value={muteMinutes} onChange={(event) => setMuteMinutes(event.target.value)} type="number" min={1} max={10080} className="ios-input mt-1 w-full text-sm"/></label><div className="flex flex-wrap gap-2">{["mute", "unmute", "kick", "ban"].map((verb) => <button key={verb} type="button" disabled={!canRestrict || saving || !memberId} onClick={() => { if ((verb === "kick" || verb === "ban") && !window.confirm(`${verb === "kick" ? "Kick" : "Ban"} Telegram user ${memberId} from ${detail.chat.title}?`)) return; void sendAction({ action: "member_action", verb, user_id: memberId, minutes: Number(muteMinutes) }); }} className={`action-button ${verb === "ban" ? "!text-rose-200" : ""}`}>{prettify(verb)}</button>)}</div></form>{!canRestrict && <p className="mt-3 text-xs text-amber-200/70">Moderation is disabled until both you and Videl have “Restrict members” permission.</p>}</Card></>}
            {tab === "inbox" && <><Card title="Join requests" subtitle="Review pending requests. Telegram invite rights are required.">{(detail.inbox?.join_requests || []).length ? detail.inbox!.join_requests!.map((item) => <div key={item.user_id} className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3"><div className="text-sm text-white">{item.name || `User ${item.user_id}`} <span className="text-indigo-100/40">{item.username ? `@${item.username}` : `· ${item.user_id}`}</span></div><div className="flex gap-2"><button disabled={!canInvite || saving} onClick={() => { if (window.confirm(`Approve join request from ${item.name || `user ${item.user_id}`} in ${detail.chat.title}?`)) void sendAction({ action: "join_request", decision: "approve", user_id: item.user_id }); }} className="action-button"><Check size={14}/> Approve</button><button disabled={!canInvite || saving} onClick={() => { if (window.confirm(`Decline join request from ${item.name || `user ${item.user_id}`} in ${detail.chat.title}?`)) void sendAction({ action: "join_request", decision: "decline", user_id: item.user_id }); }} className="action-button !text-rose-200"><X size={14}/> Decline</button></div></div>) : <Empty>No pending join requests.</Empty>}</Card><Card title="Member reports" subtitle="Resolve reports with a ban or the group’s configured warning ladder.">{(detail.inbox?.reports || []).length ? detail.inbox!.reports!.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3"><p className="max-w-xl text-sm text-indigo-50/75">{item.text || "Reported message"}<span className="block text-xs text-indigo-100/35">Reported member ID {item.target}</span></p><div className="flex gap-2"><button disabled={saving} onClick={() => { if (window.confirm(`Issue a warning for reported member ${item.target ?? "unknown"} in ${detail.chat.title}?`)) void sendAction({ action: "report_update", id: item.id, decision: "warn" }); }} className="action-button">Warn</button><button disabled={!canRestrict || saving} onClick={() => { if (window.confirm(`Ban reported member ${item.target ?? "unknown"} from ${detail.chat.title}? This removes them from the group.`)) void sendAction({ action: "report_update", id: item.id, decision: "ban" }); }} className="action-button !text-rose-200">Ban</button></div></div>) : <Empty>No open reports.</Empty>}</Card></>}
            {tab === "cases" && <Card title="Member case timelines" subtitle="Reports, warning history, moderator actions and private admin notes are grouped under each member."><CaseTimeline cases={detail.cases || []} disabled={saving} onAddNote={(userId, text) => sendAction({ action: "case_note", user_id: userId, text })} onReviewEscalation={(id, decision) => sendAction({ action: "escalation_review", id, decision })}/></Card>}
            {tab === "commands" && <Card title="Group commands" subtitle="Toggle the registered bot commands for this group. Owner-only commands are excluded and the backend checks each name against the runtime registry."><label className="mb-3 flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2"><Search size={14} className="text-indigo-100/35"/><input value={commandQuery} onChange={(event) => setCommandQuery(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none" placeholder="Filter commands" aria-label="Filter group commands"/></label><div className="max-h-[540px] divide-y divide-white/5 overflow-auto">{BOT_COMMANDS.filter((command) => !command.owner && command.context !== "private" && command.name.includes(commandQuery.trim().replace(/^\//, "").toLowerCase())).map((command) => { const disabled = (detail.community?.disabled_commands || []).includes(command.name); return <div key={command.name} className="flex items-center justify-between gap-3 py-2.5"><div className="min-w-0"><code className="text-sm text-indigo-50">/{command.name}</code><p className="truncate text-xs text-indigo-100/40">{command.summary}</p></div><button disabled={saving} onClick={() => void sendAction({ action: disabled ? "command_enable" : "command_disable", command: command.name })} className={`shrink-0 text-xs ${disabled ? "text-emerald-200" : "text-indigo-200"}`}>{disabled ? "Enable" : "Disable"}</button></div>; })}</div></Card>}
            {tab === "activity" && <Card title="Group activity" subtitle="Filter this group’s bounded audit history. Exports contain at most 40 rows and omit actor identifiers."><form onSubmit={(event) => { event.preventDefault(); setAuditFilter({ kind: auditKind, query: auditQuery, actor: auditActor, from: auditFrom, through: auditThrough }); }} className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3"><label className="text-xs text-indigo-100/50">Category<select value={auditKind} onChange={(event) => setAuditKind(event.target.value)} className="ios-input mt-1 w-full text-sm"><option value="">All categories</option>{["settings", "preset", "warn_limit", "welcome", "goodbye", "rules", "blacklist", "note", "filter", "approval", "warn", "warn_reset", "escalation", "moderation", "invite", "automation", "commands", "join_request", "report", "backup"].map((kind) => <option key={kind} value={kind}>{prettify(kind)}</option>)}</select></label><label className="text-xs text-indigo-100/50">Search action or summary<input value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} maxLength={60} className="ios-input mt-1 w-full text-sm" placeholder="e.g. protection"/></label><label className="text-xs text-indigo-100/50">Actor Telegram ID (optional)<input value={auditActor} onChange={(event) => setAuditActor(event.target.value.replace(/[^0-9]/g, "").slice(0, 20))} inputMode="numeric" className="ios-input mt-1 w-full text-sm" placeholder="Filter by admin"/></label><label className="text-xs text-indigo-100/50">From (UTC)<input type="date" value={auditFrom} max={auditThrough || undefined} onChange={(event) => setAuditFrom(event.target.value)} className="ios-input mt-1 w-full text-sm"/></label><label className="text-xs text-indigo-100/50">Through (UTC)<input type="date" value={auditThrough} min={auditFrom || undefined} onChange={(event) => setAuditThrough(event.target.value)} className="ios-input mt-1 w-full text-sm"/></label><div className="flex items-end gap-2"><button type="submit" disabled={auditLoading} className="action-button"><Search size={14}/> Apply filters</button><button type="button" disabled={!audit.length} onClick={() => { const url = URL.createObjectURL(new Blob([auditCsv(audit)], { type: "text/csv;charset=utf-8" })); const link = document.createElement("a"); link.href = url; link.download = "group-audit.csv"; link.click(); URL.revokeObjectURL(url); }} className="action-button"><Download size={14}/> Export CSV</button></div></form>{auditLoading ? <p role="status" className="text-sm text-indigo-100/50">Loading filtered activity…</p> : audit.length ? <div className="divide-y divide-white/5">{audit.map((event, index) => <div key={String(event.id || index)} className="py-3"><div className="flex flex-wrap justify-between gap-2"><p className="text-sm font-medium text-white">{prettify(String(event.action || event.kind || "Update"))}</p><time className="text-xs text-indigo-100/35">{String(event.at || event.created_at || "")}</time></div><p className="mt-1 text-xs text-indigo-100/45">{String(event.detail || "Group management change")}</p></div>)}</div> : <Empty>No matching recorded changes in the current page.</Empty>}<p className="mt-3 text-[11px] text-indigo-100/35">Showing at most 40 newest matching events. Member message contents are not part of this history.</p></Card>}
          </div>
        </>}
      </section>
    </div>
  </main>;
}

function Card({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <section className="rounded-2xl border border-white/[.07] bg-white/[.02] p-4 sm:p-5"><h3 className="font-semibold text-white">{title}</h3><p className="mb-4 mt-1 text-xs leading-5 text-indigo-100/45">{subtitle}</p>{children}</section>; }
function GreetingCard({ title, value, enabled, disabled, onText, onSave }: { title: string; value: string; enabled: boolean; disabled: boolean; onText: (value: string) => void; onSave: (enabled: boolean) => void }) { return <Card title={title} subtitle="Set the group’s greeting text and switch it on or off."><textarea value={value} onChange={(event) => onText(event.target.value)} maxLength={1000} rows={3} aria-label={`${title} text`} className="ios-input w-full resize-y text-sm" placeholder="Use {name}, {id}, {title} or {mention} for member details."/><div className="mt-3 flex flex-wrap items-center justify-between gap-3"><label className="flex items-center gap-2 text-sm text-indigo-50/70"><input type="checkbox" checked={enabled} disabled={disabled} onChange={(event) => onSave(event.target.checked)} className="accent-indigo-400"/> Enabled</label><button disabled={disabled} onClick={() => onSave(enabled)} className="action-button"><Check size={14}/> Save text</button></div></Card>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/5 bg-white/[.025] p-4"><p className="text-xs text-indigo-100/40">{label}</p><p className="mt-1 text-lg font-semibold text-white">{value}</p></div>; }
function Empty({ children }: { children: React.ReactNode }) { return <p className="rounded-xl border border-dashed border-white/10 p-5 text-center text-sm text-indigo-100/40">{children}</p>; }
