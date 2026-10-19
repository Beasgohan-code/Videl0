"use client";
import { useState } from "react";

export type Btn = { text: string; url: string; color: string; style?: string };
export type BtnRow = Btn[];

const COLOR_PRESETS: Record<string, { label: string; bg: string; fg: string; border: string }> = {
  primary: { label: "Blue", bg: "#0A84FF", fg: "#fff", border: "transparent" },
  success: { label: "Green", bg: "#30D158", fg: "#fff", border: "transparent" },
  danger:  { label: "Red", bg: "#FF453A", fg: "#fff", border: "transparent" },
  warn:    { label: "Orange", bg: "#FF9F0A", fg: "#fff", border: "transparent" },
  ghost:   { label: "Ghost", bg: "rgba(120,128,128,0.14)", fg: "#fff", border: "rgba(255,255,255,0.14)" },
  black:   { label: "Black", bg: "#000", fg: "#fff", border: "#222" },
  pink:    { label: "Pink", bg: "#FF2D55", fg: "#fff", border: "transparent" },
  indigo:  { label: "Indigo", bg: "#5856D6", fg: "#fff", border: "transparent" },
};

export function ButtonBuilder({ value, onChange }: { value: BtnRow[]; onChange: (v: BtnRow[]) => void }) {
  const [draftText, setDraftText] = useState("");
  const [draftUrl, setDraftUrl] = useState("");
  const [draftColor, setDraftColor] = useState("primary");

  function add() {
    if (!draftText.trim() || !draftUrl.trim()) return;
    // add as new row (1 button per row default)
    const next = [...value, [{ text: draftText.trim(), url: draftUrl.trim(), color: draftColor }]];
    onChange(next);
    setDraftText("");
    setDraftUrl("");
  }

  function addToLastRow() {
    if (!draftText.trim() || !draftUrl.trim() || value.length === 0) return add();
    const next = [...value];
    next[next.length - 1] = [...next[next.length - 1], { text: draftText.trim(), url: draftUrl.trim(), color: draftColor }];
    onChange(next);
    setDraftText("");
    setDraftUrl("");
  }

  function remove(rowIdx: number, colIdx?: number) {
    if (colIdx === undefined) {
      onChange(value.filter((_, i) => i !== rowIdx));
    } else {
      const next = [...value];
      next[rowIdx] = next[rowIdx].filter((_, j) => j !== colIdx);
      if (next[rowIdx].length === 0) next.splice(rowIdx, 1);
      onChange(next);
    }
  }

  function moveRow(idx: number, dir: -1 | 1) {
    const next = [...value];
    const j = idx + dir;
    if (j < 0 || j >= next.length) return;
    [next[idx], next[j]] = [next[j], next[idx]];
    onChange(next);
  }

  return (
    <div className="ios-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="ios-headline text-[15px]">⬢ Buttons</h3>
        <span className="ios-caption">{value.length} rows • {value.flat().length} buttons</span>
      </div>

      {/* Existing rows */}
      <div className="space-y-2">
        {value.length === 0 ? (
          <p className="ios-caption py-2">No buttons yet — add below. Example: “Open Bot” → https://t.me/Videl0Bot</p>
        ) : (
          value.map((row, ri) => (
            <div key={ri} className="flex flex-wrap gap-2 p-2 rounded-[12px] bg-[var(--ios-fill-secondary)] border border-[var(--ios-border)]">
              <span className="ios-caption2 mr-2 py-2">R{ri + 1}</span>
              {row.map((b, ci) => {
                const c = COLOR_PRESETS[b.color] || COLOR_PRESETS.primary;
                return (
                  <span key={ci} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-semibold border" style={{ background: c.bg, color: c.fg, borderColor: c.border }}>
                    {b.text} <span className="opacity-60 hidden sm:inline truncate max-w-[120px]">{b.url}</span>
                    <button onClick={() => remove(ri, ci)} className="ml-1 h-5 w-5 rounded-full bg-black/20 flex items-center justify-center text-[10px]">×</button>
                  </span>
                );
              })}
              <div className="ml-auto flex gap-1">
                <button onClick={() => moveRow(ri, -1)} className="ios-pill text-[10px]">↑</button>
                <button onClick={() => moveRow(ri, 1)} className="ios-pill text-[10px]">↓</button>
                <button onClick={() => remove(ri)} className="ios-pill text-[10px]">Del row</button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Draft */}
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
        <input value={draftText} onChange={e => setDraftText(e.target.value)} placeholder="Label e.g. ⬪ Open Bot" className="ios-input" />
        <input value={draftUrl} onChange={e => setDraftUrl(e.target.value)} placeholder="https://t.me/… or https://…" className="ios-input" />
        <div className="flex gap-2">
          <button onClick={add} className="ios-btn ios-btn-primary flex-1 sm:flex-none">+ Row</button>
          <button onClick={addToLastRow} className="ios-btn ios-btn-glass">+ Col</button>
        </div>
      </div>

      {/* Color picker */}
      <div>
        <p className="ios-caption mb-2">Colour — affects preview pill (Telegram shows blue, we preserve colour for webapp + richgram)</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(COLOR_PRESETS).map(([k, v]) => (
            <button
              key={k}
              onClick={() => setDraftColor(k)}
              className={`px-3 py-2 rounded-full text-[12px] font-semibold border transition ${draftColor === k ? "ring-2 ring-white" : ""}`}
              style={{ background: v.bg, color: v.fg, borderColor: v.border }}
            >
              {v.label}
            </button>
          ))}
        </div>
        <p className="ios-caption mt-2">Tip: “+ Row” = new line of buttons, “+ Col” = side-by-side on same row (max 8 per row in Telegram).</p>
      </div>

      {/* Quick presets */}
      <div className="flex flex-wrap gap-2">
        {[
          ["⬪ Open Bot", "https://t.me/Videl0Bot"],
          ["◎ Support", "https://t.me/VidelSupport"],
          ["⬢ GitHub", "https://github.com/Beasgohan-code/Videl0"],
        ].map(([t, u]) => (
          <button key={t} onClick={() => { setDraftText(t); setDraftUrl(u); }} className="ios-pill">{t}</button>
        ))}
      </div>

      {/* JSON fallback */}
      <details className="rounded-[12px] bg-[var(--ios-fill-secondary)] p-3">
        <summary className="ios-caption cursor-pointer">Advanced — JSON inline_keyboard</summary>
        <pre className="mt-2 text-[11px] leading-relaxed whitespace-pre-wrap break-all mono p-3 bg-black/30 rounded-[10px]">{JSON.stringify(value, null, 2)}</pre>
      </details>
    </div>
  );
}
