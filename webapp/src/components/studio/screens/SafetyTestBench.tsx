"use client";

import { useState, type FormEvent } from "react";
import { FlaskConical, Info, ShieldCheck } from "lucide-react";
import type { FilterRow, GroupSettings } from "@/lib/group-admin";
import { safetyRuleLabel, simulateSafety, type SampleKind, type SampleSender, type SafetyPreview } from "@/lib/safety-simulation";

const SAMPLE_KINDS: { value: SampleKind; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "link", label: "Link" },
  { value: "forward", label: "Forward" },
  { value: "photo", label: "Photo" },
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "voice", label: "Voice note" },
  { value: "document", label: "Document" },
  { value: "sticker", label: "Sticker" },
  { value: "animation", label: "GIF / animation" },
  { value: "poll", label: "Poll" },
  { value: "mention", label: "Mention" },
  { value: "contact", label: "Contact" },
  { value: "location", label: "Location" },
  { value: "game", label: "Game" },
  { value: "inline", label: "Inline bot" },
  { value: "bot", label: "Message from a bot" },
];

export default function SafetyTestBench({ settings, filters }: { settings: GroupSettings; filters: FilterRow[] }) {
  const [message, setMessage] = useState("Check this link https://example.com");
  const [kind, setKind] = useState<SampleKind>("text");
  const [sender, setSender] = useState<SampleSender>("member");
  const [preview, setPreview] = useState<SafetyPreview | null>(null);

  function run(event: FormEvent) {
    event.preventDefault();
    setPreview(simulateSafety(settings, filters, message, kind, sender));
  }

  function clearPreview() { setPreview(null); }

  return (
    <section className="mt-4 rounded-2xl border border-cyan-200/15 bg-[linear-gradient(135deg,rgba(34,211,238,.06),rgba(255,255,255,.025))] p-4 sm:p-5" aria-labelledby="safety-bench-title">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-cyan-200/15 bg-cyan-200/[0.08] text-cyan-100"><FlaskConical size={17} /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 id="safety-bench-title" className="text-sm font-semibold">Protection Test Bench</h3>
            <span className="ios-pill text-[9px]">Preview only</span>
          </div>
          <p className="ios-caption mt-1">Try a sample before changing this group’s protection. Nothing is sent, deleted, or saved.</p>
        </div>
      </div>

      <form onSubmit={run} className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_170px_150px]">
        <label className="block text-xs text-[var(--ios-label-secondary)]">
          Sample text
          <input
            aria-label="Sample message text"
            value={message}
            maxLength={500}
            onChange={(event) => { setMessage(event.target.value); clearPreview(); }}
            className="ios-input mt-1.5 text-sm"
            placeholder="Type example text or a URL…"
          />
        </label>
        <label className="block text-xs text-[var(--ios-label-secondary)]">
          Content
          <select aria-label="Sample content type" value={kind} onChange={(event) => { setKind(event.target.value as SampleKind); clearPreview(); }} className="ios-input mt-1.5 text-sm">
            {SAMPLE_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="block text-xs text-[var(--ios-label-secondary)]">
          Sender
          <select aria-label="Sample sender role" value={sender} onChange={(event) => { setSender(event.target.value as SampleSender); clearPreview(); }} className="ios-input mt-1.5 text-sm">
            <option value="member">Regular member</option>
            <option value="admin">Group admin</option>
            <option value="approved">Approved member</option>
          </select>
        </label>
        <button type="submit" className="ios-btn ios-btn-primary justify-center text-xs sm:col-span-3 sm:justify-self-start">
          <FlaskConical size={14} /> Test this sample
        </button>
      </form>

      {preview && (
        <div className="mt-3 rounded-xl border border-white/[0.08] bg-black/15 p-3" role="status" aria-live="polite">
          {preview.exemptFromLocks ? (
            <p className="flex items-start gap-2 text-sm text-emerald-100"><ShieldCheck size={16} className="mt-0.5 shrink-0" /> This sender is exempt from content locks.</p>
          ) : preview.blockedBy ? (
            <p className="flex items-start gap-2 text-sm text-amber-100"><ShieldCheck size={16} className="mt-0.5 shrink-0" /> This sample would be deleted by the <b>{safetyRuleLabel(preview.blockedBy)}</b> lock.</p>
          ) : (
            <p className="flex items-start gap-2 text-sm text-emerald-100"><ShieldCheck size={16} className="mt-0.5 shrink-0" /> This sample would pass the configured content-lock checks.</p>
          )}
          {preview.autoReply && <p className="mt-2 border-t border-white/[0.07] pt-2 text-xs text-cyan-100/80">A matching auto-answer would also reply: “{preview.autoReply.slice(0, 180)}”</p>}
          <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-4 text-white/40"><Info size={12} className="mt-0.5 shrink-0" /> Preview follows Videl’s lock priority and admin/approved exemptions. It can’t model anti-flood history, quiet-hour timing, Telegram entities, or permissions.</p>
        </div>
      )}
    </section>
  );
}
