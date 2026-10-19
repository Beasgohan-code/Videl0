"use client";
import { useEffect, useState } from "react";
import { Music, Bot, Shield, Users, Activity, Play, Pause, SkipForward, Server, Heart, BarChart3, Zap, MessageSquare, Settings } from "lucide-react";

type Stats = { users:number; chats:number; commands:number };

export default function Home() {
  const [stats, setStats] = useState<Stats>({users:0,chats:0,commands:0});
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(()=> {
    fetch("/api/stats").then(r=>r.json()).then(d=> setStats(d.stats || d)).catch(()=>{});
    fetch("/api/health").then(r=>r.json()).then(setHealth).catch(()=>{});
    setTimeout(()=> setLoading(false), 600);
  },[]);

  const features = [
    { icon: Music, title:"Music", desc:"VC streaming • queue • lyrics • playlists", color:"from-violet-500 to-fuchsia-500" },
    { icon: Bot, title:"AI Chat", desc:"OpenAI / Groq / Gemini • vision • imagine", color:"from-blue-500 to-cyan-500" },
    { icon: Shield, title:"Admin", desc:"ban/mute/warn/lock/purge • GBan • antiflood", color:"from-emerald-500 to-teal-500" },
    { icon: Settings, title:"Utilities", desc:"weather • qr • git • carbon • wiki • tts", color:"from-orange-500 to-amber-500" },
    { icon: Users, title:"Groups", desc:"welcome • filters • notes • rules • reports", color:"from-pink-500 to-rose-500" },
    { icon: Activity, title:"Ops", desc:"keep-alive • watchdog • logs • Dropbox", color:"from-slate-500 to-zinc-500" },
  ];

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center font-bold">V</div>
          <div>
            <h1 className="text-xl font-bold gradient-text">Videl0</h1>
            <p className="text-xs text-zinc-400">Telegram Bot API 10.3 • aiogram 3.31 • Richgram</p>
          </div>
        </div>
        <div className="flex gap-2">
          <a href="https://t.me/Videl0Bot" target="_blank" className="rounded-full bg-white text-black px-4 py-2 text-sm font-semibold">Open in Telegram →</a>
          <a href="/dashboard" className="rounded-full glass px-4 py-2 text-sm">Dashboard</a>
          <a href="/api/health" target="_blank" className="rounded-full glass px-3 py-2 text-sm"><Heart size={16} className={health?.status==="ok"?"text-emerald-400 fill-emerald-400":"text-amber-400"} /></a>
        </div>
      </header>

      {/* Hero */}
      <section className="mt-10 glass rounded-[24px] p-8 md:p-10 overflow-hidden relative">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-violet-500/10 to-fuchsia-500/10" />
        <div className="relative grid md:grid-cols-2 gap-8">
          <div>
            <p className="inline-flex gap-2 items-center rounded-full bg-white/10 px-3 py-1 text-xs text-zinc-300"><span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> Bot is Operational • keep-alive active</p>
            <h2 className="mt-4 text-4xl md:text-5xl font-black leading-tight">Music, AI &<br/><span className="gradient-text">Admin — in One</span></h2>
            <p className="mt-4 text-zinc-400 max-w-lg">Full-stack Telegram bot built by Beasgohan-code. Uses Badmunda05&apos;s Richgram + ShizuMusic core, wired to Supabase, Dropbox & Vercel.</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href="https://t.me/Videl0Bot?startgroup=true" className="rounded-xl bg-white text-black px-5 py-3 font-semibold">➕ Add to Group</a>
              <a href="/dashboard" className="rounded-xl glass px-5 py-3 font-semibold">📊 Open Dashboard</a>
              <a href="https://github.com/Beasgohan-code/Videl0" target="_blank" className="rounded-xl border border-zinc-700 px-5 py-3">GitHub</a>
            </div>
            <div className="mt-6 flex gap-4 text-xs text-zinc-500">
              <span className="flex items-center gap-1"><Server size={12}/> FastAPI keep-alive</span>
              <span className="flex items-center gap-1"><Zap size={12}/> Bot API 10.3 Rich Messages</span>
              <span className="flex items-center gap-1"><BarChart3 size={12}/> Vercel hosted</span>
            </div>
          </div>
          <div className="glass rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold flex gap-2 items-center"><Play size={16}/> Now Playing — Rich UI Demo</h3>
              <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-1 rounded-full">LIVE</span>
            </div>
            <div className="rounded-xl bg-zinc-900 p-4">
              <img src="https://files.catbox.moe/f084wg.png" alt="thumb" className="w-full h-28 object-cover rounded-lg" />
              <h4 className="mt-3 font-semibold">Shizu — High Quality VC Streaming</h4>
              <p className="text-xs text-zinc-400">Duration 3:27 • Requested by @Beasgohan</p>
              <div className="mt-3 h-1 bg-zinc-800 rounded-full overflow-hidden"><div className="h-full w-[42%] bg-gradient-to-r from-blue-500 to-violet-500" /></div>
              <div className="mt-3 grid grid-cols-4 gap-2">
                <button className="rounded-lg bg-zinc-800 py-2 text-xs">Pause</button>
                <button className="rounded-lg bg-zinc-800 py-2 text-xs">Resume</button>
                <button className="rounded-lg bg-zinc-800 py-2 text-xs">Skip</button>
                <button className="rounded-lg bg-red-500/20 text-red-300 py-2 text-xs">Stop</button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              {[["Users", stats.users||"—"],["Chats", stats.chats||"—"],["Uptime","24/7"]].map(([k,v])=>(
                <div key={k} className="rounded-xl bg-zinc-900 p-3"><div className="text-lg font-bold">{v}</div><div className="text-[10px] text-zinc-500">{k}</div></div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mt-8 grid md:grid-cols-3 gap-4">
        {features.map(f=>(
          <div key={f.title} className="glass rounded-2xl p-5">
            <div className={`h-10 w-10 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center`}><f.icon size={18} className="text-white"/></div>
            <h3 className="mt-3 font-semibold">{f.title}</h3>
            <p className="text-sm text-zinc-400 mt-1">{f.desc}</p>
          </div>
        ))}
      </section>

      {/* Stats */}
      <section className="mt-8 glass rounded-2xl p-6">
        <h3 className="font-semibold flex gap-2 items-center"><BarChart3 size={18}/> Live Stats</h3>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            ["Total Users", stats.users ?? "—"],
            ["Active Chats", stats.chats ?? "—"],
            ["Commands Served", stats.commands ?? "—"],
            ["Bot Status", health?.status==="ok" ? "Healthy" : "Checking…"],
          ].map(([k,v])=>(
            <div key={k} className="rounded-xl bg-zinc-900 p-4"><div className="text-2xl font-bold gradient-text">{loading?"…":v}</div><div className="text-xs text-zinc-500 mt-1">{k}</div></div>
          ))}
        </div>
        <p className="text-xs text-zinc-600 mt-4">Data from Supabase • Backup to Dropbox • Hosted on Vercel • Watchdog active</p>
      </section>

      {/* Commands */}
      <section className="mt-8 glass rounded-2xl p-6">
        <h3 className="font-semibold">📚 Commands</h3>
        <div className="mt-4 grid md:grid-cols-2 gap-4 text-sm">
          {Object.entries({
            "🎵 Music": "/play /vplay /queue /skip /stop /pause /lyrics /playlist /thumbnail /autoplay",
            "🤖 AI": "/ask /gpt /imagine /summarize /translate /tts /vision",
            "🛡️ Admin": "/ban /kick /mute /warn /pin /purge /lock /slowmode",
            "👑 Owner": "/broadcast /gban /addsudo /backup /eval /logs",
            "🧰 Utility": "/weather /qr /shorten /calc /wiki /git /carbon /afk /tagall",
            "👥 Group": "/welcome /filter /note /rules /report /staff /setlang",
          }).map(([k,v])=>(
            <div key={k} className="rounded-xl bg-zinc-900 p-4"><div className="font-semibold text-zinc-200">{k}</div><div className="text-zinc-500 text-xs mt-1 font-mono">{v}</div></div>
          ))}
        </div>
      </section>

      <footer className="mt-10 text-center text-xs text-zinc-600 pb-8">
        <p>Made with ❤️ by <a href="https://github.com/Beasgohan-code" className="text-zinc-400">Beasgohan-code</a> • Richgram by <a href="https://github.com/Badmunda05/richgram" className="text-zinc-400">Badmunda05</a> • ShizuMusic • © 2026 Videl0</p>
        <p className="mt-1">Vercel: hosting-bot-dashboard • Supabase: hanre-studio • Dropbox: /Videl0/backups</p>
      </footer>
    </main>
  );
}
