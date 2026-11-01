"use client";

import { Check, Circle } from "lucide-react";

type Item = { id: string; label: string; complete: boolean; detail: string };

export default function GroupSetupChecklist({ items }: { items: Item[] }) {
  const completed = items.filter((item) => item.complete).length;
  return (
    <section aria-labelledby="group-setup-checklist" className="mb-4 rounded-2xl border border-white/10 bg-white/[0.025] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="group-setup-checklist" className="text-sm font-semibold text-white">Admin setup checklist</h3>
        <span className="text-xs text-white/55">{completed} of {items.length} checks complete</span>
      </div>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.id} className="flex gap-2.5 rounded-xl bg-black/15 p-3">
            <span aria-hidden="true" className={item.complete ? "mt-0.5 text-emerald-300" : "mt-0.5 text-white/35"}>
              {item.complete ? <Check size={15} /> : <Circle size={15} />}
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium text-white/90">{item.label}</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-white/50">{item.complete ? "Ready" : item.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
