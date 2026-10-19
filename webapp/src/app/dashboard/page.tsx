"use client";
import { useEffect, useState } from "react";

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
        <div>
          <h1 className="text-[13px] tracking-[0.14em] font-bold uppercase">◍ Vɪᴅᴇʟ — ᴅᴀsʜʙᴏᴀʀᴅ ⬪</h1>
          <p className="text-[11px] text-zinc-500 mono">sᴜᴘᴀʙᴀsᴇ ⫶ ᴅʀᴏᴘʙᴏx ⫶ ᴠᴇʀᴄᴇʟ ⫶ ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ ⫶ ᴡᴀᴛᴄʜᴅᴏɢ</p>
        </div>
        <div className="flex gap-2 text-[11px] mono">
          <span className="cyber-pill" style={{color:"#10b981", borderColor:"#143d2a"}}>● ᴏᴡɴᴇʀ</span>
          <span className="cyber-pill">◍ sᴜᴘᴀʙᴀsᴇ ⬪ ᴄᴏɴɴᴇᴄᴛᴇᴅ</span>
        </div>
      </header>

      <nav className="mt-6 flex gap-2 overflow-auto">
        {[
          ["overview","◍ ᴏᴠᴇʀᴠɪᴇᴡ"], ["music","⬪ ᴍᴜsɪᴄ"], ["ai","⦿ ᴀɪ"], ["moderation","◎ ᴍᴏᴅs"], ["ops","⬢ ᴏᴘs"]
        ].map(([id,label])=>(
          <button key={id} onClick={()=>setTab(id)} className={`rounded-full px-4 py-2 text-[11px] mono ${tab===id?"bg-white text-black font-bold":"cyber-border"}`}>{label}</button>
        ))}
      </nav>

      {tab==="overview" && (
        <section className="mt-6 grid md:grid-cols-3 gap-3">
          <div className="cyber-border rounded-2xl p-5"><div className="text-[11px] tracking-wide text-zinc-500">◍ ᴜsᴇʀs</div><div className="text-2xl font-bold mt-1">{stats?.users ?? "—"}</div></div>
          <div className="cyber-border rounded-2xl p-5"><div className="text-[11px] tracking-wide text-zinc-500">⫶ ᴄʜᴀᴛs</div><div className="text-2xl font-bold mt-1">{stats?.chats ?? "—"}</div></div>
          <div className="cyber-border rounded-2xl p-5"><div className="text-[11px] tracking-wide text-zinc-500">⬪ ᴄᴏᴍᴍᴀɴᴅs</div><div className="text-2xl font-bold mt-1">{stats?.commands ?? "—"}</div></div>
          <div className="cyber-border rounded-2xl p-5 md:col-span-3">
            <h3 className="text-[11px] tracking-[0.1em] font-bold">⬪ sʏsᴛᴇᴍ ⬪</h3>
            <div className="mt-3 grid md:grid-cols-4 gap-3 text-[11px] mono">
              <div className="cyber-border rounded-xl p-3">ʙᴏᴛ: @Vɪᴅᴇʟ0Bᴏᴛ<br/><span className="text-zinc-500">ᴀɪᴏɢʀᴀᴍ 3.31</span></div>
              <div className="cyber-border rounded-xl p-3">ᴅʙ: sᴜᴘᴀʙᴀsᴇ<br/><span className="text-zinc-500">ʜᴀɴʀᴇ-sᴛᴜᴅɪᴏ</span></div>
              <div className="cyber-border rounded-xl p-3">ʙᴀᴄᴋᴜᴘ: ᴅʀᴏᴘʙᴏx<br/><span className="text-zinc-500">/Vɪᴅᴇʟ0/ʙᴀᴄᴋᴜᴘs</span></div>
              <div className="cyber-border rounded-xl p-3">ʜᴏsᴛ: ᴠᴇʀᴄᴇʟ<br/><span className="text-zinc-500">ʜᴏsᴛɪɴɢ-ᴅᴀsʜʙᴏᴀʀᴅ</span></div>
            </div>
          </div>
        </section>
      )}

      {tab==="music" && (
        <section className="mt-6 cyber-border rounded-2xl p-5">
          <h3 className="text-[11px] tracking-[0.1em] font-bold">⬪ ᴍᴜsɪᴄ ǫᴜᴇᴜᴇ ⬪</h3>
          <div className="mt-4 space-y-2">
            {queue.length? queue.map((q:any,i:number)=>(
              <div key={q.id||i} className="flex justify-between cyber-border rounded-xl p-3 text-[12px] mono"><span>{i+1}. {q.title}</span><span className="text-zinc-500">{q.duration}s ⫶ {q.chat_id}</span></div>
            )): <p className="text-[11px] text-zinc-500 mono">ɴᴏ ᴀᴄᴛɪᴠᴇ ǫᴜᴇᴜᴇs — ᴜsᴇ /play ɪɴ ᴛɢ</p>}
          </div>
        </section>
      )}

      {tab==="moderation" && (
        <section className="mt-6 cyber-border rounded-2xl p-5">
          <h3 className="text-[11px] tracking-[0.1em] font-bold">◎ ɢʙᴀɴs ◎</h3>
          <div className="mt-4 space-y-2">
            {gbans.length? gbans.map((g:any)=>(
              <div key={g.user_id} className="cyber-border rounded-xl p-3 text-[12px] mono flex justify-between"><span><code>{g.user_id}</code> — {g.reason}</span><span className="text-amber-300">◍</span></div>
            )): <p className="text-[11px] text-zinc-500 mono">ɴᴏ ɢʙᴀɴs</p>}
          </div>
        </section>
      )}

      {tab==="ai" && (
        <section className="mt-6 cyber-border rounded-2xl p-5">
          <h3 className="text-[11px] tracking-[0.1em] font-bold">⦿ ᴀɪ ᴘʟᴀʏɢʀᴏᴜɴᴅ ⦿</h3>
          <p className="text-[11px] text-zinc-500 mono mt-2">ᴛᴇsᴛ ᴘʀᴏᴍᴘᴛs — sᴀᴍᴇ ᴘʀᴏᴠɪᴅᴇʀ ᴀs ʙᴏᴛ (ᴏᴘᴇɴᴀɪ→ɢʀᴏǫ→ɢᴇᴍɪɴɪ)</p>
          <div className="mt-4 flex gap-2">
            <input id="aiq" placeholder="ᴀsᴋ Vɪᴅᴇʟ…" className="flex-1 cyber-border rounded-xl px-4 py-3 text-[12px] mono outline-none bg-[#0f0f10]"/>
            <button onClick={async()=>{
              const el=document.getElementById("aiq") as HTMLInputElement;
              const q=el?.value; if(!q) return;
              const r=await fetch("/api/ai",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:q})}).then(x=>x.json());
              alert(r.answer || r.error);
            }} className="bg-white text-black rounded-xl px-5 text-[11px] font-bold">⬪ ᴀsᴋ</button>
          </div>
        </section>
      )}

      {tab==="ops" && (
        <section className="mt-6 cyber-border rounded-2xl p-5">
          <h3 className="text-[11px] tracking-[0.1em] font-bold">⬢ ᴏᴘs & ʟᴏɢs ⬢</h3>
          <div className="mt-3 grid md:grid-cols-2 gap-3 text-[11px] mono">
            <div className="cyber-border rounded-xl p-3">ᴋᴇᴇᴘ-ᴀʟɪᴠᴇ: <span style={{color:"#10b981"}}>ᴀᴄᴛɪᴠᴇ (300s)</span><br/>ᴡᴀᴛᴄʜᴅᴏɢ: <span style={{color:"#10b981"}}>ᴀᴄᴛɪᴠᴇ</span><br/>ʟᴏɢs: <code>-100…</code></div>
            <div className="cyber-border rounded-xl p-3">ᴅʀᴏᴘʙᴏx: <span className="text-zinc-400">ᴇᴠᴇʀʏ 6ʜ</span><br/>ᴠᴇʀᴄᴇʟ: ᴇɴᴀʙʟᴇᴅ<br/>ᴇɴᴠ: ᴘʀᴏᴅᴜᴄᴛɪᴏɴ ⫶ ᴄʏʙᴇʀ ᴅᴀʀᴋ</div>
          </div>
        </section>
      )}
    </main>
  );
}
