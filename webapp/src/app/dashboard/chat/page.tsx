"use client";
import { useEffect, useRef, useState } from "react";
import { ChatView, ChatMsg } from "@/components/chat/ChatView";
import { OwnerGate } from "@/components/auth/TelegramLogin";

export default function WebChatPage() {
  const [chatId, setChatId] = useState("muhehehe");
  const [asUser, setAsUser] = useState(false);
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { id: "1", chat_id: "muhehehe", from: "bot", text: "◍ Videl — real-time web chat 𖦹\n⬪ You are chatting as bot. Messages go via Bot API 10.3.\n⫶ Tip: set chat_id to -100123… or @username or user_id.\n◎ Toggle ‘as user’ to send via STRING_SESSION userbot (assistant).", time: new Date().toLocaleTimeString(), via: "system" },
  ]);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [typing, setTyping] = useState(false);
  const ownerId = parseInt(process.env.NEXT_PUBLIC_OWNER_ID || "0", 10);

  // History polling
  useEffect(() => {
    if (!live) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch(`/api/chat?chat_id=${encodeURIComponent(chatId)}`).then(x => x.json());
        if (r.items?.length) {
          const mapped: ChatMsg[] = r.items.slice(0, 20).map((m: any, i: number) => ({
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
      setStatus("⚠️ ‘muhehehe’ is demo — set real chat_id to send live");
      setMsgs(v => [...v, { id: Date.now() + "", chat_id: chatId, from: "you", text: t, time: new Date().toLocaleTimeString(), via: asUser ? "userbot" : "bot" }]);
      setText("");
      return;
    }
    setSending(true);
    setStatus(null);
    setTyping(true);
    const via = asUser ? "user" : "bot";
    setMsgs(v => [...v, { id: Date.now() + "", chat_id: chatId, from: "you", text: t, time: new Date().toLocaleTimeString(), via }]);
    setText("");
    // fake typing for realism
    await new Promise(r => setTimeout(r, 600));
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chat_id: chatId.trim(), text: t, as_user: asUser }) });
      const j = await res.json();
      if (j.ok) {
        setStatus(`✅ Sent via ${j.via || via} — ${j.message_id || ""}`);
        setMsgs(v => [...v, { id: (Date.now() + 1) + "", chat_id: chatId, from: "bot", text: `⬪ Delivered to ${j.chat_id || chatId} • ${j.via || via}`, time: new Date().toLocaleTimeString(), via: j.via || via }]);
      } else setStatus(`❌ ${j.error || "Failed"}`);
    } catch (e: any) { setStatus(`❌ ${String(e)}`); }
    finally { setSending(false); setTyping(false); }
  }

  const inner = (
    <main className="mx-auto max-w-6xl py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="ios-title">Web Chat</h1>
          <p className="ios-subheadline">Chat as <b>muhehehe</b> ⫶ bot + userbot (STRING_SESSION) ⫶ <code>{chatId || "muhehehe"}</code></p>
        </div>
        <div className="flex gap-2">
          <span className={`ios-pill ${live ? "ios-pill-blue" : ""}`}>● {live ? "Live" : "Paused"}</span>
          <a href="/dashboard/channel" className="ios-btn ios-btn-glass">⬪ Studio</a>
        </div>
      </header>

      <div className="mt-6 grid lg:grid-cols-[0.9fr_1.3fr] gap-4">
        {/* Left */}
        <div className="ios-card p-5 space-y-4 self-start lg:sticky lg:top-[72px]">
          <h3 className="ios-caption2">◎ Session</h3>
          <div>
            <label className="ios-caption">Chat ID (where to send)</label>
            <input value={chatId} onChange={e => setChatId(e.target.value)} placeholder="muhehehe | -100123… | @username | 123456" className="ios-input mt-2" />
            <p className="ios-caption mt-2">Demo <code>muhehehe</code> = local only. Set real ID to send live.</p>
          </div>

          <div className="ios-card p-3 flex items-center justify-between bg-[var(--ios-fill-secondary)]">
            <div><div className="text-[13px] font-semibold">Send as</div><div className="ios-caption">{asUser ? "userbot (you)" : "bot (@Videl0Bot)"}</div></div>
            <button onClick={() => setAsUser(v => !v)} className={`relative h-7 w-12 rounded-full transition ${asUser ? "bg-white" : "bg-[#2C2C2E] border border-[var(--ios-border)]"}`}><span className={`absolute top-[3px] h-5 w-5 rounded-full transition ${asUser ? "bg-black translate-x-6" : "bg-white translate-x-1"}`} /></button>
          </div>

          <div className="ios-card p-3">
            <div className="text-[13px] font-semibold">◍ How it works</div>
            <ul className="mt-2 space-y-1 ios-caption">
              <li>• <b>Bot</b>: Bot API 10.3 — needs admin</li>
              <li>• <b>User</b>: Pyrogram STRING_SESSION — sends as you</li>
              <li>• Polls Supabase <code>videl_webchat</code> every 4s</li>
            </ul>
          </div>

          <div className="flex gap-2">
            <button onClick={() => setLive(v => !v)} className="ios-btn ios-btn-glass flex-1">{live ? "⏸ Pause" : "▶ Resume"}</button>
            <button onClick={() => setMsgs(v => v.slice(0, 1))} className="ios-btn ios-btn-glass">Clear</button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {[["Demo", "muhehehe"], ["Channel", "@VidelUpdates"], ["Group", "-100123456789"], ["User", "123456789"]].map(([k, v]) => (
              <button key={k} onClick={() => setChatId(v)} className="ios-card p-3 text-left">
                <div className="ios-caption">{k}</div><code className="text-[13px]">{v}</code>
              </button>
            ))}
          </div>

          <div className="ios-card p-3 ios-caption">
            <b>Setup real user:</b> Generate STRING_SESSION via @StringSessionBot → add env STRING_SESSION → bot auto-connects as userbot.
          </div>
        </div>

        {/* Right — iOS chat */}
        <div className="ios-card-elevated overflow-hidden flex flex-col min-h-[520px]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--ios-separator)] bg-[var(--ios-card)]">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-white text-black flex items-center justify-center text-[12px] font-bold">◍</div>
              <div><div className="text-[14px] font-semibold">Videl Chat <span className="text-[var(--ios-label-secondary)] font-normal">• {chatId}</span></div><div className="ios-caption">{asUser ? "as you (userbot)" : "as bot"} • {msgs.length} msgs</div></div>
            </div>
            <span className="ios-pill">◍ Videl Perfect</span>
          </div>

          <ChatView msgs={msgs} typing={typing} onClear={() => setMsgs(v => v.slice(0, 1))} />

          <div className="p-3 border-t border-[var(--ios-separator)] bg-[var(--ios-card)]">
            {status && <div className={`mb-2 p-2 rounded-[10px] text-[12px] border ${status.startsWith("✅") ? "bg-[rgba(48,209,88,0.14)] border-[rgba(48,209,88,0.2)] text-[#30D158]" : status.startsWith("⚠️") ? "bg-[rgba(255,159,10,0.14)] border-[rgba(255,159,10,0.2)] text-[#FF9F0A]" : "bg-[rgba(255,69,58,0.14)] border-[rgba(255,69,58,0.2)] text-[#FF453A]"}`}>{status}</div>}
            <div className="flex gap-2 items-end">
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder={chatId === "muhehehe" ? "Type — demo local (set real chat_id)…" : `Message ${chatId} as ${asUser ? "you" : "bot"}…`}
                rows={1}
                className="flex-1 ios-input py-3 resize-none min-h-[44px] max-h-[120px]"
                style={{ fieldSizing: "content" } as any}
              />
              <button onClick={send} disabled={sending || !text.trim()} className="h-11 w-11 rounded-full bg-[#0A84FF] text-white flex items-center justify-center shrink-0 disabled:opacity-50 active:scale-95 transition">➤</button>
            </div>
            <p className="ios-caption mt-2">Enter = send • Shift+Enter = newline • owner-only • Supabase logged</p>
          </div>
        </div>
      </div>
    </main>
  );

  if (ownerId) return <OwnerGate ownerId={ownerId}>{inner}</OwnerGate>;
  return inner;
}
