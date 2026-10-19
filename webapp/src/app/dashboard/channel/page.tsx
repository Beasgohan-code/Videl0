"use client";
import { useEffect, useState } from "react";
import { RichEditor } from "@/components/editor/RichEditor";
import { ButtonBuilder, BtnRow } from "@/components/editor/ButtonBuilder";
import { ChannelPreview } from "@/components/channel/Preview";
import { OwnerGate } from "@/components/auth/TelegramLogin";

export default function ChannelStudio() {
  const [channel, setChannel] = useState("@");
  const [text, setText] = useState("<b>◍ Vɪᴅᴇʟ ⫶ ᴜᴘᴅᴀᴛᴇ 𖦹</b>\n\n⬪ <b>New music engine shipped</b> ⫶ yt-dlp + aria2c\n⫶ <code>/song</code> — instant MP3 192k • <code>/vsong</code> — MP4 1080p\n◎ <code>/play</code> still streams to VC • queue + effects\n\n⬢ <i>Powered by kurigram + pytgcalls + richgram</i>");
  const [parseMode, setParseMode] = useState<"HTML" | "Markdown">("HTML");
  const [mediaUrl, setMediaUrl] = useState("");
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [buttons, setButtons] = useState<BtnRow[]>([[{ text: "⬪ Open Bot", url: "https://t.me/Videl0Bot", color: "primary" }]]);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [schedule, setSchedule] = useState("");
  const ownerId = parseInt(process.env.NEXT_PUBLIC_OWNER_ID || "0", 10);

  // Drafts
  const [drafts, setDrafts] = useState<any[]>([]);
  useEffect(() => {
    try { const d = localStorage.getItem("videl_drafts"); if (d) setDrafts(JSON.parse(d)); } catch {}
  }, []);
  function saveDraft() {
    const next = [{ id: Date.now(), channel, text: text.slice(0, 80), at: new Date().toLocaleString() }, ...drafts].slice(0, 10);
    setDrafts(next);
    localStorage.setItem("videl_drafts", JSON.stringify(next));
    setResult("💾 Draft saved");
  }

  async function sendPost() {
    if (!channel || channel === "@" || !text.trim()) { setResult("⚠️ Fill channel & text"); return; }
    setSending(true); setResult(null);
    const payload: any = { chat_id: channel.trim(), text, parse_mode: parseMode, media_url: mediaUrl.trim() || undefined, buttons: JSON.stringify(buttons) };
    // If file selected, we'd need upload — for now URL only; show note
    if (mediaFile) {
      setResult("⚠️ File upload preview only — use media URL for now. Dropbox/Supabase upload coming.");
    }
    try {
      const res = await fetch("/api/channel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const j = await res.json();
      if (j.ok) setResult(`✅ Sent — message_id ${j.message_id} • ${j.chat_id}`);
      else setResult(`❌ ${j.error || "Failed"}`);
    } catch (e: any) { setResult(`❌ ${String(e)}`); }
    setSending(false);
  }

  const inner = (
    <main className="mx-auto max-w-6xl py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="ios-title">Channel Studio</h1>
          <p className="ios-subheadline">Notion-like editor ⫶ colour buttons ⫶ live Telegram preview ⫶ drafts</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTheme(t => t === "dark" ? "light" : "dark")} className="ios-btn ios-btn-glass">{theme === "dark" ? "☀︎ Light" : "◍ Dark"} preview</button>
          <button onClick={saveDraft} className="ios-btn ios-btn-glass">💾 Draft</button>
        </div>
      </header>

      <div className="mt-6 grid lg:grid-cols-[1.2fr_0.8fr] gap-4">
        {/* Editor column */}
        <div className="space-y-4">
          <div className="ios-card p-4">
            <h3 className="ios-caption2">◎ Channel / Chat ID</h3>
            <div className="mt-3 flex gap-2">
              <input value={channel} onChange={e => setChannel(e.target.value)} placeholder="@YourChannel or -100123…" className="ios-input flex-1" />
              <select value={parseMode} onChange={e => setParseMode(e.target.value as any)} className="ios-input w-[120px]">
                <option>HTML</option><option>Markdown</option>
              </select>
            </div>
            <p className="ios-caption mt-2">Bot must be admin with <i>Post messages</i>. Private channel: <code>-100…</code></p>
            <div className="mt-3 flex gap-2">
              <input type="datetime-local" value={schedule} onChange={e => setSchedule(e.target.value)} className="ios-input flex-1" />
              <button onClick={() => schedule && setResult(`⏰ Scheduled for ${schedule} (requires Vercel Cron — saved as draft for now)`)} className="ios-btn ios-btn-glass">⏰ Schedule</button>
            </div>
          </div>

          <div>
            <h3 className="ios-caption2 mb-2">✎ Message — Pro editor</h3>
            <RichEditor value={text} onChange={setText} placeholder="Write your post…" />
          </div>

          <div className="ios-card p-4 space-y-3">
            <h3 className="ios-caption2">⬢ Media (optional)</h3>
            <input value={mediaUrl} onChange={e => setMediaUrl(e.target.value)} placeholder="https://…/image.jpg (or gif, short video)" className="ios-input" />
            <div className="flex items-center gap-2">
              <input type="file" accept="image/*" onChange={e => setMediaFile(e.target.files?.[0] || null)} className="text-[12px]" />
              <span className="ios-caption">or drag URL — file upload via Supabase coming</span>
            </div>
            {mediaUrl && <img src={mediaUrl} alt="" className="w-full h-36 object-cover rounded-[12px] border border-[var(--ios-border)]" onError={e => ((e.target as HTMLImageElement).style.display = "none")} />}
          </div>

          <ButtonBuilder value={buttons} onChange={setButtons} />

          {result && <div className={`p-3 rounded-[12px] text-[13px] border ${result.startsWith("✅") ? "bg-[rgba(48,209,88,0.12)] border-[rgba(48,209,88,0.2)] text-[#30D158]" : result.startsWith("⚠️") ? "bg-[rgba(255,159,10,0.12)] border-[rgba(255,159,10,0.2)] text-[#FF9F0A]" : "bg-[rgba(255,69,58,0.12)] border-[rgba(255,69,58,0.2)] text-[#FF453A]"}`}>{result}</div>}

          <div className="flex gap-2">
            <button onClick={sendPost} disabled={sending} className="ios-btn ios-btn-primary flex-1">{sending ? "⬪ Sending…" : "⬪ Post to Channel ➪"}</button>
            <button onClick={() => setText("")} className="ios-btn ios-btn-glass">Clear</button>
          </div>

          <div className="ios-card p-4">
            <h3 className="ios-caption2">💾 Drafts</h3>
            {drafts.length ? drafts.map(d => (
              <div key={d.id} className="ios-list-row">
                <div><div className="text-[13px] font-medium">{d.text}</div><div className="ios-caption">{d.channel} • {d.at}</div></div>
                <button onClick={() => { setChannel(d.channel); /* text reload would need full */ }} className="ios-pill">Restore</button>
              </div>
            )) : <p className="ios-caption mt-2">No drafts yet</p>}
          </div>

          <div className="ios-card p-4">
            <h3 className="ios-caption2">⬢ Quick templates</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                ["Announcement", "<b>◍ Vɪᴅᴇʟ ⫶ ᴜᴘᴅᴀᴛᴇ 𖦹</b>\n\n⬪ <b>Maintenance complete</b>"],
                ["Welcome", "<b>◍ Welcome ⫶ @Videl0Bot 𖦹</b>\n\n◎ Add to group → /start"],
                ["Giveaway", "<b>𖦹 Giveaway ⦿</b>\n\n⬪ Prize: <b>Premium x1</b>"],
                ["Music", "<b>⬪ Now Playing 𖦹</b>\n\n🎵 <i>Believer — Imagine Dragons</i>"],
              ].map(([k, v]) => (
                <button key={k} onClick={() => setText(v)} className="ios-pill">{k}</button>
              ))}
            </div>
          </div>
        </div>

        {/* Preview column — sticky */}
        <div className="space-y-4 lg:sticky lg:top-[72px] self-start">
          <div className="ios-card-elevated p-4">
            <h3 className="ios-caption2">◎ Live Preview — Telegram</h3>
            <div className="mt-3">
              <ChannelPreview channel={channel} text={text} mediaUrl={mediaUrl} buttons={buttons} theme={theme} />
            </div>
            <div className="mt-3 flex gap-2">
              <a href={`https://t.me/${(channel || "").replace("@","")}`} target="_blank" className="ios-btn ios-btn-glass flex-1 text-[13px]">Open channel</a>
              <button onClick={() => navigator.clipboard.writeText(text)} className="ios-btn ios-btn-glass">Copy HTML</button>
            </div>
          </div>

          <div className="ios-card p-4">
            <h3 className="ios-caption2">⬢ Tips</h3>
            <ul className="mt-2 space-y-2 ios-caption leading-5">
              <li>• Colour buttons show as <b>coloured pills</b> in preview; Telegram displays blue but your followers see the colour in webapp archive.</li>
              <li>• Drag schedule to post later — needs Vercel Cron (we save draft now).</li>
              <li>• Use <code>&lt;b&gt; &lt;i&gt; &lt;code&gt; &lt;pre&gt; &lt;a href&gt; &lt;blockquote&gt;</code> — exactly Telegram HTML.</li>
              <li>• File upload → auto to <code>downloads/</code> → Supabase coming.</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  );

  // Owner gate — if ownerId known
  if (ownerId) {
    return <OwnerGate ownerId={ownerId}>{inner}</OwnerGate>;
  }
  return inner;
}
