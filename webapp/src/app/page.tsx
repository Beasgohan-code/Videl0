"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Music2, Sparkles, Shield, Wrench, Users, Zap } from "lucide-react";

type Stats = { users: number; chats: number; commands: number };
type Health = { status: string; uptime?: number };

export default function Home() {
  const [stats, setStats] = useState<Stats>({ users: 0, chats: 0, commands: 0 });
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    fetch("/api/stats").then(r => r.json()).then(d => setStats(d.stats ?? d)).catch(() => {});
    fetch("/api/health").then(r => r.json()).then(setHealth).catch(() => {});
  }, []);

  const up = health?.uptime ? `${Math.floor(health.uptime / 3600)}h ${Math.floor((health.uptime % 3600) / 60)}m` : "—";

  return (
    <main className="mx-auto max-w-6xl py-6">
      {/* iOS Hero */}
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} className="ios-card-elevated p-6 md:p-10 overflow-hidden relative">
        <div className="absolute -top-20 -right-20 h-64 w-64 rounded-full bg-[radial-gradient(circle_at_center,rgba(10,132,255,0.18),transparent_70%)] blur-2xl" />
        <div className="grid md:grid-cols-[1.1fr_0.9fr] gap-8 items-center">
          <div>
            <span className="ios-pill ios-pill-blue"><span className="h-2 w-2 rounded-full bg-[#0A84FF] animate-pulse" /> Live • Keep-alive active</span>
            <h1 className="ios-title-large mt-4">Music, AI<br/><span className="text-[var(--ios-label-secondary)]">and admin —</span> in one.</h1>
            <p className="ios-subheadline mt-3 max-w-[520px]">◍ Full-stack TG bot with VC streaming, AI chat, group manager & owner tools. iOS 26 glass • Built by <b>Beasgohan-code</b> on Richgram & Shizu.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <a href="https://t.me/Videl0Bot?startgroup=true" className="ios-btn ios-btn-primary">⬪ Add to Group</a>
              <Link href="/dashboard" className="ios-btn ios-btn-glass">◎ Dashboard</Link>
              <a href="https://github.com/Beasgohan-code/Videl0" target="_blank" className="ios-btn ios-btn-ghost">⬢ GitHub</a>
            </div>
            <div className="mt-6 flex flex-wrap gap-2">
              {["⬪ /play","⫶ /ask","◎ /ban","◍ /weather","⬩ Bot API 10.3"].map(s => (
                <span key={s} className="ios-pill">{s}</span>
              ))}
            </div>
          </div>

          <div className="ios-card p-4 space-y-3 bg-[#0A0A0B]">
            <div className="flex items-center justify-between">
              <h3 className="ios-caption2">◍ Now Playing — Rich UI</h3>
              <span className="ios-pill" style={{ background: "rgba(48,209,88,0.12)", color: "#30D158", borderColor: "rgba(48,209,88,0.16)" }}>● Live</span>
            </div>
            <div className="ios-card-elevated p-4">
              <img src="https://files.catbox.moe/f084wg.png" alt="" className="w-full h-28 object-cover rounded-[12px]" />
              <h4 className="ios-headline mt-3 text-[14px]">Shizu — High Quality VC</h4>
              <p className="ios-caption">Dur 3:27 ⫶ by @Beasgohan</p>
              <div className="mt-3 h-1 bg-[#1E1E22] rounded-full overflow-hidden"><div className="h-full w-[42%] bg-white" /></div>
              <p className="ios-caption mt-1">0:52 ⬪ ──◍────── ⬪ 3:27</p>
              <div className="mt-3 grid grid-cols-4 gap-2">
                <button className="ios-btn ios-btn-glass py-2 text-[11px]">II Pause</button>
                <button className="ios-btn ios-btn-glass py-2 text-[11px]">▷ Resume</button>
                <button className="ios-btn ios-btn-glass py-2 text-[11px]">‣‣ Skip</button>
                <button className="ios-btn ios-btn-red py-2 text-[11px]">⬩ Stop</button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                ["Users", stats.users || "—"],
                ["Chats", stats.chats || "—"],
                ["Uptime", up],
              ].map(([k, v]) => (
                <div key={k} className="ios-card p-3">
                  <div className="text-[16px] font-bold">{v}</div>
                  <div className="ios-caption2">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.section>

      {/* Features — iOS grouped */}
      <section className="mt-6 grid md:grid-cols-3 gap-3">
        {[
          { icon: Music2, t: "◍ Music", d: "VC streaming ⫶ queue ⫶ lyrics ⫶ playlists ⫶ /song downloader" },
          { icon: Sparkles, t: "⬪ AI Chat", d: "OpenAI ⫶ Groq ⫶ Gemini ⫶ imagine ⫶ vision ⫶ tts" },
          { icon: Shield, t: "⫶ Admin", d: "Ban ⫶ mute ⫶ warn ⫶ lock ⫶ gban ⫶ federation" },
          { icon: Wrench, t: "◎ Utils", d: "Weather ⫶ QR ⫶ carbon ⫶ git ⫶ wiki ⫶ afk" },
          { icon: Users, t: "⬢ Groups", d: "Welcome ⫶ filters ⫶ notes ⫶ rules ⫶ connections" },
          { icon: Zap, t: "𖦹 Ops", d: "Keep-alive ⫶ watchdog ⫶ logs ⫶ Dropbox ⫶ Vercel" },
        ].map(f => (
          <div key={f.t} className="ios-card p-5 flex gap-3">
            <div className="h-9 w-9 rounded-full bg-white text-black flex items-center justify-center shrink-0"><f.icon size={16} /></div>
            <div>
              <h3 className="ios-caption2 !text-white">{f.t}</h3>
              <p className="ios-caption mt-1 leading-5">{f.d}</p>
            </div>
          </div>
        ))}
      </section>

      {/* Commands + Live stats */}
      <section className="mt-6 grid md:grid-cols-2 gap-3">
        <div className="ios-card p-6">
          <h3 className="ios-caption2">⬪ Commands</h3>
          <div className="mt-4 grid gap-3">
            {Object.entries({
              "◍ Music": "/play /vplay /cplay /queue /skip /stop /pause /lyrics /song /vsong",
              "⬪ AI": "/ask /gpt /imagine /summarize /translate /tts /vision",
              "⫶ Admin": "/ban /kick /mute /warn /pin /purge /lock /slowmode",
              "◎ Owner": "/broadcast /gban /addsudo /backup /eval /logs",
            }).map(([k, v]) => (
              <div key={k} className="ios-list-row !py-3">
                <span className="text-[13px] font-semibold">{k}</span>
                <span className="ios-caption text-right max-w-[68%] leading-5">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="ios-card p-6">
          <h3 className="ios-caption2">⬪ Live Stats</h3>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              ["Total users", stats.users ?? "—"],
              ["Active chats", stats.chats ?? "—"],
              ["Commands", stats.commands ?? "—"],
              ["Status", health?.status === "ok" ? "Healthy" : "Checking…"],
            ].map(([k, v]) => (
              <div key={k} className="ios-card p-4 text-center bg-[var(--ios-card-elevated)]">
                <div className="text-[18px] font-bold">{v}</div>
                <div className="ios-caption2 mt-1">{k}</div>
              </div>
            ))}
          </div>
          <p className="ios-caption mt-4">Supabase ⫶ Dropbox ⫶ Vercel ⫶ watchdog • {health?.status ?? "..."}</p>
          <div className="mt-4 flex gap-2">
            <Link href="/dashboard/channel" className="ios-btn ios-btn-primary flex-1">⬪ Studio</Link>
            <Link href="/dashboard/chat" className="ios-btn ios-btn-glass flex-1">◍ Web Chat</Link>
          </div>
        </div>
      </section>

      <footer className="mt-10 pb-8 text-center ios-caption">
        Made with ◍ by <a href="https://github.com/Beasgohan-code" className="text-white">Beasgohan-code</a> ⫶ Richgram by <a href="https://github.com/Badmunda05/richgram" className="text-white">Badmunda05</a> ⫶ ShizuMusic ⬪ iOS 26 Perfect<br/>
        Vercel: hosting-bot-dashboard ⫶ Supabase: hanre-studio ⫶ Dropbox: /Videl0/backups
      </footer>
    </main>
  );
}
