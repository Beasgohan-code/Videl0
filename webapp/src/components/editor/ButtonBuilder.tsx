"use client";
import { useState } from "react";
import { BUTTON_STYLES, buttonClasses, parseButtons, type ButtonStyle, type PostButton, type ButtonRow } from "@/lib/post-buttons";
export type Btn = PostButton;
export type BtnRow = ButtonRow;
export function ButtonBuilder({
  value,
  onChange,
}: {
  value: BtnRow[];
  onChange: (v: BtnRow[]) => void;
}) {
  const [draftText, setDraftText] = useState("");
  const [draftUrl, setDraftUrl] = useState("");
  const [editing,setEditing]=useState<[number,number]|null>(null);
  const [error, setError] = useState("");
  const [action,setAction]=useState("link");
  const [style,setStyle]=useState<ButtonStyle>("primary");
  const [iconId,setIconId]=useState("");
  function add(toLastRow: boolean) {
    const text = draftText.trim(),
      url = draftUrl.trim();
    if (!text || !url) {
      setError("Add a button label and action value.");
      return;
    }
    if (text.length > 64) { setError("Labels allow 64 characters."); return; }
    if (action === "copy" && draftUrl.length > 256) { setError("Copy buttons allow up to 256 characters."); return; }
    const raw = {text,url:action === "link" ? url : "",...(action === "copy" ? {copyText:draftUrl} : {}),style,iconId};
    const valid=parseButtons([[raw]])[0]?.[0];
    if(!valid){setError("Use an HTTPS URL without credentials, or non-empty copy text.");return}
    if(iconId && valid.iconId !== iconId){setError("Custom emoji ID must be a positive 64-bit decimal ID.");return}
    if (!editing && value.length >= 8 && !toLastRow) {
      setError("Telegram supports up to 8 inline keyboard rows.");
      return;
    }
    const item = valid;
    let next: BtnRow[];
    if (editing) {
      next=value.map((row,ri)=>row.map((button,ci)=>ri===editing[0]&&ci===editing[1]?item:button));
    } else if (toLastRow && value.length && value[value.length - 1].length < 8) {
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
    setEditing(null);
    setDraftText("");
    setDraftUrl("");
    setError("");
  }
  function remove(rowIndex: number, columnIndex?: number) {
    setEditing(null);
    if (columnIndex === undefined) {
      onChange(value.filter((_, i) => i !== rowIndex));
      return;
    }
    const next = value.map((row) => [...row]);
    next[rowIndex].splice(columnIndex, 1);
    onChange(next.filter((row) => row.length));
  }
  function move(rowIndex: number, delta: -1 | 1) {
    setEditing(null);
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
          <h2 className="font-semibold">Rich Telegram buttons</h2>
          <p className="mt-1 ios-caption">
            Choose native colors, link or copy actions, and optional custom emoji IDs. Older clients may render standard buttons.
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
                  className={`inline-flex max-w-full items-center gap-2 rounded-lg px-3 py-2 text-xs ${buttonClasses[button.style || "default"]}`}
                >
                  <button type="button" aria-label={`Edit ${button.text}`} className="max-w-[130px] truncate underline decoration-white/30 underline-offset-4" onClick={()=>{setEditing([ri,ci]);setDraftText(button.text);setDraftUrl(button.copyText||button.url);setAction(button.copyText?"copy":"link");setStyle(button.style||"default");setIconId(button.iconId||"");setError("")}}>{button.text}</button>
                  <span className="hidden max-w-[180px] truncate text-blue-100/45 sm:inline">
                    {button.copyText ? `Copy: ${button.copyText}` : button.url}
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
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs">Action<select aria-label="Button action" className="ios-input mt-2" value={action} onChange={e=>{setAction(e.target.value);setDraftUrl("")}}><option value="link">Open HTTPS link</option><option value="copy">Copy text</option></select></label>
        <label className="text-xs">Color<select aria-label="Button color" className="ios-input mt-2" value={style} onChange={e=>setStyle(e.target.value as ButtonStyle)}>{BUTTON_STYLES.map(s=><option key={s} value={s}>{s}</option>)}</select></label>
        <label className="text-xs">Custom emoji ID (optional)<input aria-label="Button custom emoji ID" className="ios-input mt-2" value={iconId} maxLength={19} onChange={e=>setIconId(e.target.value)} inputMode="numeric" placeholder="Telegram eligibility required"/></label>
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
          maxLength={action === "link" ? 2048 : 256}
          type={action === "link" ? "url" : "text"}
          onChange={(e) => setDraftUrl(e.target.value)}
          placeholder={action === "link" ? "https://example.com" : "Text to copy"}
          className="ios-input"
        />
        <button
          type="button"
          onClick={() => add(false)}
          className="ios-btn ios-btn-primary text-sm"
        >
          {editing ? "Save button" : "+ Row"}
        </button>
        <button
          type="button"
          onClick={() => editing ? (setEditing(null),setDraftText(""),setDraftUrl(""),setError("")) : add(true)}
          className="ios-btn ios-btn-glass text-sm"
        >
          {editing ? "Cancel edit" : "+ Column"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-amber-200">
          {error}
        </p>
      )}
      <p className="ios-caption">
        Maximum 8 rows and 8 buttons per row. Preview colors approximate Telegram. Emoji IDs do not bypass Premium eligibility.
      </p>
    </section>
  );
}
