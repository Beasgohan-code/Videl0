"use client";
import { useRef } from "react";

type Props = {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
};

export function RichEditor({ value, onChange, placeholder }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function wrap(before: string, after: string, fallback = "") {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const sel = value.slice(start, end) || fallback;
    const next = value.slice(0, start) + before + sel + after + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + before.length + sel.length + after.length;
      el.setSelectionRange(pos, pos);
    });
  }

  function insertAtCursor(text: string) {
    const el = ref.current;
    if (!el) return onChange(value + text);
    const s = el.selectionStart ?? value.length;
    const e = el.selectionEnd ?? value.length;
    const next = value.slice(0, s) + text + value.slice(e);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(s + text.length, s + text.length);
    });
  }

  return (
    <div className="ios-card overflow-hidden">
      {/* Toolbar — iOS style */}
      <div className="flex flex-wrap gap-1.5 p-2 border-b border-[var(--ios-separator)] bg-[var(--ios-bg-subtle)]">
        <ToolbarBtn onClick={() => wrap("<b>", "</b>", "bold")} label="B" title="Bold" />
        <ToolbarBtn onClick={() => wrap("<i>", "</i>", "italic")} label="I" italic title="Italic" />
        <ToolbarBtn onClick={() => wrap("<u>", "</u>", "underline")} label="U" underline title="Underline" />
        <ToolbarBtn onClick={() => wrap("<s>", "</s>", "strike")} label="S" strike title="Strike" />
        <ToolbarBtn onClick={() => wrap('<span class="tg-spoiler">', "</span>", "spoiler")} label="◍" title="Spoiler" />
        <div className="w-px h-6 bg-[var(--ios-separator)] mx-1 self-center" />
        <ToolbarBtn onClick={() => insertAtCursor("\n<b>◍ Heading</b>\n")} label="H1" title="Heading" small />
        <ToolbarBtn onClick={() => wrap("<code>", "</code>", "code")} label="</>" title="Code" small />
        <ToolbarBtn onClick={() => wrap("<pre>", "</pre>", "block code")} label="≋" title="Pre" />
        <ToolbarBtn onClick={() => wrap('<a href="">', "</a>", "link")} label="🔗" title="Link" />
        <div className="w-px h-6 bg-[var(--ios-separator)] mx-1 self-center" />
        <ToolbarBtn onClick={() => wrap("<blockquote>", "</blockquote>", "quote")} label="❝" title="Quote" />
        <ToolbarBtn onClick={() => insertAtCursor("\n• ")} label="•" title="Bullet" />
        <ToolbarBtn onClick={() => insertAtCursor("\n1. ")} label="1." title="Ordered" small />
        <div className="w-px h-6 bg-[var(--ios-separator)] mx-1 self-center" />
        {["◍","⬪","⫶","◎","⬢","𖦹","⦿"].map(s => (
          <button key={s} onClick={() => insertAtCursor(s)} className="h-8 w-8 rounded-full bg-[var(--ios-card)] border border-[var(--ios-border)] flex items-center justify-center text-[13px] hover:bg-white hover:text-black transition">{s}</button>
        ))}
      </div>

      {/* Editor */}
      <div className="p-3">
        <textarea
          ref={ref}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder || "◍ Vɪᴅᴇʟ ⫶ ᴀɴɴᴏᴜɴᴄᴇᴍᴇɴᴛ 𖦹\n\n⬪ <b>Bold</b> • <i>italic</i> • <code>code</code> • <a href=\"https://t.me/Videl0Bot\">Link</a>\n⫶ <blockquote>Quote line</blockquote>\n◎ Bullet list\n• Clean formatting"}
          rows={12}
          className="w-full min-h-[220px] bg-transparent outline-none text-[15px] leading-6 placeholder:text-[var(--ios-label-tertiary)] resize-none"
          style={{ fieldSizing: "content" } as any}
        />
        <div className="mt-3 flex flex-wrap gap-2 ios-caption">
          <span>HTML supported: &lt;b&gt; &lt;i&gt; &lt;u&gt; &lt;s&gt; &lt;code&gt; &lt;pre&gt; &lt;a href&gt; &lt;blockquote&gt;</span>
          <span className="ml-auto">{value.length} chars</span>
        </div>
      </div>
    </div>
  );
}

function ToolbarBtn({ onClick, label, title, italic, underline, strike, small }: any) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`h-8 px-3 rounded-full bg-white text-black text-[12px] font-bold flex items-center justify-center hover:bg-zinc-100 active:scale-95 transition ${italic ? "italic" : ""} ${underline ? "underline" : ""} ${strike ? "line-through" : ""} ${small ? "text-[11px]" : ""}`}
    >
      {label}
    </button>
  );
}
