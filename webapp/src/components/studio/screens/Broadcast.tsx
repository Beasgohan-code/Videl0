"use client";
import { useEffect, useRef, useState } from "react";
import { Eye, PencilLine, Send, Users, Megaphone } from "lucide-react";
import { previewHtml } from "@/lib/telegram-format";
import type { BroadcastButton } from "@/lib/broadcast";
import { BusyLabel, Callout, PageHeader } from "../ui";

const audiences = [
  { value: "chats", label: "Groups & channels" },
  { value: "users", label: "Users" },
  { value: "all", label: "Groups and users" },
] as const;

const LIMIT = 4096;

export default function Broadcast() {
  const sending = useRef(false);
  const previous = useRef("");
  const [text, setText] = useState("");
  const [images, setImages] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [buttons, setButtons] = useState<BroadcastButton[]>([]);
  const [scope, setScope] = useState<(typeof audiences)[number]["value"]>("chats");
  const [confirmed, setConfirmed] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const remaining = LIMIT - text.length;
  const nearLimit = remaining <= 200;
  useEffect(() => {
    const urls = images.map((image) => URL.createObjectURL(image));
    setImagePreviews(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [images]);

  async function send() {
    if (sending.current || !confirmed || (!text.trim() && images.length === 0) || (images.length > 1 && buttons.length > 0)) return;
    const fingerprint = JSON.stringify([scope, text, buttons, images.map((image) => [image.name, image.size, image.lastModified])]);
    if (
      previous.current === fingerprint &&
      !window.confirm("This exact broadcast already completed. Send it to the audience again?")
    )
      return;
    sending.current = true;
    setBusy(true);
    setResult(null);
    try {
      let requestBody: BodyInit;
      const headers: Record<string, string> = {};
      if (images.length > 0) {
        const form = new FormData();
        for (const image of images) form.append("images", image, image.name);
        form.set("text", text);
        form.set("scope", scope);
        form.set("buttons", JSON.stringify(buttons));
        requestBody = form;
      } else {
        headers["Content-Type"] = "application/json";
        requestBody = JSON.stringify({ text, scope, buttons });
      }
      const response = await fetch("/api/broadcast", { method: "POST", headers, body: requestBody });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Broadcast failed");
      previous.current = fingerprint;
      setResult({
        tone: "success",
        text: `Telegram confirmed ${data.sent} sent, ${data.failed} failed (${data.total} recipients).`,
      });
      setConfirmed(false);
    } catch (error) {
      setResult({
        tone: "danger",
        text: error instanceof Error ? error.message : "Broadcast failed",
      });
    } finally {
      sending.current = false;
      setBusy(false);
      setConfirmed(false);
    }
  }

  return (
    <main className="ios-page ios-page-narrow">
      <PageHeader
        eyebrow="Videl · Community reach"
        title="Broadcast"
        subtitle="Send one announcement to the recipients the bot has recorded."
      />
      <fieldset disabled={busy} className="ios-card ios-section min-w-0 space-y-5 p-5 sm:p-6" aria-busy={busy}>
        <div>
          <p className="text-sm font-medium" id="broadcast-audience">Audience</p>
          <div className="scroll-row mt-2 flex gap-2" role="group" aria-labelledby="broadcast-audience">
            {audiences.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={scope === option.value}
                onClick={() => {
                  setScope(option.value);
                  setConfirmed(false);
                  setPreviewOpen(false);
                }}
                className="ios-chip"
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="ios-caption mt-2 flex items-center gap-1.5">
            <Users size={13} aria-hidden /> Counted from chats and users the bot has served.
          </p>
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-3">
            <label className="text-sm font-medium" htmlFor="broadcast-text">Announcement</label>
            <span className={`mono text-[11px] ${nearLimit ? "text-amber-200" : "text-[var(--ios-label-tertiary)]"}`}>
              {text.length}/{LIMIT}
            </span>
          </div>
          <textarea
            id="broadcast-text"
            className="ios-input mt-2"
            rows={8}
            maxLength={LIMIT}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setConfirmed(false);
              setPreviewOpen(false);
            }}
            placeholder="Write your community update…"
          />
          <p className="ios-caption mt-2">Telegram HTML is supported. The preview is exactly what will be sent.</p>
          <label className="mt-4 block text-xs font-medium text-indigo-100/65">Optional image album (up to 10 JPEG, PNG or WebP images; 4 MB each, 8 MB total)
            <input className="ios-input mt-2" type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={(event) => { const selected = Array.from(event.target.files || []); setConfirmed(false); setPreviewOpen(false); const total = selected.reduce((sum, file) => sum + file.size, 0); if (selected.length > 10 || total > 8 * 1024 * 1024 || selected.some((file) => file.size > 4 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type))) { setImages([]); setResult({ tone: "danger", text: "Choose up to ten JPEG, PNG or WebP images, each under 4 MB and 8 MB total." }); event.currentTarget.value = ""; return; } setResult(null); setImages(selected); }} />
          </label>
          {images.length > 0 && <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">{images.map((file, index) => <div key={`${file.name}-${file.lastModified}-${index}`} className="relative rounded-xl border border-white/10 bg-white/[.03] p-2"><img src={imagePreviews[index]} alt={`Selected album image ${index + 1}`} className="h-24 w-full rounded-lg object-cover"/><p className="mt-1 truncate text-[10px] text-indigo-100/55">{index + 1}. {file.name}</p><button type="button" aria-label={`Remove image ${index + 1}`} onClick={() => { setImages((current) => current.filter((_, i) => i !== index)); setPreviewOpen(false); setConfirmed(false); }} className="mt-1 text-[10px] text-rose-200">Remove</button></div>)}</div>}
        </div>
        <section className="space-y-3" aria-label="Inline buttons">
          <div className="flex items-center justify-between gap-3"><div><h2 className="text-sm font-medium">Inline URL buttons</h2><p className="ios-caption mt-1">Optional. Up to eight secure HTTPS links.{images.length > 1 ? " Remove extra images or these buttons; Telegram albums do not support inline keyboards." : ""}</p></div><button type="button" disabled={buttons.length >= 8 || images.length > 1} onClick={() => { setButtons((current) => [...current, { text: "Visit link", url: "https://" }]); setPreviewOpen(false); setConfirmed(false); }} className="ios-btn ios-btn-glass text-xs">Add button</button></div>
          {buttons.map((button, index) => <div key={index} className="grid gap-2 rounded-xl border border-white/10 bg-white/[.025] p-3 sm:grid-cols-[1fr_2fr_auto]"><label className="text-xs text-indigo-100/55">Button label<input className="ios-input mt-1" maxLength={64} value={button.text} onChange={(event) => { const value = event.target.value; setButtons((current) => current.map((item, i) => i === index ? { ...item, text: value } : item)); setPreviewOpen(false); setConfirmed(false); }} /></label><label className="text-xs text-indigo-100/55">HTTPS destination<input className="ios-input mt-1" type="url" maxLength={2048} value={button.url} onChange={(event) => { const value = event.target.value; setButtons((current) => current.map((item, i) => i === index ? { ...item, url: value } : item)); setPreviewOpen(false); setConfirmed(false); }} placeholder="https://example.com" /></label><button type="button" onClick={() => { setButtons((current) => current.filter((_, i) => i !== index)); setPreviewOpen(false); setConfirmed(false); }} className="ios-btn ios-btn-glass self-end text-xs">Remove</button></div>)}
        </section>
        {previewOpen ? (
          <section aria-label="Broadcast preview" className="rounded-2xl border border-indigo-300/20 bg-[#0a1020] p-4">
            <div className="flex items-center justify-between gap-3">
              <div><p className="text-xs font-semibold text-indigo-100">Preview before sending</p><p className="mt-1 text-[10px] text-indigo-100/45">Audience: {audiences.find((item) => item.value === scope)?.label}</p></div>
              <button type="button" onClick={() => { setPreviewOpen(false); setConfirmed(false); }} className="ios-btn ios-btn-glass text-xs"><PencilLine size={14} aria-hidden /> Edit</button>
            </div>
            {imagePreviews.length > 0 && <div className={`mt-3 grid gap-2 ${imagePreviews.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>{imagePreviews.map((src, index) => <img key={src} src={src} alt={`Broadcast album image ${index + 1}`} className="max-h-72 w-full rounded-xl object-contain" />)}</div>}
            <div className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-white" dangerouslySetInnerHTML={{ __html: previewHtml(text) }} />
            {buttons.length > 0 && <div className="mt-3 grid gap-2">{buttons.map((button, index) => <div key={index} className="rounded-lg border border-blue-300/15 bg-blue-400/10 px-3 py-2 text-center text-xs text-blue-100">{button.text || "Button"}</div>)}</div>}
          </section>
        ) : (
          <button type="button" className="ios-btn ios-btn-glass" disabled={(!text.trim() && images.length === 0) || (images.length > 1 && buttons.length > 0)} onClick={() => { setConfirmed(false); setPreviewOpen(true); }}><Eye size={16} aria-hidden /> Preview message</button>
        )}
        <Callout tone="info" title="This is a single request, not a campaign">
          Limited to the first 60 recipients. Do not retry a timed-out request without checking
          Telegram first — some recipients may already have received it.
        </Callout>
        {previewOpen && <label className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-sm text-indigo-50/80">
          <input
            type="checkbox"
            className="mt-1"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I confirm this sends real messages to the selected audience.
        </label>}
        <div className="flex flex-wrap items-center gap-3">
          <button
            className="ios-btn ios-btn-primary"
            disabled={!previewOpen || !confirmed || (!text.trim() && images.length === 0) || (images.length > 1 && buttons.length > 0) || busy}
            onClick={() => void send()}
          >
            <Send size={16} aria-hidden />
            {busy ? <BusyLabel label="Sending — please wait…" /> : "Send broadcast"}
          </button>
          <span className="ios-caption flex items-center gap-1.5">
            <Megaphone size={13} aria-hidden /> Messages come from your bot, not this browser.
          </span>
        </div>
        {result && <Callout tone={result.tone}>{result.text}</Callout>}
      </fieldset>
    </main>
  );
}
