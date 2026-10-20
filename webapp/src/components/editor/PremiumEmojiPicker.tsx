"use client";
import { useMemo, useState } from "react";
import { Search, Sparkles, Wand2, X } from "lucide-react";
import { PREMIUM_EMOJI, PREMIUM_GROUPS, isEmojiId, type PremiumEmoji } from "@/lib/premium-emoji";

/**
 * Premium emoji browser: real artwork from Telegram packs, grouped, searchable,
 * plus a manual ID field for any emoji copied out of a Telegram client.
 */
export function PremiumEmojiPicker({
  onInsert,
  onClose,
  compact = false,
}: {
  onInsert: (id: string, char: string, label: string) => void;
  onClose?: () => void;
  compact?: boolean;
}) {
  const [group, setGroup] = useState<PremiumEmoji["group"] | "All">("All");
  const [query, setQuery] = useState("");
  const [customId, setCustomId] = useState("");
  const [customChar, setCustomChar] = useState("✨");
  const [error, setError] = useState("");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return PREMIUM_EMOJI.filter(
      (item) =>
        (group === "All" || item.group === group) &&
        (!needle || `${item.label} ${item.char} ${item.id}`.toLowerCase().includes(needle)),
    );
  }, [group, query]);

  function addCustom() {
    if (!isEmojiId(customId)) {
      setError("Enter the 1–20 digit emoji ID from Telegram.");
      return;
    }
    onInsert(customId.trim(), customChar || "✨", "Custom emoji");
    setError("");
    setCustomId("");
  }

  return (
    <div
      className={`emoji-picker ${compact ? "emoji-picker-compact" : ""}`}
      role="group"
      aria-label="Premium emoji"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[.18em] text-violet-200/90">
          <Sparkles size={12} /> Premium emoji
        </p>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close premium emoji picker" className="rounded-full p-1 text-white/50 hover:bg-white/10 hover:text-white">
            <X size={14} />
          </button>
        )}
      </div>

      <label className="mt-2 flex items-center gap-2 rounded-lg bg-black/25 px-2.5 ring-1 ring-white/10 focus-within:ring-violet-400/40">
        <Search size={12} className="text-white/40" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find an emoji…"
          aria-label="Search premium emoji"
          className="w-full bg-transparent py-2 text-xs text-white/90 outline-none placeholder:text-white/30"
        />
      </label>

      <div className="mt-2 flex flex-wrap gap-1">
        {(["All", ...PREMIUM_GROUPS] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={group === value}
            onClick={() => setGroup(value)}
            className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition ${
              group === value ? "bg-violet-500/25 text-violet-100 ring-1 ring-violet-300/30" : "text-white/45 hover:bg-white/5 hover:text-white/80"
            }`}
          >
            {value}
          </button>
        ))}
      </div>

      <div className={`mt-2 grid gap-1.5 overflow-y-auto pr-1 ${compact ? "max-h-36 grid-cols-7" : "max-h-48 grid-cols-8"}`}>
        {visible.map((item) => (
          <button
            key={`${item.id}-${item.label}`}
            type="button"
            title={`${item.label} · ${item.id}`}
            aria-label={`Insert ${item.label} premium emoji`}
            onClick={() => onInsert(item.id, item.char, item.label)}
            className="group relative grid aspect-square place-items-center rounded-lg bg-white/[0.04] ring-1 ring-white/5 transition hover:bg-violet-500/15 hover:ring-violet-300/30"
          >
            <span className="tg-premium-emoji text-lg">
              {item.char}
              <span className="tg-emoji-art" aria-hidden="true" style={{ backgroundImage: `url('/api/premium-emoji?id=${item.id}')` }} />
            </span>
          </button>
        ))}
        {!visible.length && <p className="col-span-full py-4 text-center text-[11px] text-white/40">No emoji match that search.</p>}
      </div>

      <div className="mt-2 rounded-lg bg-black/25 p-2 ring-1 ring-white/10">
        <p className="text-[9px] font-semibold uppercase tracking-[.16em] text-white/40">Any emoji ID</p>
        <div className="mt-1.5 flex gap-1.5">
          <input
            value={customId}
            onChange={(event) => setCustomId(event.target.value.replace(/[^0-9]/g, "").slice(0, 20))}
            placeholder="5368324170671202286"
            aria-label="Premium emoji ID"
            inputMode="numeric"
            className="min-w-0 flex-1 rounded-md bg-white/5 px-2 py-1.5 font-mono text-[11px] text-white/85 outline-none placeholder:text-white/25"
          />
          <input
            value={customChar}
            onChange={(event) => setCustomChar([...event.target.value].slice(0, 2).join(""))}
            aria-label="Fallback character"
            className="w-10 rounded-md bg-white/5 px-1 py-1.5 text-center text-sm outline-none"
          />
          <button
            type="button"
            onClick={addCustom}
            aria-label="Insert emoji ID"
            className="rounded-md bg-violet-500/80 px-2 text-white transition hover:bg-violet-400"
          >
            <Wand2 size={13} />
          </button>
        </div>
        {error && (
          <p role="alert" className="mt-1.5 text-[10px] text-amber-200">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
