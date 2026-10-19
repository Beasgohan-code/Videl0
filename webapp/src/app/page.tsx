"use client";
import { useEffect, useState } from "react";

type Stats = { users:number; chats:number; commands:number };
type Health = { status:string; uptime?:number };

export default function Home() {
  const [stats, setStats] = useState<Stats>({users:0,chats:0,commands:0});
  const [health, setHealth] = useState<Health|null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(()=> {
    fetch("/api/stats").then(r=>r.json()).then(d=> setStats(d.stats ?? d)).catch(()=>{});
    fetch("/api/health").then(r=>r.json()).then(setHealth).catch(()=>{});
    const t=setTimeout(()=> setLoading(false), 600); return ()=> clearTimeout(t);
  },[]);

  const up = health?.uptime ? `${Math.floor(health.uptime/3600)}ʜ ${Math.floor(health.uptime%3600/60)}ᴍ` : "—";

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl cyber-border flex items-center justify-center font-bold text-[13px]">◍</div>
          <div>
            <h1 className="text-[13px] font-bold tracking-[0.14em] uppercase">◍ Vɪᴅᴇʟ ⫶ ᴘᴇʀғᴇᴄᴛ</h1>
            <p className="text-[11px] text-zinc-500 mono">ᴋᴜʀɪɢʀᴀᴍ ⫶ ᴘʏᴛɢᴄᴀʟʟs ⫶ ᴀɪᴏɢʀᴀᴍ 3.31 ⫶ ʀɪᴄʜɢʀᴀᴍ ⫶ sᴜᴘᴀʙᴀsᴇ ⫶ ᴅʀᴏᴘʙᴏx ⫶ ᴠᴇʀᴄᴇʟ</p>
          </div>
        </div>
        <div className="flex gap-2 text-[11px]">
          <a href="https://t.me/Videl0Bot" target="_blank" className="cyber-pill mono">⬪ ᴏᴘᴇɴ ɪɴ ᴛɢ ➪</a>
          <a href="/dashboard" className="cyber-pill mono">◎ ᴅᴀsʜʙᴏᴀʀᴅ</a>
          <a href="/api/health" target="_blank" className="cyber-pill" style={{color: health?.status==="ok"?"#10b981":"#f59e0b"}}>● {health?.status??"…"}</a>
        </div>
      </header>

      <section className="mt-10 cyber-border rounded-[20px] p-8 md:p-10">
        <div className="grid md:grid-cols-2 gap-8">
          <div>
            <p className="cyber-pill"><span className="cyber-dot"/> ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ ⫶ ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ ᴀᴄᴛɪᴠᴇ</p>
            <h2 className="mt-5 text-4xl md:text-[42px] font-black leading-[0.95] tracking-[-0.02em] uppercase">
              ᴍᴜsɪᴄ, ᴀɪ &<br/><span style={{color:"#9aa0b0"}}>ᴀᴅᴍɪɴ — ɪɴ ᴏɴᴇ</span>
            </h2>
            <p className="mt-4 text-zinc-400 text-[13px] leading-6 max-w-lg">
              ◍ ғᴜʟʟ-sᴛᴀᴄᴋ ᴛɢ ʙᴏᴛ ᴡɪᴛʜ ᴠᴄ sᴛʀᴇᴀᴍɪɴɢ, ᴀɪ ᴄʜᴀᴛ, ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇʀ & ᴏᴡɴᴇʀ ᴛᴏᴏʟs. ᴄʏʙᴇʀ ᴅᴀʀᴋ ᴘᴇʀғᴇᴄᴛ. ʙᴜɪʟᴛ ʙʏ ʙᴇᴀsɢᴏʜᴀɴ-ᴄᴏᴅᴇ ⫶ ʙᴀsᴇᴅ ᴏɴ ʀɪᴄʜɢʀᴀᴍ & sʜɪᴢᴜ.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <a href="https://t.me/Videl0Bot?startgroup=true" className="rounded-xl bg-white text-black px-5 py-2.5 text-[12px] font-bold uppercase tracking-wide">⬪ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ</a>
              <a href="/dashboard" className="cyber-border rounded-xl px-5 py-2.5 text-[12px]">◎ ᴅᴀsʜʙᴏᴀʀᴅ</a>
              <a href="https://github.com/Beasgohan-code/Videl0" target="_blank" className="cyber-border rounded-xl px-5 py-2.5 text-[12px]">⬢ ɢɪᴛʜᴜʙ</a>
            </div>
            <div className="mt-6 flex flex-wrap gap-2 text-[11px] text-zinc-500 mono">
              <span className="cyber-pill">⬪ /play</span>
              <span className="cyber-pill">⫶ /ask</span>
              <span className="cyber-pill">◎ /ban</span>
              <span className="cyber-pill">◍ /weather</span>
              <span className="cyber-pill">⬩ 10.3 ʀɪᴄʜ</span>
            </div>
          </div>

          <div className="cyber-border rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[11px] tracking-[0.1em] uppercase text-zinc-400">◍ ɴᴏᴡ ᴘʟᴀʏɪɴɢ — ʀɪᴄʜ ᴜɪ</h3>
              <span className="cyber-pill" style={{background:"#0f1a14", borderColor:"#143d2a", color:"#10b981"}}>● ʟɪᴠᴇ</span>
            </div>
            <div className="cyber-border rounded-xl p-4">
              <img src="https://files.catbox.moe/f084wg.png" alt="thumb" className="w-full h-28 object-cover rounded-lg border border-[#1e1e22]" />
              <h4 className="mt-3 text-[13px] font-semibold">sʜɪᴢᴜ — ʜɪɢʜ ǫᴜᴀʟɪᴛʏ ᴠᴄ</h4>
              <p className="text-[11px] text-zinc-500 mono">ᴅᴜʀ 3:27 ⫶ ʙʏ @ʙᴇᴀsɢᴏʜᴀɴ</p>
              <div className="mt-3 h-[3px] bg-[#1a1a1e] rounded-full overflow-hidden"><div className="h-full w-[42%] bg-white" /></div>
              <p className="mono text-[11px] text-zinc-500 mt-1">0:52 ⬪ ──◍────── ⬪ 3:27</p>
              <div className="mt-3 grid grid-cols-4 gap-2">
                <button className="cyber-border rounded-lg py-2 text-[11px]">ɪɪ ᴘᴀᴜsᴇ</button>
                <button className="cyber-border rounded-lg py-2 text-[11px]">▷ ʀᴇsᴜᴍᴇ</button>
                <button className="cyber-border rounded-lg py-2 text-[11px]">‣‣ sᴋɪᴘ</button>
                <button className="rounded-lg bg-[#1a0f0f] border border-[#2a1a1a] text-red-300 py-2 text-[11px]">⬩ sᴛᴏᴘ</button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {([["ᴜsᴇʀs", stats.users||"—"],["ᴄʜᴀᴛs", stats.chats||"—"],["ᴜᴘᴛɪᴍᴇ", up]] as const).map(([k,v])=>(
                <div key={k} className="cyber-border rounded-xl p-3">
                  <div className="text-[16px] font-bold">{loading?"…":v}</div>
                  <div className="text-[10px] text-zinc-500 tracking-wide">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 grid md:grid-cols-3 gap-3">
        {[
          ["◍ ᴍᴜsɪᴄ","ᴠᴄ sᴛʀᴇᴀᴍɪɴɢ ⫶ ǫᴜᴇᴜᴇ ⫶ ʟʏʀɪᴄs ⫶ ᴘʟᴀʏʟɪsᴛs"],
          ["⬪ ᴀɪ ᴄʜᴀᴛ","ᴏᴘᴇɴᴀɪ ⫶ ɢʀᴏǫ ⫶ ɢᴇᴍɪɴɪ ⫶ ɪᴍᴀɢɪɴᴇ"],
          ["⫶ ᴀᴅᴍɪɴ","ʙᴀɴ ⫶ ᴍᴜᴛᴇ ⫶ ᴡᴀʀɴ ⫶ ʟᴏᴄᴋ ⫶ ɢʙᴀɴ"],
          ["◎ ᴜᴛɪʟs","ᴡᴇᴀᴛʜᴇʀ ⫶ ǫʀ ⫶ ɢɪᴛ ⫶ ᴄᴀʀʙᴏɴ ⫶ ᴡɪᴋɪ"],
          ["⬢ ɢʀᴏᴜᴘs","ᴡᴇʟᴄᴏᴍᴇ ⫶ ғɪʟᴛᴇʀs ⫶ ɴᴏᴛᴇs ⫶ ʀᴜʟᴇs"],
          ["𖦹 ᴏᴘs","ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ ⫶ ᴡᴀᴛᴄʜᴅᴏɢ ⫶ ʟᴏɢs ⫶ ᴅʀᴏᴘʙᴏx"],
        ].map(([t,d])=>(
          <div key={t} className="cyber-border rounded-2xl p-5">
            <h3 className="text-[11px] tracking-[0.12em] font-bold">{t}</h3>
            <p className="text-[11px] text-zinc-500 mono mt-1 leading-5">{d}</p>
          </div>
        ))}
      </section>

      <section className="mt-6 cyber-border rounded-2xl p-6">
        <h3 className="text-[11px] tracking-[0.12em] font-bold">⬪ ʟɪᴠᴇ sᴛᴀᴛs ⬪</h3>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["ᴛᴏᴛᴀʟ ᴜsᴇʀs", stats.users ?? "—"],
            ["ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs", stats.chats ?? "—"],
            ["ᴄᴏᴍᴍᴀɴᴅs", stats.commands ?? "—"],
            ["sᴛᴀᴛᴜs", health?.status==="ok" ? "ʜᴇᴀʟᴛʜʏ" : "ᴄʜᴇᴄᴋɪɴɢ…"],
          ].map(([k,v])=>(
            <div key={k} className="cyber-border rounded-xl p-4">
              <div className="text-[18px] font-bold">{loading?"…":v}</div>
              <div className="text-[10px] text-zinc-500 tracking-wide mt-1">{k}</div>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-zinc-600 mono mt-4">sᴜᴘᴀʙᴀsᴇ ⫶ ᴅʀᴏᴘʙᴏx ⫶ ᴠᴇʀᴄᴇʟ ⫶ ᴡᴀᴛᴄʜᴅᴏɢ</p>
      </section>

      <section className="mt-6 cyber-border rounded-2xl p-6">
        <h3 className="text-[11px] tracking-[0.12em] font-bold">⬪ ᴄᴏᴍᴍᴀɴᴅs ⬪</h3>
        <div className="mt-4 grid md:grid-cols-2 gap-3 text-[11px] mono">
          {Object.entries({
            "◍ ᴍᴜsɪᴄ": "/play /vplay /queue /skip /stop /pause /lyrics /playlist /autoplay",
            "⬪ ᴀɪ": "/ask /gpt /imagine /summarize /translate /tts /vision",
            "⫶ ᴀᴅᴍɪɴ": "/ban /kick /mute /warn /pin /purge /lock /slowmode",
            "◎ ᴏᴡɴᴇʀ": "/broadcast /gban /addsudo /backup /eval /logs",
            "⬩ ᴜᴛɪʟs": "/weather /qr /shorten /calc /wiki /git /carbon /afk",
            "⬢ ɢʀᴏᴜᴘ": "/welcome /filter /note /rules /report /staff /setlang",
          }).map(([k,v])=>(
            <div key={k} className="cyber-border rounded-xl p-4"><div className="text-zinc-200 tracking-wide">{k}</div><div className="text-zinc-500 text-[11px] mt-1 leading-5">{v}</div></div>
          ))}
        </div>
      </section>

      <footer className="mt-10 text-center text-[11px] text-zinc-600 mono pb-8">
        <p>ᴍᴀᴅᴇ ᴡɪᴛʜ ◍ ʙʏ <a href="https://github.com/Beasgohan-code" className="text-zinc-400 border-zinc-700">ʙᴇᴀsɢᴏʜᴀɴ-ᴄᴏᴅᴇ</a> ⫶ ʀɪᴄʜɢʀᴀᴍ ʙʏ <a href="https://github.com/Badmunda05/richgram" className="text-zinc-400 border-zinc-700">ʙᴀᴅᴍᴜɴᴅᴀ05</a> ⫶ sʜɪᴢᴜᴍᴜsɪᴄ ⬪ ᴄʏʙᴇʀ ᴅᴀʀᴋ ᴘᴇʀғᴇᴄᴛ</p>
        <p className="mt-1 mono">ᴠᴇʀᴄᴇʟ: ʜᴏsᴛɪɴɢ-ʙᴏᴛ-ᴅᴀsʜʙᴏᴀʀᴅ ⫶ sᴜᴘᴀʙᴀsᴇ: ʜᴀɴʀᴇ-sᴛᴜᴅɪᴏ ⫶ ᴅʀᴏᴘʙᴏx: /Vɪᴅᴇʟ0/ʙᴀᴄᴋᴜᴘs</p>
      </footer>
    </main>
  );
}
