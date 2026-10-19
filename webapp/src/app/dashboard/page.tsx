"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Music2, Bot, Shield, Settings, BarChart3, Radio, MessageCircle } from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [gbans, setGbans] = useState<any[]>([]);
  const [queue, setQueue] = useState<any[]>([]);
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    fetch("/api/stats").then(r => r.json()).then(j => setStats(j.stats || j)).catch(() => {});
    fetch("/api/gbans").then(r => r.json()).then(j => setGbans(j.items || [])).catch(() => {});
    fetch("/api/queue").then(r => r.json()).then(j => setQueue(j.items || [])).catch(() => {});
  }, []);

  return (
    <main className="mx-auto max-w-6xl py-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="ios-title">Dashboard</h1>
          <p className="ios-subheadline">Supabase ⫶ Dropbox ⫶ Vercel ⫶ keep-alive ⫶ watchdog</p>
        </div>
        <div className="hidden sm:flex gap-2">
          <Link href="/dashboard/channel" className="ios-btn ios-btn-primary">⬪ Studio</Link>
          <Link href="/dashboard/chat" className="ios-btn ios-btn-glass">◍ Chat</Link>
          <Link href="/auth" className="ios-btn ios-btn-glass">◎ Login</Link>
        </div>
      </header>

      <div className="mt-6 flex gap-2 overflow-auto pb-2">
        {[
          ["overview", "◍ Overview", BarChart3],
          ["music", "⬪ Music", Music2],
          ["ai", "⦿ AI", Bot],
          ["moderation", "◎ Mods", Shield],
          ["ops", "⬢ Ops", Settings],
        ].map(([id, label, Icon]: any) => (
          <button key={id} onClick={() => setTab(id)} className={`ios-tab ${tab === id ? "active" : ""}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <section className="mt-6 space-y-4 animate-slide">
          <div className="grid md:grid-cols-3 gap-3">
            <div className="ios-card p-5"><div className="ios-caption2">◍ Users</div><div className="text-[28px] font-bold mt-1">{stats?.users ?? "—"}</div><div className="ios-caption">Total registered</div></div>
            <div className="ios-card p-5"><div className="ios-caption2">⫶ Chats</div><div className="text-[28px] font-bold mt-1">{stats?.chats ?? "—"}</div><div className="ios-caption">Groups + channels</div></div>
            <div className="ios-card p-5"><div className="ios-caption2">⬪ Commands</div><div className="text-[28px] font-bold mt-1">{stats?.commands ?? "—"}</div><div className="ios-caption">Ever executed</div></div>
          </div>

          <div className="ios-card p-5">
            <h3 className="ios-caption2">⬪ Quick actions</h3>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
              <Link href="/dashboard/channel" className="ios-card p-4 flex flex-col gap-2 hover:bg-white hover:text-black transition"><Radio size={18} /> <span className="ios-headline text-[14px]">Channel Studio</span><span className="ios-caption">Post with colors & buttons</span></Link>
              <Link href="/dashboard/chat" className="ios-card p-4 flex flex-col gap-2 hover:bg-white hover:text-black transition"><MessageCircle size={18} /> <span className="ios-headline text-[14px]">Web Chat</span><span className="ios-caption">Chat as real user</span></Link>
              <a href="https://t.me/Videl0Bot" target="_blank" className="ios-card p-4"><span className="ios-headline text-[14px]">⬪ Open Bot</span><span className="ios-caption block mt-1">Add to group / PM</span></a>
              <a href="/api/health" target="_blank" className="ios-card p-4"><span className="ios-headline text-[14px]">◎ Health</span><span className="ios-caption block mt-1">/health • /ping</span></a>
            </div>
          </div>

          <div className="ios-card p-5">
            <h3 className="ios-caption2">⬪ System</h3>
            <div className="mt-3 grid md:grid-cols-4 gap-3 ios-caption">
              <div className="ios-card p-3">Bot: @Videl0Bot<br/><span className="text-[var(--ios-label-tertiary)]">aiogram 3.31</span></div>
              <div className="ios-card p-3">DB: Supabase<br/><span className="text-[var(--ios-label-tertiary)]">hanre-studio</span></div>
              <div className="ios-card p-3">Backup: Dropbox<br/><span className="text-[var(--ios-label-tertiary)]">/Videl0/backups</span></div>
              <div className="ios-card p-3">Host: Vercel<br/><span className="text-[var(--ios-label-tertiary)]">hosting-dashboard</span></div>
            </div>
          </div>
        </section>
      )}

      {tab === "music" && (
        <section className="mt-6 ios-card p-5">
          <h3 className="ios-caption2">⬪ Music Queue</h3>
          <div className="mt-4 space-y-2">
            {queue.length ? queue.map((q: any, i: number) => (
              <div key={q.id || i} className="ios-list-row"><span className="text-[13px]">{i + 1}. {q.title}</span><span className="ios-caption">{q.duration}s ⫶ {q.chat_id}</span></div>
            )) : <p className="ios-caption">No active queues — use /play in TG</p>}
          </div>
        </section>
      )}

      {tab === "moderation" && (
        <section className="mt-6 ios-card p-5">
          <h3 className="ios-caption2">◎ Gbans</h3>
          <div className="mt-4 space-y-2">
            {gbans.length ? gbans.map((g: any) => (
              <div key={g.user_id} className="ios-list-row"><span className="text-[13px]"><code>{g.user_id}</code> — {g.reason}</span><span className="text-amber-300">◍</span></div>
            )) : <p className="ios-caption">No gbans</p>}
          </div>
        </section>
      )}

      {tab === "ai" && (
        <section className="mt-6 ios-card p-5">
          <h3 className="ios-caption2">⦿ AI Playground</h3>
          <p className="ios-caption mt-2">Test prompts — same provider as bot (OpenAI→Groq→Gemini)</p>
          <div className="mt-4 flex gap-2">
            <input id="aiq" placeholder="Ask Videl…" className="ios-input flex-1" />
            <button onClick={async () => {
              const el = document.getElementById("aiq") as HTMLInputElement;
              const q = el?.value; if (!q) return;
              const r = await fetch("/api/ai", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt: q }) }).then(x => x.json());
              alert(r.answer || r.error);
            }} className="ios-btn ios-btn-primary">⬪ Ask</button>
          </div>
        </section>
      )}

      {tab === "ops" && (
        <section className="mt-6 ios-card p-5">
          <h3 className="ios-caption2">⬢ Ops & Logs</h3>
          <div className="mt-3 grid md:grid-cols-2 gap-3 ios-caption">
            <div className="ios-card p-3">Keep-alive: <span style={{ color: "#30D158" }}>active (300s)</span><br/>Watchdog: <span style={{ color: "#30D158" }}>active</span><br/>Logs: <code>-100…</code></div>
            <div className="ios-card p-3">Dropbox: <span className="text-zinc-400">every 6h</span><br/>Vercel: enabled<br/>Env: production ⫶ cyber dark</div>
          </div>
        </section>
      )}
    </main>
  );
}
