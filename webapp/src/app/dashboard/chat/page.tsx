"use client";
import { useEffect, useRef, useState } from "react";

type Msg = { id: string; chat_id: string; from: "you" | "bot" | "user"; text: string; time: string; via?: string };

export default function WebChat() {
  const [chatId, setChatId] = useState("muhehehe");
  const [asUser, setAsUser] = useState(false);
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    { id: "1", chat_id: "muhehehe", from: "bot", text: "◍ Videl — real-time web chat 𖦹\n⬪ You are chatting as bot. Messages go via Bot API 10.3.\n⫶ Tip: set chat_id to -100123… or @username or user_id.\n◎ Toggle ‘as user’ to send via STRING_SESSION userbot (assistant).", time: new Date().toLocaleTimeString(), via: "system" },
  ]);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(true);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  // Poll history from Supabase via API (if available)
  useEffect(() => {
    if (!live) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch(`/api/chat?chat_id=${encodeURIComponent(chatId)}`).then(x => x.json());
        if (r.items?.length) {
          const mapped: Msg[] = r.items.slice(0, 20).map((m: any, i: number) => ({
            id: String(m.id ?? i),
            chat_id: String(m.chat_id ?? chatId),
            from: m.from === "owner" ? "you" : m.from || "user",
            text: m.content || m.text || "",
            time: new Date(m.created_at || Date.now()).toLocaleTimeString(),
            via: m.via || "api",
          }));
          if (mapped.length) setMsgs(v => [...v.slice(-30), ...mapped.slice(-5)]);
        }
      } catch {}
    }, 4000);
    return () => clearInterval(id);
  }, [chatId, live]);

  async function send() {
    const t = text.trim();
    if (!t) return;
    if (chatId.trim() === "muhehehe") {
      setStatus("⚠️ ‘muhehehe’ is demo — set real chat_id (e.g. -100123… or @channel or user id) to actually send.");
      setMsgs(v => [...v, { id: Date.now() + "", chat_id: chatId, from: "you", text: t, time: new Date().toLocaleTimeString(), via: asUser ? "userbot" : "bot" }]);
      setText("");
      return;
    }
    setSending(true);
    setStatus(null);
    const localId = Date.now() + "";
    const via = asUser ? "user" : "bot";
    setMsgs(v => [...v, { id: localId, chat_id: chatId, from: "you", text: t, time: new Date().toLocaleTimeString(), via }]);
    setText("");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId.trim(), text: t, as_user: asUser }),
      });
      const j = await res.json();
      if (j.ok) {
        setStatus(`✅ Sent via ${j.via || via} — id ${j.message_id || j.id || "—"}`);
        setMsgs(v => [...v, { id: (Date.now() + 1) + "", chat_id: chatId, from: "bot", text: `⬪ Delivered to ${j.chat_id || chatId} • ${j.via || via}\n⫶ ${t.slice(0, 80)}`, time: new Date().toLocaleTimeString(), via: j.via || via }]);
      } else {
        setStatus(`❌ ${j.error || "Failed"}`);
      }
    } catch (e: any) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[13px] tracking-[0.14em] font-bold uppercase">◍ ᴡᴇʙ ᴄʜᴀᴛ — ʀᴇᴀʟ ᴜsᴇʀ 𖦹</h1>
          <p className="text-[11px] text-zinc-500 mono">ᴄʜᴀᴛ ᴀs ᴍᴜʜᴇʜᴇʜᴇ ⫶ ʙᴏᴛ + ᴜsᴇʀʙᴏᴛ (STRING_SESSION) ⫶ chat_id: <code className="text-white">{chatId || "muhehehe"}</code> ⫶ Vercel + Supabase + Python bot</p>
        </div>
        <div className="flex gap-2 text-[11px] mono">
          <a href="/dashboard" className="cyber-pill">◎ ᴅᴀsʜʙᴏᴀʀᴅ</a>
          <a href="/dashboard/channel" className="cyber-pill">⬪ ᴄʜᴀɴɴᴇʟ sᴛᴜᴅɪᴏ</a>
          <span className={`cyber-pill ${live ? "" : "opacity-60"}`} style={{ color: live ? "#10b981" : undefined, borderColor: live ? "#143d2a" : undefined }}>● {live ? "ʟɪᴠᴇ" : "ᴘᴀᴜsᴇᴅ"}</span>
        </div>
      </header>

      <div className="mt-6 grid lg:grid-cols-[0.95fr_1.25fr] gap-4">
        {/* Left — controls */}
        <section className="cyber-border rounded-2xl p-5 space-y-4">
          <div>
            <h2 className="text-[11px] tracking-[0.12em] font-bold">◎ sᴇssɪᴏɴ ◎</h2>
            <div className="mt-3 space-y-3">
              <div>
                <label className="text-[11px] text-zinc-400 mono">ᴄʜᴀᴛ ɪᴅ (ᴡʜᴇʀᴇ ᴛᴏ sᴇɴᴅ)</label>
                <input value={chatId} onChange={e => setChatId(e.target.value)} placeholder="muhehehe | -100123… | @username | 123456" className="mt-1 w-full cyber-border rounded-xl px-4 py-3 text-[12px] mono outline-none bg-[#0f0f10] border-[#1e1e22]" />
                <p className="text-[10px] text-zinc-600 mono mt-1">Demo <code>muhehehe</code> = local-only. Set real ID to send live via Telegram.</p>
              </div>

              <div className="flex items-center justify-between cyber-border rounded-xl p-3 bg-[#0f0f10]">
                <div>
                  <div className="text-[11px] font-bold">⬪ Send as</div>
                  <div className="text-[10px] text-zinc-500 mono">{asUser ? "userbot (STRING_SESSION)" : "bot (BOT_TOKEN)"}</div>
                </div>
                <button onClick={() => setAsUser(v => !v)} className={`relative h-7 w-12 rounded-full transition ${asUser ? "bg-white" : "bg-[#1e1e22] border border-[#2a2a2e]"}`}>
                  <span className={`absolute top-[3px] h-5 w-5 rounded-full transition ${asUser ? "bg-black translate-x-6" : "bg-white translate-x-1"}`} />
                </button>
              </div>

              <div className="cyber-border rounded-xl p-3 bg-[#0f0f10] text-[11px] mono leading-5 text-zinc-400">
                <div className="font-bold text-white">◍ How it works</div>
                <div className="mt-1 space-y-1">
                  <div>• <b>Bot</b>: via Bot API 10.3 — needs bot admin in channel/group.</div>
                  <div>• <b>User</b>: via Pyrogram userbot (<code>STRING_SESSION</code>) — sends as you. Enable in bot: <code>STRING_SESSION</code> env.</div>
                  <div>• Polls <code>/api/chat?chat_id=</code> every 4s (Supabase <code>videl_messages</code> if present).</div>
                </div>
              </div>

              <div className="flex gap-2">
                <button onClick={() => setLive(v => !v)} className="cyber-border rounded-xl px-4 py-2 text-[11px] mono flex-1">{live ? "⏸ ᴘᴀᴜsᴇ" : "▶ ʀᴇsᴜᴍᴇ"}</button>
                <button onClick={() => setMsgs(v => v.slice(-1))} className="cyber-border rounded-xl px-4 py-2 text-[11px] mono">◎ ᴄʟᴇᴀʀ</button>
              </div>
            </div>
          </div>

          <div className="cyber-border rounded-2xl p-4 bg-[#0a0a0a]">
            <h3 className="text-[11px] tracking-[0.12em] font-bold">⬢ ᴇxᴀᴍᴘʟᴇ ɪᴅs ⬢</h3>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] mono">
              {[["Demo", "muhehehe"], ["Channel", "@VidelUpdates"], ["Group", "-100123456789"], ["User", "123456789"]].map(([k, v]) => (
                <button key={k} onClick={() => setChatId(v)} className="cyber-border rounded-xl p-3 text-left hover:bg-[#111113]"><div className="text-zinc-500">{k}</div><code className="text-white">{v}</code></button>
              ))}
            </div>
          </div>
        </section>

        {/* Right — chat */}
        <section className="cyber-border rounded-2xl p-0 overflow-hidden flex flex-col" style={{ minHeight: 420 }}>
          <div className="flex items-center justify-between p-4 border-b border-[#1e1e22]">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-white text-black flex items-center justify-center text-[11px] font-bold">◍</div>
              <div>
                <div className="text-[12px] font-bold">Videl WebChat <span className="text-zinc-500 font-normal">⫶ {chatId}</span></div>
                <div className="text-[11px] text-zinc-500 mono">{asUser ? "as user (you)" : "as bot (@Videl0Bot)"} • {msgs.length} msgs</div>
              </div>
            </div>
            <span className="cyber-pill text-[10px] mono">◍ Vɪᴅᴇʟ ⫶ ᴘᴇʀғᴇᴄᴛ</span>
          </div>

          <div ref={listRef} className="flex-1 overflow-auto p-4 space-y-3 bg-[#0a0a0a]" style={{ maxHeight: 360 }}>
            {msgs.map(m => (
              <div key={m.id} className={`max-w-[85%] rounded-2xl px-4 py-3 text-[12px] leading-6 ${m.from === "you" ? "ml-auto bg-white text-black" : "bg-[#111113] border border-[#1e1e22] text-zinc-200"}`}>
                <div className="whitespace-pre-wrap break-words">{m.text}</div>
                <div className={`mt-1 text-[10px] mono ${m.from === "you" ? "text-zinc-600" : "text-zinc-500"}`}>{m.time} • {m.via || m.from} • {m.chat_id}</div>
              </div>
            ))}
          </div>

          <div className="p-3 border-t border-[#1e1e22] bg-[#0f0f10]">
            {status && <div className={`mb-2 text-[11px] mono rounded-xl p-2 border ${status.startsWith("✅") ? "border-[#143d2a] text-[#10b981] bg-[#0f1a14]" : status.startsWith("⚠️") ? "border-[#422006] text-amber-300 bg-[#1a140f]" : "border-[#2a1a1a] text-red-300 bg-[#1a0f0f]"}`}>{status}</div>}
            <div className="flex gap-2">
              <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder={chatId === "muhehehe" ? "Type — demo local (set real chat_id to send live)…" : `Message ${chatId} as ${asUser ? "you" : "bot"}… (Enter to send)`} className="flex-1 cyber-border rounded-xl px-4 py-3 text-[12px] mono outline-none bg-[#0a0a0a] border-[#1e1e22]" />
              <button onClick={send} disabled={sending || !text.trim()} className="rounded-xl bg-white text-black px-6 text-[12px] font-bold disabled:opacity-50">➪</button>
            </div>
            <p className="mt-2 text-[10px] text-zinc-600 mono">Enter = send • Shift+Enter = newline • Uses Bot API (bot) or Pyrogram user session (user). Logged to Supabase if configured.</p>
          </div>
        </section>
      </div>

      <section className="mt-4 cyber-border rounded-2xl p-4">
        <h3 className="text-[11px] tracking-[0.12em] font-bold">◎ sᴇᴛᴜᴘ — ʀᴇᴀʟ ᴜsᴇʀ ᴍᴏᴅᴇ ◎</h3>
        <div className="mt-3 grid md:grid-cols-3 gap-3 text-[11px] mono">
          <div className="cyber-border rounded-xl p-3 bg-[#0f0f10]"><b>1. STRING_SESSION</b><br /><span className="text-zinc-500">Generate via @StringSessionBot • Add to env <code>STRING_SESSION</code>. Deployed bot auto-connects as userbot.</span></div>
          <div className="cyber-border rounded-xl p-3 bg-[#0f0f10]"><b>2. Bot as admin</b><br /><span className="text-zinc-500">For channels/groups: add <code>@Videl0Bot</code> as admin → can post via Bot API even without userbot.</span></div>
          <div className="cyber-border rounded-xl p-3 bg-[#0f0f10]"><b>3. Supabase history</b><br /><span className="text-zinc-500">Optional: creates <code>videl_webchat</code> table → live history + search. Fallback is stateless send.</span></div>
        </div>
      </section>

      <footer className="mt-6 text-center text-[10px] text-zinc-600 mono">web chat • channel studio • music • ai — ◍ Videl perfect • Kurigram · PyTgCalls · Richgram · Vercel</footer>
    </main>
  );
}
