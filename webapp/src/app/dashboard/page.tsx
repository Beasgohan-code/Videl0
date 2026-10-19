"use client";
import { useEffect, useState } from "react";
import { Users, MessageSquare, ListMusic, ShieldBan, Settings, Database, Activity, Terminal } from "lucide-react";

export default function Dashboard(){
  const [stats,setStats]=useState<any>(null);
  const [gbans,setGbans]=useState<any[]>([]);
  const [queue,setQueue]=useState<any[]>([]);
  const [tab,setTab]=useState("overview");

  useEffect(()=>{
    fetch("/api/stats").then(r=>r.json()).then(j=> setStats(j.stats || j)).catch(()=>{});
    fetch("/api/gbans").then(r=>r.json()).then(j=> setGbans(j.items || [])).catch(()=>{});
    fetch("/api/queue").then(r=>r.json()).then(j=> setQueue(j.items || [])).catch(()=>{});
  },[]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Videl0 Dashboard</h1>
        <div className="flex gap-2 text-xs">
          <span className="rounded-full bg-emerald-500/20 text-emerald-300 px-3 py-1">Owner</span>
          <span className="rounded-full glass px-3 py-1">Supabase ● Connected</span>
        </div>
      </header>

      <nav className="mt-6 flex gap-2 overflow-auto">
        {[
          ["overview", "Overview"], ["music","Music"], ["ai","AI"], ["moderation","Moderation"], ["ops","Ops & Logs"]
        ].map(([id,label])=>(
          <button key={id} onClick={()=>setTab(id)} className={`rounded-full px-4 py-2 text-sm ${tab===id?"bg-white text-black":"glass"}`}>{label}</button>
        ))}
      </nav>

      {tab==="overview" && (
        <section className="mt-6 grid md:grid-cols-3 gap-4">
          <div className="glass rounded-2xl p-5"><div className="text-zinc-400 text-sm flex gap-2 items-center"><Users size={14}/> Users</div><div className="text-3xl font-bold mt-2">{stats?.users ?? "—"}</div></div>
          <div className="glass rounded-2xl p-5"><div className="text-zinc-400 text-sm flex gap-2 items-center"><MessageSquare size={14}/> Chats</div><div className="text-3xl font-bold mt-2">{stats?.chats ?? "—"}</div></div>
          <div className="glass rounded-2xl p-5"><div className="text-zinc-400 text-sm flex gap-2 items-center"><Activity size={14}/> Commands</div><div className="text-3xl font-bold mt-2">{stats?.commands ?? "—"}</div></div>
          <div className="glass rounded-2xl p-5 md:col-span-3">
            <h3 className="font-semibold">System</h3>
            <div className="mt-3 grid md:grid-cols-4 gap-3 text-sm">
              <div className="bg-zinc-900 rounded-xl p-3">Bot: @Videl0Bot<br/><span className="text-xs text-zinc-500">aiogram 3.31</span></div>
              <div className="bg-zinc-900 rounded-xl p-3">DB: Supabase<br/><span className="text-xs text-zinc-500">hanre-studio • ap-south-1</span></div>
              <div className="bg-zinc-900 rounded-xl p-3">Backup: Dropbox<br/><span className="text-xs text-zinc-500">/Videl0/backups</span></div>
              <div className="bg-zinc-900 rounded-xl p-3">Hosting: Vercel<br/><span className="text-xs text-zinc-500">hosting-bot-dashboard</span></div>
            </div>
          </div>
        </section>
      )}

      {tab==="music" && (
        <section className="mt-6 glass rounded-2xl p-5">
          <h3 className="font-semibold flex gap-2 items-center"><ListMusic size={16}/> Music Queue</h3>
          <div className="mt-4 space-y-2">
            {queue.length? queue.map((q:any,i:number)=>(
              <div key={q.id||i} className="flex justify-between bg-zinc-900 rounded-xl p-3 text-sm"><span>{i+1}. {q.title}</span><span className="text-zinc-500">{q.duration}s • {q.chat_id}</span></div>
            )): <p className="text-sm text-zinc-500">No active queues. Use /play in Telegram.</p>}
          </div>
        </section>
      )}

      {tab==="moderation" && (
        <section className="mt-6 glass rounded-2xl p-5">
          <h3 className="font-semibold flex gap-2 items-center"><ShieldBan size={16}/> Gbans</h3>
          <div className="mt-4 space-y-2">
            {gbans.length? gbans.map((g:any)=>(
              <div key={g.user_id} className="bg-zinc-900 rounded-xl p-3 text-sm flex justify-between"><span><code>{g.user_id}</code> — {g.reason}</span><button className="text-xs text-amber-300">Ungban</button></div>
            )): <p className="text-sm text-zinc-500">No gbans.</p>}
          </div>
        </section>
      )}

      {tab==="ai" && (
        <section className="mt-6 glass rounded-2xl p-5">
          <h3 className="font-semibold">AI Playground</h3>
          <p className="text-sm text-zinc-400 mt-2">Test prompts directly from dashboard (calls same provider as bot).</p>
          <div className="mt-4 flex gap-2">
            <input id="aiq" placeholder="Ask Videl…" className="flex-1 bg-zinc-900 rounded-xl px-4 py-3 text-sm outline-none"/>
            <button onClick={async()=>{
              const el=document.getElementById("aiq") as HTMLInputElement;
              const q=el?.value; if(!q) return;
              const r=await fetch("/api/ai",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:q})}).then(x=>x.json());
              alert(r.answer || r.error);
            }} className="bg-white text-black rounded-xl px-5 font-semibold">Ask</button>
          </div>
        </section>
      )}

      {tab==="ops" && (
        <section className="mt-6 glass rounded-2xl p-5">
          <h3 className="font-semibold flex gap-2 items-center"><Terminal size={16}/> Ops & Logs</h3>
          <div className="mt-3 grid md:grid-cols-2 gap-3 text-sm">
            <div className="bg-zinc-900 rounded-xl p-3">Keep-alive: <span className="text-emerald-400">active (every 300s)</span><br/>Watchdog: <span className="text-emerald-400">active</span><br/>Logs channel: <code>{process.env.NEXT_PUBLIC_LOG_CHANNEL || "-100…"}</code></div>
            <div className="bg-zinc-900 rounded-xl p-3">Dropbox backup: <span className="text-zinc-400">every 6h</span><br/>Vercel cron: enabled<br/>Env: production</div>
          </div>
        </section>
      )}
    </main>
  );
}
