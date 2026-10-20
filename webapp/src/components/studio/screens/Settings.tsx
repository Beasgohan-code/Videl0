"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BotControls } from "@/components/BotControls";
import { BackendStatusChip } from "@/components/studio/BackendStatus";
import { AlertTriangle, ArrowUpRight, Database, GitCompare, Globe2, RefreshCw, ShieldCheck, Settings2 } from "lucide-react";
import { driftLabel, type ReleaseCheck } from "@/lib/release";

function ReleasePanel(){
 const [check,setCheck]=useState<ReleaseCheck|null>(null);const [loading,setLoading]=useState(true);const [note,setNote]=useState("");
 const read=useCallback(async()=>{setLoading(true);setNote("");try{const response=await fetch("/api/version",{cache:"no-store"});const data=await response.json().catch(()=>({}));if(!response.ok||!data.hint)throw new Error(data.error||"Version check unavailable");setCheck(data as ReleaseCheck)}catch(e){setCheck(null);setNote(e instanceof Error?e.message:"Version check unavailable")}finally{setLoading(false)}},[]);
 useEffect(()=>{void read()},[read]);
 const tone=check?.drift==="different"?"text-amber-200":check?.drift==="same"?"text-[#30D158]":"text-[var(--ios-label-secondary)]";
 return <section className="mt-4 ios-card p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-400/10 text-emerald-200"><GitCompare size={19}/></span><div><h2 className="font-semibold">Release check</h2><p className="ios-caption">Panel commit vs bot backend commit</p></div></div><button onClick={()=>void read()} disabled={loading} className="ios-btn ios-btn-glass text-xs"><RefreshCw size={14} className={loading?"animate-spin":""}/> Check now</button></div>
 <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-white/[0.035] p-4"><div className="ios-caption">Web panel</div><div className="mt-1 font-mono text-sm">{check?.web??"—"}</div></div><div className="rounded-xl bg-white/[0.035] p-4"><div className="ios-caption">Bot backend</div><div className="mt-1 font-mono text-sm">{check?.backend??"—"}</div></div><div className="rounded-xl bg-white/[0.035] p-4"><div className="ios-caption">Verdict</div><div className={`mt-1 text-sm font-medium ${tone}`}>{check?driftLabel(check):loading?"Checking…":"Unavailable"}</div></div></div>
 {check?.latencyMs!=null&&<p className="mt-3 ios-caption">Backend answered /health in {check.latencyMs} ms · checked {new Date(check.checkedAt).toLocaleTimeString()}</p>}
 {check&&<p role="status" className="mt-2 text-xs text-[var(--ios-label-secondary)]">{check.hint}</p>}
 {note&&<p role="status" className="mt-2 text-xs text-amber-200">{note}</p>}
 <p className="mt-3 ios-caption">A drift badge means one deployment is behind. Redeploy that service; the panel never guesses which one from a version string alone.</p>
 </section>;
}

type Stats = { ok?: boolean; database?: string; services?: Record<string, boolean>; stats?: { database?: string; services?: Record<string, boolean> }; error?: string };
type Health = { ok?: boolean; status?: string; bot_status?: string; database?: string; service?: string; uptime?: number; error?: string; hint?: string; code?: string };
const serviceLabels: Record<string,string> = { bot_token:"Telegram bot", user_session:"User session", mongo:"MongoDB", music_api:"Eldian music API", logger_channel:"Log channel" };
export default function SettingsPage(){
 const [stats,setStats]=useState<Stats|null>(null);const [health,setHealth]=useState<Health|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 // Both cards load independently: a sleeping Render instance must not blank
 // the whole panel or throw a raw "backend error" at the owner.
 const load=useCallback(async()=>{setLoading(true);setError("");const healthPromise=fetch("/api/health",{cache:"no-store"}).then(async r=>({ok:r.ok,...(await r.json().catch(()=>({})))} as Health)).catch(()=>null);const statsPromise=fetch("/api/stats",{cache:"no-store"}).then(async r=>({ok:r.ok,...(await r.json().catch(()=>({})))} as Stats)).catch(()=>null);const [s,h]=await Promise.all([statsPromise,healthPromise]);setStats(s?.stats||null);setHealth(h?{...h,ok:Boolean(h.ok)}:null);const notes:string[]=[];if(!s?.ok)notes.push(s?.error||"Live stats are unavailable right now.");if(h&&!h.ok)notes.push(h.code==="BACKEND_WAKING"?"The Render backend is waking up - a cold start takes up to a minute.":h.hint||h.error||"The Render backend is not responding.");setError(notes.join(" "));setLoading(false);},[]);
 useEffect(()=>{void load();},[load]);
 return <main className="mx-auto max-w-5xl py-5 sm:py-8">
  <header className="flex flex-wrap items-center justify-between gap-3"><div><p className="ios-caps text-[11px]">Videl · Configuration</p><h1 className="mt-2 ios-title">Settings & services</h1><p className="mt-1 ios-subheadline">Live configuration and health checks. Secrets are never displayed in the browser.</p></div><button onClick={()=>void load()} disabled={loading} className="ios-btn ios-btn-glass text-sm"><RefreshCw size={16} className={loading?"animate-spin":""}/> Refresh</button></header>
  {error&&<div role="alert" className="mt-4 flex gap-2 rounded-2xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm text-amber-100"><AlertTriangle size={18} className="shrink-0"/>{error}</div>}
  <BotControls />
  <section className="mt-6 grid gap-4 lg:grid-cols-2">
   <div className="ios-card p-5"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-400/10 text-blue-200"><Database size={19}/></span><div><h2 className="font-semibold">Database</h2><p className="ios-caption">Live backend connection</p></div></div><div className="mt-5 flex items-center justify-between rounded-xl bg-white/[0.035] p-4"><span className="text-sm">MongoDB</span><span className={`ios-pill ${stats?.database==="connected"?"ios-pill-green":""}`}>{stats?.database||"Unavailable"}</span></div><p className="mt-3 ios-caption">Videl reads and writes application data to MongoDB. This panel does not expose database URLs or credentials.</p></div>
   <div className="ios-card p-5"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-purple-400/10 text-purple-200"><ShieldCheck size={19}/></span><div><h2 className="font-semibold">Connected services</h2><p className="ios-caption">Configuration presence only</p></div></div><div className="mt-4 divide-y divide-white/[0.07]">{Object.entries(serviceLabels).map(([key,label])=>{const configured=Boolean(stats?.services?.[key]);return <div key={key} className="flex items-center justify-between gap-3 py-3"><span className="text-sm">{label}</span><span className={`text-xs ${configured?"text-[#30D158]":"text-[var(--ios-label-tertiary)]"}`}>{stats?configured?"Configured":"Not configured":"—"}</span></div>})}</div></div>
  </section>
  <section className="mt-4 ios-card p-5"><div className="flex items-center gap-3"><Globe2 size={19}/><div><h2 className="font-semibold">Deployment status</h2><p className="ios-caption">Frontend on Vercel · bot/API backend on Render</p></div></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-white/[0.035] p-4"><div className="text-sm font-medium">Web control panel</div><div className="mt-2 text-xs text-[var(--ios-label-secondary)]">Vercel deployment status is managed in your Vercel project settings.</div></div><div className="rounded-xl bg-white/[0.035] p-4"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">Videl bot backend</span><BackendStatusChip health={health}/></div><div className="mt-2 text-xs text-[var(--ios-label-secondary)]">{health?.ok?`API reachable · bot ${health.bot_status||"status unknown"}${health.database?" · DB "+health.database:""}${typeof health.uptime==="number"?` · uptime ${Math.floor(health.uptime/3600)}h ${Math.floor(health.uptime%3600/60)}m`:""}`:"Health check unavailable"}</div></div></div><p className="mt-4 flex items-start gap-2 ios-caption"><Settings2 size={14} className="mt-0.5 shrink-0"/>Set secrets in Render or Vercel environment settings as appropriate. Never paste bot tokens into the UI.</p></section>
  <ReleasePanel />
  <div className="mt-5 flex flex-wrap gap-2"><Link href="/" className="ios-btn ios-btn-glass text-sm">Control room <ArrowUpRight size={15}/></Link><Link href="/?tab=analytics" className="ios-btn ios-btn-glass text-sm">Analytics <ArrowUpRight size={15}/></Link></div>
 </main>;
}
