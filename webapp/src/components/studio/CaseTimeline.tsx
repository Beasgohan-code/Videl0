"use client";

import { useState } from "react";
import { Check, FilePlus2, Loader2, X } from "lucide-react";
import type { MemberCase } from "@/lib/group-admin";

type Props = {
  cases: MemberCase[];
  disabled?: boolean;
  onAddNote: (userId: number, text: string) => Promise<boolean>;
  onReviewEscalation: (id: string, decision: "approve" | "reject") => Promise<boolean>;
};

export function CaseTimeline({ cases, disabled = false, onAddNote, onReviewEscalation }: Props) {
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [savingUser, setSavingUser] = useState<number | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  if (!cases.length) return <p className="rounded-xl border border-dashed border-white/10 p-5 text-center text-sm text-indigo-100/45">No case activity recorded yet. Reports, warnings and future moderator notes will appear here.</p>;

  return <div className="space-y-3">
    <p className="text-xs text-indigo-100/45">Warnings, reports, moderator actions and internal notes are grouped by member. Only this group’s admins can view them.</p>
    {cases.map((item) => (
      <article key={item.user_id} className="rounded-xl border border-white/[.08] bg-white/[.02] p-4">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-white">Member <code>{item.user_id}</code></h3>
          <span className="text-xs text-indigo-100/45">{item.event_count} events · {item.open_reports} open reports{item.latest ? ` · latest ${new Date(item.latest).toLocaleString()}` : ""}</span>
        </header>
        {(item.pending_escalations || []).map((pending) => (
          <div key={pending.id} className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/[.05] p-3">
            <p className="text-xs font-semibold text-amber-100">Pending review · proposed {pending.action} after {pending.warning_count} warnings</p>
            {pending.reason && <p className="mt-1 text-xs leading-5 text-amber-50/70">{pending.reason}</p>}
            <p className="mt-1 text-[10px] text-amber-100/40">Requested {pending.at ? new Date(pending.at).toLocaleString() : "recently"}. Approval applies the action; rejection records the decision without changing membership.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" disabled={disabled || reviewing !== null} onClick={async () => {
                if (!window.confirm(`Approve the proposed ${pending.action} for member ${item.user_id}?`)) return;
                setReviewing(pending.id); try { await onReviewEscalation(pending.id, "approve"); } finally { setReviewing(null); }
              }} className="ios-btn ios-btn-primary text-[11px] disabled:opacity-40"><Check size={13}/> Approve {pending.action}</button>
              <button type="button" disabled={disabled || reviewing !== null} onClick={async () => {
                setReviewing(pending.id); try { await onReviewEscalation(pending.id, "reject"); } finally { setReviewing(null); }
              }} className="ios-btn ios-btn-glass text-[11px] disabled:opacity-40"><X size={13}/> Reject</button>
            </div>
          </div>
        ))}
        <ol className="mt-3 space-y-2 border-l border-indigo-300/15 pl-3">
          {item.events.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute -left-[17px] top-1.5 h-1.5 w-1.5 rounded-full bg-indigo-300/60" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <strong className="text-xs text-indigo-50/80">{event.action.replaceAll("_", " ") || event.kind}</strong>
                <time className="text-[10px] text-indigo-100/35">{event.at ? new Date(event.at).toLocaleString() : "Time unavailable"}</time>
              </div>
              {event.detail && <p className="mt-0.5 break-words text-xs leading-5 text-indigo-100/55">{event.detail}</p>}
              {event.actor && <p className="mt-0.5 text-[10px] text-indigo-100/30">Admin ID {event.actor} · {event.source}</p>}
            </li>
          ))}
        </ol>
        <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={async (event) => {
          event.preventDefault(); const text = (drafts[item.user_id] || "").trim();
          if (!text || disabled || savingUser !== null) return;
          setSavingUser(item.user_id);
          try { if (await onAddNote(item.user_id, text)) setDrafts((current) => ({ ...current, [item.user_id]: "" })); }
          finally { setSavingUser(null); }
        }}>
          <input value={drafts[item.user_id] || ""} maxLength={600} onChange={(event) => setDrafts((current) => ({ ...current, [item.user_id]: event.target.value }))} placeholder="Add an internal moderator note" aria-label={`Internal note for member ${item.user_id}`} className="ios-input min-w-0 flex-1 text-xs" />
          <button type="submit" disabled={disabled || savingUser !== null || !(drafts[item.user_id] || "").trim()} className="ios-btn ios-btn-glass text-xs disabled:opacity-40">
            {savingUser === item.user_id ? <Loader2 size={13} className="animate-spin" /> : <FilePlus2 size={13} />} Add note
          </button>
        </form>
      </article>
    ))}
  </div>;
}
