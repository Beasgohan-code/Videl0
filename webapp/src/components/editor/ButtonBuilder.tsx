"use client";
import { useState } from "react";
export type Btn = { text: string; url: string };
export type BtnRow = Btn[];
export function ButtonBuilder({
  value,
  onChange,
}: {
  value: BtnRow[];
  onChange: (v: BtnRow[]) => void;
}) {
  const [draftText, setDraftText] = useState("");
  const [draftUrl, setDraftUrl] = useState("");
  const [error, setError] = useState("");
  function add(toLastRow: boolean) {
    const text = draftText.trim(),
      url = draftUrl.trim();
    if (!text || !url) {
      setError("Add a button label and URL.");
      return;
    }
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      setError("Enter a valid HTTPS URL.");
      return;
    }
    if (parsed.protocol !== "https:") {
      setError("Telegram URL buttons must use HTTPS.");
      return;
    }
    if (text.length > 64 || url.length > 2048) {
      setError("Labels are limited to 64 characters; URLs to 2048.");
      return;
    }
    if (value.length >= 8 && !toLastRow) {
      setError("Telegram supports up to 8 inline keyboard rows.");
      return;
    }
    const item = { text, url };
    let next: BtnRow[];
    if (toLastRow && value.length && value[value.length - 1].length < 8) {
      next = value.map((row, i) =>
        i === value.length - 1 ? [...row, item] : row,
      );
    } else if (
      toLastRow &&
      value.length &&
      value[value.length - 1].length >= 8
    ) {
      setError("A Telegram button row can contain at most 8 buttons.");
      return;
    } else next = [...value, [item]];
    onChange(next);
    setDraftText("");
    setDraftUrl("");
    setError("");
  }
  function remove(rowIndex: number, columnIndex?: number) {
    if (columnIndex === undefined) {
      onChange(value.filter((_, i) => i !== rowIndex));
      return;
    }
    const next = value.map((row) => [...row]);
    next[rowIndex].splice(columnIndex, 1);
    onChange(next.filter((row) => row.length));
  }
  function move(rowIndex: number, delta: -1 | 1) {
    const next = [...value];
    const target = rowIndex + delta;
    if (target < 0 || target >= next.length) return;
    [next[rowIndex], next[target]] = [next[target], next[rowIndex]];
    onChange(next);
  }
  return (
    <section className="ios-card space-y-4 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Inline URL buttons</h2>
          <p className="mt-1 ios-caption">
            Telegram controls button color and style.
          </p>
        </div>
        <span className="ios-pill">{value.flat().length} buttons</span>
      </div>
      <div className="space-y-2">
        {value.length ? (
          value.map((row, ri) => (
            <div
              key={ri}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] p-2"
            >
              <span className="ios-caption2 px-2">Row {ri + 1}</span>
              {row.map((button, ci) => (
                <span
                  key={`${button.url}-${ci}`}
                  className="inline-flex max-w-full items-center gap-2 rounded-lg border border-blue-300/15 bg-blue-400/10 px-3 py-2 text-xs text-blue-100"
                >
                  <span className="max-w-[130px] truncate">{button.text}</span>
                  <span className="hidden max-w-[180px] truncate text-blue-100/45 sm:inline">
                    {button.url}
                  </span>
                  <button
                    type="button"
                    aria-label={`Remove ${button.text}`}
                    onClick={() => remove(ri, ci)}
                    className="text-blue-100/70 hover:text-white"
                  >
                    ×
                  </button>
                </span>
              ))}
              <span className="ml-auto flex gap-1">
                <button
                  type="button"
                  onClick={() => move(ri, -1)}
                  aria-label="Move row up"
                  className="ios-pill"
                >
                  ↑
                </button>
                <button
                  type="button"
                  onClick={() => move(ri, 1)}
                  aria-label="Move row down"
                  className="ios-pill"
                >
                  ↓
                </button>
                <button
                  type="button"
                  onClick={() => remove(ri)}
                  className="ios-pill"
                >
                  Remove row
                </button>
              </span>
            </div>
          ))
        ) : (
          <p className="rounded-xl bg-white/[0.025] p-3 text-sm text-[var(--ios-label-secondary)]">
            No buttons added. This is optional.
          </p>
        )}
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_1.4fr_auto_auto]">
        <input
          value={draftText}
          maxLength={64}
          onChange={(e) => setDraftText(e.target.value)}
          placeholder="Button label"
          className="ios-input"
        />
        <input
          value={draftUrl}
          maxLength={2048}
          type="url"
          onChange={(e) => setDraftUrl(e.target.value)}
          placeholder="https://example.com"
          className="ios-input"
        />
        <button
          type="button"
          onClick={() => add(false)}
          className="ios-btn ios-btn-primary text-sm"
        >
          + Row
        </button>
        <button
          type="button"
          onClick={() => add(true)}
          className="ios-btn ios-btn-glass text-sm"
        >
          + Column
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-amber-200">
          {error}
        </p>
      )}
      <p className="ios-caption">
        Maximum 8 rows and 8 buttons per row. HTTPS links only.
      </p>
    </section>
  );
}
