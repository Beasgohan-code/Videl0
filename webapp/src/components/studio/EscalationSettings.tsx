"use client";

import type { Escalation } from "@/lib/group-admin";

type Props = {
  value: Escalation | undefined;
  disabled?: boolean;
  onChange: (patch: Partial<Escalation>) => void;
};

const LADDERS: Record<string, string[]> = {
  single: [],
  "mute-kick-ban": ["mute", "kick", "ban"],
  "mute-ban": ["mute", "ban"],
  "kick-ban": ["kick", "ban"],
  "mute-kick": ["mute", "kick"],
};

function ladderKey(ladder: Escalation["ladder"]): string {
  const key = (ladder || []).join("-");
  return Object.entries(LADDERS).find(([, steps]) => steps.join("-") === key)?.[0] || "single";
}

export function EscalationSettings({ value, disabled = false, onChange }: Props) {
  const current = value || { enabled: true, action: "ban" as const, mute_hours: 6, decay_days: 0, ladder: [], review_severe: false };
  return <div className="space-y-3">
    <label className="flex items-center justify-between gap-3 rounded-xl bg-white/[.03] p-3">
      <span><span className="block text-sm font-medium">Enable warning escalation</span><span className="ios-caption">Apply the selected step each time the warning limit is reached.</span></span>
      <input type="checkbox" checked={current.enabled} disabled={disabled} onChange={(event) => onChange({ enabled: event.target.checked })} className="h-4 w-4 accent-indigo-400" />
    </label>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="text-xs text-indigo-100/55">Escalation sequence
        <select value={ladderKey(current.ladder)} disabled={disabled} onChange={(event) => onChange({ ladder: LADDERS[event.target.value] as Escalation["ladder"] })} className="ios-input mt-1 block w-full">
          <option value="single">Repeat one action</option><option value="mute-kick-ban">Mute → Kick → Ban</option><option value="mute-ban">Mute → Ban</option><option value="kick-ban">Kick → Ban</option><option value="mute-kick">Mute → Kick</option>
        </select>
      </label>
      <label className="text-xs text-indigo-100/55">Single action (when sequence is off)
        <select value={current.action} disabled={disabled || ladderKey(current.ladder) !== "single"} onChange={(event) => onChange({ action: event.target.value as Escalation["action"] })} className="ios-input mt-1 block w-full">
          <option value="none">No automatic action</option><option value="mute">Mute</option><option value="kick">Kick</option><option value="ban">Ban</option>
        </select>
      </label>
      <label className="text-xs text-indigo-100/55">Mute duration (hours)
        <input type="number" min={1} max={168} defaultValue={current.mute_hours} disabled={disabled} onBlur={(event) => onChange({ mute_hours: Math.max(1, Math.min(168, Number(event.target.value) || 1)) })} className="ios-input mt-1 block w-full" />
      </label>
      <label className="text-xs text-indigo-100/55">Warning decay (days; 0 keeps warnings)
        <input type="number" min={0} max={365} defaultValue={current.decay_days || 0} disabled={disabled} onBlur={(event) => onChange({ decay_days: Math.max(0, Math.min(365, Number(event.target.value) || 0)) })} className="ios-input mt-1 block w-full" />
      </label>
    </div>
    <label className="flex items-start gap-2 rounded-xl border border-amber-300/15 bg-amber-300/[.04] p-3 text-xs text-indigo-50/75">
      <input type="checkbox" checked={Boolean(current.review_severe)} disabled={disabled} onChange={(event) => onChange({ review_severe: event.target.checked })} className="mt-0.5 h-4 w-4 shrink-0 accent-amber-300" />
      <span><strong className="font-semibold text-amber-100">Require admin review before kick or ban.</strong> Severe rungs wait in the member’s Cases timeline. Mutes can still apply automatically; approval requires Telegram’s Restrict members permission.</span>
    </label>
  </div>;
}
