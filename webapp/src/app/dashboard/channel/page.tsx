"use client";
import { useState } from "react";

export default function ChannelStudio() {
  const [channel, setChannel] = useState("@");
  const [text, setText] = useState("");
  const [parseMode, setParseMode] = useState<"HTML" | "Markdown">("HTML");
  const [mediaUrl, setMediaUrl] = useState("");
  const [buttons, setButtons] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [preview, setPreview] = useState(false);

  async function sendPost() {
    if (!channel || channel === "@" || !text.trim()) {
      setResult("⚠️ Fill channel & text.");
      return;
    }
    setSending(true);
    setResult(null);
    try {
      const res = await fetch("/api/channel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: channel.trim(), text, parse_mode: parseMode, media_url: mediaUrl.trim() || undefined, buttons: buttons.trim() || undefined }),
      });
      const j = await res.json();
      if (j.ok) {
        setResult(`✅ Sent — message_id ${j.message_id} • ${j.chat_id}`);
      } else {
        setResult(`❌ ${j.error || "Failed"}`);
      }
    } catch (e: any) {
      setResult(`❌ ${String(e)}`);
    } finally {
      setSending(false);
    }
  }

  const t = `◍ ᴄʜᴀɴɴᴇʟ ᴘᴏsᴛ sᴛᴜᴅɪᴏ 𖦹`;
  const samples = [
    ["Cyber announcement", `◍ Vɪᴅᴇʟ ⫶ ᴜᴘᴅᴀᴛᴇ 𖦹\n\n⬪ <b>New music engine shipped</b> ⫶ yt-dlp + aria2c\n⫶ <code>/song</code> — instant MP3 192k • <code>/vsong</code> — MP4 1080p\n◎ <code>/play</code> still streams to VC • queue + effects\n\n⬢ <i>Powered by kurigram + pytgcalls + richgram</i> — Beasgohan-code`],
    ["Welcome template", `◍ Wᴇʟᴄᴏᴍᴇ ⫶ @Vɪᴅᴇʟ0Bᴏᴛ 𖦹\n\n◎ Add to group → /start\n⬪ Music: /play <code>song</code>\n⫶ AI: /ask <code>question</code>\n⬢ Admin: /ban /mute /warn /lock`],
    ["Giveaway", `𖦹 ɢɪᴠᴇᴀᴡᴀʏ ⦿\n\n⬪ Prize: <b>Premium x1</b>\n⫶ Join @UpdatesChannel\n◎ Winner in 24ʜ — good luck!`],
  ] as const;

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[13px] tracking-[0.14em] font-bold uppercase">{t}</h1>
          <p className="text-[11px] text-zinc-500 mono">ᴄʜᴀɴɴᴇʟ ᴘᴏsᴛ ᴍᴀᴋᴇʀ ⫶ ʟɪᴠᴇ ᴘʀᴇᴠɪᴇᴡ ⫶ ʙᴏᴛ ᴀᴘɪ 10.3 ⫶ ʀɪᴄʜɢʀᴀᴍ</p>
        </div>
        <div className="flex gap-2 text-[11px] mono">
          <a href="/dashboard" className="cyber-pill">◎ ᴅᴀsʜʙᴏᴀʀᴅ</a>
          <a href="/dashboard/chat" className="cyber-pill">◍ ᴡᴇʙ ᴄʜᴀᴛ</a>
          <span className="cyber-pill" style={{ color: "#10b981", borderColor: "#143d2a" }}>● ʟɪᴠᴇ</span>
        </div>
      </header>

      <div className="mt-6 grid lg:grid-cols-[1.15fr_0.85fr] gap-4">
        {/* Editor */}
        <section className="cyber-border rounded-2xl p-5">
          <h2 className="text-[11px] tracking-[0.12em] font-bold">◎ ᴄᴏᴍᴘᴏsᴇ ◎</h2>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-[11px] text-zinc-400 mono">ᴄʜᴀɴɴᴇʟ / ᴄʜᴀᴛ ɪᴅ</label>
              <div className="mt-1 flex gap-2">
                <input value={channel} onChange={e => setChannel(e.target.value)} placeholder="@YourChannel or -100123…" className="flex-1 cyber-border rounded-xl px-4 py-3 text-[12px] mono outline-none bg-[#0f0f10] border-[#1e1e22]" />
                <select value={parseMode} onChange={e => setParseMode(e.target.value as any)} className="cyber-border rounded-xl px-3 text-[11px] bg-[#0f0f10] mono">
                  <option>HTML</option>
                  <option>Markdown</option>
                </select>
              </div>
              <p className="text-[10px] text-zinc-600 mono mt-1">Bot must be admin in channel. IDs like <code>-100123…</code> work too.</p>
            </div>

            <div>
              <label className="text-[11px] text-zinc-400 mono">ᴍᴇssᴀɢᴇ • sᴜᴘᴘᴏʀᴛs HTML</label>
              <textarea value={text} onChange={e => setText(e.target.value)} rows={10} placeholder={`◍ Vɪᴅᴇʟ ⫶ ᴀɴɴᴏᴜɴᴄᴇᴍᴇɴᴛ 𖦹\n\n⬪ <b>Bold</b> • <i>italic</i> • <code>code</code>\n⫶ <a href="https://t.me/Videl0Bot">Link</a>\n◎ More…`} className="mt-1 w-full cyber-border rounded-xl px-4 py-3 text-[12px] mono outline-none bg-[#0f0f10] border-[#1e1e22] min-h-[180px]" />
              <div className="mt-2 flex flex-wrap gap-1 text-[10px] mono">
                {(["<b>bold</b>", "<i>italic</i>", "<code>code</code>", `<a href="">link</a>`, "◍", "⬪", "⫶", "◎", "⬢", "𖦹", "⦿"] as const).map(tag => (
                  <button key={tag} onClick={() => setText(v => v + (tag.startsWith("<") ? tag + " " : tag + " "))} className="cyber-border rounded-full px-3 py-1 text-zinc-400 hover:text-white">{tag}</button>
                ))}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-zinc-400 mono">ᴍᴇᴅɪᴀ ᴜʀʟ (ᴏᴘᴛɪᴏɴᴀʟ)</label>
                <input value={mediaUrl} onChange={e => setMediaUrl(e.target.value)} placeholder="https://…/image.jpg" className="mt-1 w-full cyber-border rounded-xl px-4 py-3 text-[11px] mono outline-none bg-[#0f0f10]" />
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 mono">ɪɴʟɪɴᴇ ʙᴜᴛᴛᴏɴs JSON (ᴏᴘᴛɪᴏɴᴀʟ)</label>
                <input value={buttons} onChange={e => setButtons(e.target.value)} placeholder='[{"text":"Open","url":"https://t.me/Videl0Bot"}]' className="mt-1 w-full cyber-border rounded-xl px-4 py-3 text-[11px] mono outline-none bg-[#0f0f10]" />
              </div>
            </div>

            {result && <div className="cyber-border rounded-xl p-3 text-[11px] mono" style={{ borderColor: result.startsWith("✅") ? "#143d2a" : result.startsWith("⚠️") ? "#422006" : "#2a1a1a", color: result.startsWith("✅") ? "#10b981" : result.startsWith("⚠️") ? "#f59e0b" : "#f87171" }}>{result}</div>}

            <div className="flex gap-2">
              <button onClick={sendPost} disabled={sending} className="flex-1 rounded-xl bg-white text-black px-5 py-3 text-[12px] font-bold uppercase tracking-wide disabled:opacity-50">
                {sending ? "⬪ sᴇɴᴅɪɴɢ…" : "⬪ ᴘᴏsᴛ ᴛᴏ ᴄʜᴀɴɴᴇʟ ➪"}
              </button>
              <button onClick={() => setPreview(v => !v)} className="cyber-border rounded-xl px-5 py-3 text-[11px] mono">{preview ? "◎ ʜɪᴅᴇ ᴘʀᴇᴠɪᴇᴡ" : "◍ ᴘʀᴇᴠɪᴇᴡ"}</button>
            </div>

            <div className="cyber-border rounded-xl p-3 bg-[#0f0f10]">
              <p className="text-[11px] font-bold tracking-wide">⬪ ǫᴜɪᴄᴋ ᴛᴇᴍᴘʟᴀᴛᴇs</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {samples.map(([label, body]) => (
                  <button key={label} onClick={() => setText(body)} className="cyber-border rounded-full px-3 py-1.5 text-[11px] mono text-zinc-400 hover:text-white">{label}</button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Preview */}
        <section className="space-y-4">
          <div className="cyber-border rounded-2xl p-5">
            <h3 className="text-[11px] tracking-[0.12em] font-bold">{preview ? "◍ ʟɪᴠᴇ ᴘʀᴇᴠɪᴇᴡ ◍" : "◎ ᴘʀᴇᴠɪᴇᴡ (ᴛɢ sᴛʏʟᴇ) ◎"}</h3>
            <div className="mt-4 rounded-2xl bg-[#111113] border border-[#1e1e22] p-4">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-violet-500 to-sky-500 flex items-center justify-center text-[11px] font-bold">V</div>
                <div>
                  <div className="text-[12px] font-semibold">Videl0 Channel</div>
                  <div className="text-[11px] text-zinc-500 mono">{channel || "@channel"} • Bot API 10.3</div>
                </div>
                <span className="ml-auto cyber-pill" style={{ color: "#10b981", borderColor: "#143d2a" }}>● ᴄʏʙᴇʀ ᴅᴀʀᴋ</span>
              </div>
              {mediaUrl && <img src={mediaUrl} alt="media" className="mt-3 w-full h-40 object-cover rounded-xl border border-[#1e1e22]" onError={e => ((e.target as HTMLImageElement).style.display = "none")} />}
              <div className="mt-3 text-[13px] leading-6 whitespace-pre-wrap break-words" dangerouslySetInnerHTML={{ __html: text ? text.replace(/<br\/?>/g, "<br/>").replace(/\n/g, "<br/>") : "<span class='text-zinc-600 mono text-[11px]'>Your message preview will appear here…</span>" }} />
              <div className="mt-3 flex flex-wrap gap-2">
                {(buttons ? (() => { try { return JSON.parse(buttons); } catch { return []; } })() : [{ text: "⬪ Open Bot", url: "https://t.me/Videl0Bot" }, { text: "◎ Support", url: "https://t.me/VidelSupport" }]).map((b: any, i: number) => (
                  <a key={i} href={b.url} target="_blank" className="cyber-border rounded-full px-4 py-1.5 text-[11px] mono">{b.text}</a>
                ))}
              </div>
              <div className="mt-3 text-[10px] text-zinc-600 mono">◍ Vɪᴅᴇʟ • kurigram • pytgcalls • richgram — preview only</div>
            </div>
            <p className="mt-3 text-[10px] text-zinc-600 mono">Supports full HTML: &lt;b&gt; &lt;i&gt; &lt;code&gt; &lt;pre&gt; &lt;a href=&quot;…&quot;&gt;. Buttons = JSON array: <code>{`[{"text":"Label","url":"https://…"}]`}</code></p>
          </div>

          <div className="cyber-border rounded-2xl p-5">
            <h3 className="text-[11px] tracking-[0.12em] font-bold">⬢ ᴛɪᴘs ⬢</h3>
            <ul className="mt-3 space-y-2 text-[11px] text-zinc-400 mono leading-5">
              <li>• Add bot as <b>admin</b> to channel with <i>Post messages</i> right.</li>
              <li>• For private channel, use ID: <code>-100…</code> (get via @userinfobot).</li>
              <li>• Media URL = direct image/gif. Leave empty for text-only.</li>
              <li>• Web chat at <a href="/dashboard/chat" className="text-white underline">/dashboard/chat</a> sends as bot to any <code>chat_id</code>.</li>
            </ul>
          </div>
        </section>
      </div>

      <footer className="mt-8 text-center text-[10px] text-zinc-600 mono">ᴍᴀᴅᴇ ᴡɪᴛʜ ◍ ʙʏ Beasgohan-code ⫶ Vercel + Bot API 10.3 + Richgram</footer>
    </main>
  );
}
