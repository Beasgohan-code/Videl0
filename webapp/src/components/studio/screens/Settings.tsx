"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BotControls } from "@/components/BotControls";
import { BackendStatusChip } from "@/components/studio/BackendStatus";
import { AlertTriangle, ArrowUpRight, Database, Download, GitCompare, Globe2, RefreshCw, ShieldCheck, Settings2 } from "lucide-react";
import { driftLabel, type ReleaseCheck } from "@/lib/release";
import { healthCaption, healthProblems, latencyCaption } from "@/lib/health";
import { Callout, PageHeader, Skeleton } from "../ui";

function ReleasePanel(){
 const [check,setCheck]=useState<ReleaseCheck|null>(null);const [loading,setLoading]=useState(true);const [note,setNote]=useState("");
 const read=useCallback(async()=>{setLoading(true);setNote("");try{const response=await fetch("/api/version",{cache:"no-store"});const data=await response.json().catch(()=>({}));if(!response.ok||!data.hint)throw new Error(data.error||"Version check unavailable");setCheck(data as ReleaseCheck)}catch(e){setCheck(null);setNote(e instanceof Error?e.message:"Version check unavailable")}finally{setLoading(false)}},[]);
 useEffect(()=>{void read()},[read]);
 const tone=check?.drift==="different"?"text-amber-200":check?.drift==="same"?"text-[#30D158]":"text-[var(--ios-label-secondary)]";
 return <section className="mt-4 ios-card p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-400/10 text-emerald-200"><GitCompare size={19} aria-hidden /></span><div><h2 className="font-semibold">Release check</h2><p className="ios-caption">Panel commit vs bot backend commit</p></div></div><button onClick={()=>void read()} disabled={loading} className="ios-btn ios-btn-glass text-xs"><RefreshCw size={14} className={loading?"animate-spin":""} aria-hidden /> Check now</button></div>
 <div className="mt-4 grid gap-3 sm:grid-cols-3">{[{label:"Web panel",value:check?.web},{label:"Bot backend",value:check?.backend}].map((item)=><div key={item.label} className="rounded-xl bg-white/[0.035] p-4"><div className="ios-caption">{item.label}</div>{item.value?<div className="mono mt-1 text-sm">{item.value}</div>:loading?<Skeleton className="mt-2 h-4 w-20"/>:<div className="mt-1 text-sm text-[var(--ios-label-tertiary)]">—</div>}</div>)}<div className="rounded-xl bg-white/[0.035] p-4"><div className="ios-caption">Verdict</div><div className={`mt-1 text-sm font-medium ${tone}`}>{check?driftLabel(check):loading?"Checking…":"Unavailable"}</div></div></div>
 {check&&(check.latencyMs!=null||check.p95Ms!=null)&&<p className="mt-3 ios-caption">Backend answered /health in {check.latencyMs!=null?`${check.latencyMs} ms`:"unknown"} {check.p95Ms!=null?`· internal API p95 ${check.p95Ms} ms`:""} · checked {new Date(check.checkedAt).toLocaleTimeString()}</p>}
 {check&&<p role="status" className="mt-2 text-xs text-[var(--ios-label-secondary)]">{check.hint}</p>}
 {note&&<Callout tone="warn" className="mt-3 text-xs">{note}</Callout>}
 <p className="mt-3 ios-caption">A drift badge means one deployment is behind. Redeploy that service; the panel never guesses which one from a version string alone.</p>
 </section>;
}

type Stats = { ok?: boolean; database?: string; services?: Record<string, boolean>; users?: number; chats?: number; plays?: number; uptime?: number; error?: string; stats?: { database?: string; services?: Record<string, boolean>; users?: number; chats?: number; plays?: number; uptime?: number } };
type Health = { ok?: boolean; status?: string; bot_status?: string; database?: string; service?: string; uptime?: number; error?: string; hint?: string; code?: string; degraded?: boolean; degraded_reasons?: string[]; bot_error?: string | null; bot_online_at?: number | null; bot_attempts?: number | null; assistant?: { configured?: boolean; ready?: boolean; state?: string }; db?: { p95_ms?: number | null; samples?: number; connected?: boolean; last_ms?: number } | null };
const serviceLabels: Record<string,string> = { bot_token:"Telegram bot", user_session:"User session", mongo:"MongoDB", music_api:"Eldian music API", logger_channel:"Log channel" };
export default function SettingsPage(){
 const [stats,setStats]=useState<Stats|null>(null);const [health,setHealth]=useState<Health|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(true);const [reportNote,setReportNote]=useState("");
 // Both cards load independently: a sleeping Render instance must not blank
 // the whole panel or throw a raw "backend error" at the owner.
 const load=useCallback(async()=>{setLoading(true);setError("");const healthPromise=fetch("/api/health",{cache:"no-store"}).then(async r=>({ok:r.ok,...(await r.json().catch(()=>({})))} as Health)).catch(()=>null);const statsPromise=fetch("/api/stats",{cache:"no-store"}).then(async r=>({ok:r.ok,...(await r.json().catch(()=>({})))} as Stats)).catch(()=>null);const [s,h]=await Promise.all([statsPromise,healthPromise]);setStats(s?.stats||null);setHealth(h?{...h,ok:Boolean(h.ok)}:null);const notes:string[]=[];if(!s?.ok)notes.push(s?.error||"Live stats are unavailable right now.");if(h&&!h.ok)notes.push(h.code==="BACKEND_WAKING"?"The Render backend is waking up - a cold start takes up to a minute.":h.hint||h.error||"The Render backend is not responding.");setError(notes.join(" "));setLoading(false);},[]);
 useEffect(()=>{void load();},[load]);
 const downloadDiagnostics=()=>{
  const report={
   schema:"videl-diagnostic-report/v1",
   generated_at:new Date().toISOString(),
   note:"Health and service readiness only. No tokens, session strings, group IDs, usernames, or message contents are included.",
   checks:{
    backend_reachable:Boolean(health?.ok),
    backend_status:health?.status||"unknown",
    bot_status:health?.bot_status||"unknown",
    database_status:stats?.database||health?.database||"unknown",
    degraded:Boolean(health?.degraded),
    assistant:{configured:Boolean(health?.assistant?.configured??stats?.services?.user_session),ready:Boolean(health?.assistant?.ready),state:health?.assistant?.state||"unknown"},
    database_latency:health?.db?{connected:Boolean(health.db.connected),last_ms:health.db.last_ms??null,p95_ms:health.db.p95_ms??null,samples:health.db.samples??0}:null,
    services:Object.fromEntries(Object.entries(serviceLabels).map(([key,label])=>[label,Boolean(stats?.services?.[key])])),
    aggregate_counts:stats?{users:stats.users??null,chats:stats.chats??null,plays:stats.plays??null}:null,
   },
  };
  const blob=new Blob([JSON.stringify(report,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=`videl-diagnostics-${new Date().toISOString().slice(0,10)}.json`;link.click();URL.revokeObjectURL(url);setReportNote("Diagnostic report downloaded. It contains service status only, not secrets or group/member data.");
 };
 return <main className="ios-page ios-page-narrow">
  <PageHeader
    eyebrow="Videl · Configuration"
    title="Settings & services"
    subtitle="Live configuration and health checks. Secrets are never displayed in the browser."
    actions={<button onClick={()=>void load()} disabled={loading} className="ios-btn ios-btn-glass text-sm"><RefreshCw size={16} className={loading?"animate-spin":""} aria-hidden /> Refresh</button>}
  />
  {error&&<Callout tone="warn" className="mt-4" title="Some checks did not answer" icon={<AlertTriangle size={18} aria-hidden />}>{error}</Callout>}
  <BotControls />
  <section className="mt-6 grid gap-4 lg:grid-cols-2">
   <div className="ios-card p-5"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-400/10 text-blue-200"><Database size={19} aria-hidden /></span><div><h2 className="font-semibold">Database</h2><p className="ios-caption">Live backend connection</p></div></div><div className="mt-5 flex items-center justify-between rounded-xl bg-white/[0.035] p-4"><span className="text-sm">MongoDB</span><span className={`ios-pill ${stats?.database==="connected"?"ios-pill-green":""}`}>{stats?.database||"Unavailable"}</span></div><p className="mt-3 ios-caption">Videl reads and writes application data to MongoDB. This panel does not expose database URLs or credentials.</p></div>
   <div className="ios-card p-5"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-purple-400/10 text-purple-200"><ShieldCheck size={19} aria-hidden /></span><div><h2 className="font-semibold">Connected services</h2><p className="ios-caption">Configuration and live-session readiness</p></div></div><div className="mt-4 divide-y divide-white/[0.07]">{Object.entries(serviceLabels).map(([key,label])=>{const isUserSession=key==="user_session";const configured=isUserSession?Boolean(health?.assistant?.configured??stats?.services?.[key]):Boolean(stats?.services?.[key]);const ready=isUserSession?health?.assistant?.ready:configured;const status=!stats&&!health?"—":isUserSession?(ready?"Connected":configured?`Configured · ${health?.assistant?.state||"status unavailable"}`:"Not configured"):(configured?"Configured":"Not configured");const good=isUserSession?Boolean(ready):configured;return <div key={key} className="flex items-center justify-between gap-3 py-3"><span className="text-sm">{label}</span><span className={`text-xs ${good?"text-[#30D158]":configured?"text-amber-200/80":"text-[var(--ios-label-tertiary)]"}`}><span aria-hidden>{good?"● ":"○ "}</span>{status}</span></div>})}</div>{health?.assistant?.configured&&!health?.assistant?.ready&&<p className="mt-3 rounded-xl border border-amber-300/15 bg-amber-300/[0.06] p-3 text-xs text-amber-100/85">The session secret is configured, but Telegram has not started the assistant client. Check the backend startup logs and confirm <code>STRING_SESSION</code> is current. Never share the session string in chat.</p>}</div>
  </section>
  <section className="mt-4 ios-card p-5"><div className="flex items-center gap-3"><Globe2 size={19} aria-hidden /><div><h2 className="font-semibold">Deployment status</h2><p className="ios-caption">Frontend on Vercel · bot/API backend on Render</p></div></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-white/[0.035] p-4"><div className="text-sm font-medium">Web control panel</div><div className="mt-2 text-xs text-[var(--ios-label-secondary)]">Vercel deployment status is managed in your Vercel project settings.</div></div><div className="rounded-xl bg-white/[0.035] p-4"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">Videl bot backend</span><BackendStatusChip health={health}/></div><div className="mt-2 text-xs text-[var(--ios-label-secondary)]">{healthCaption(health)}</div>
                {health?.ok && latencyCaption(health) && (
                  <div className="mt-1 text-xs text-[var(--ios-label-secondary)]">{latencyCaption(health)}</div>
                )}
                {health?.ok && (health.bot_attempts ?? 1) > 1 && (
                  <div className="mt-1 text-xs text-amber-200/80">Started after {health.bot_attempts} attempts.</div>
                )}</div></div>{health?.ok && healthProblems(health).length > 0 && (
   <Callout tone="warn" className="mt-4 text-xs" title="The panel works, but the bot is not fully running">
     <ul className="mt-2 list-disc space-y-1 pl-5">
       {healthProblems(health).map((reason) => <li key={reason}>{reason}</li>)}
     </ul>
     {health.bot_error && <p className="mt-2 break-words font-mono text-[11px] opacity-80">Last start error: {health.bot_error}</p>}
     <p className="mt-2 opacity-80">Open the Render service logs for the full trace. The token is never shown here.</p>
   </Callout>
 )}
 <p className="mt-4 flex items-start gap-2 ios-caption"><Settings2 size={14} className="mt-0.5 shrink-0"/>Set secrets in Render or Vercel environment settings as appropriate. Never paste bot tokens into the UI.</p></section>
  <ReleasePanel />
  <section className="mt-4 ios-card flex flex-wrap items-center justify-between gap-4 p-5"><div><h2 className="font-semibold">One-click diagnostics</h2><p className="mt-1 ios-caption">Download a shareable JSON health report. Secrets and group/member data are excluded.</p>{reportNote&&<p role="status" className="mt-2 text-xs text-[#30D158]">{reportNote}</p>}</div><button onClick={downloadDiagnostics} disabled={loading} className="ios-btn ios-btn-primary text-sm disabled:opacity-40"><Download size={15} aria-hidden /> Download report</button></section>
  <div className="mt-5 flex flex-wrap gap-2"><Link href="/" className="ios-btn ios-btn-glass text-sm">Control room <ArrowUpRight size={15} aria-hidden /></Link><Link href="/?tab=analytics" className="ios-btn ios-btn-glass text-sm">Analytics <ArrowUpRight size={15} aria-hidden /></Link></div>
 </main>;
}
