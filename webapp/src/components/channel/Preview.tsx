"use client";

type Btn = { text: string; url: string; color: string };

const COLOR_MAP: Record<string, { bg: string; fg: string }> = {
  primary: { bg: "#0A84FF", fg: "#fff" },
  success: { bg: "#30D158", fg: "#fff" },
  danger:  { bg: "#FF453A", fg: "#fff" },
  warn:    { bg: "#FF9F0A", fg: "#fff" },
  ghost:   { bg: "rgba(120,128,128,0.14)", fg: "#fff" },
  black:   { bg: "#111", fg: "#fff" },
  pink:    { bg: "#FF2D55", fg: "#fff" },
  indigo:  { bg: "#5856D6", fg: "#fff" },
};

function renderHtml(html: string) {
  // Very light sanitizer — keep only allowed tags for preview
  // In production TG will render full HTML; we just preview safely
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/\n/g, "<br/>");
}

export function ChannelPreview({
  channel,
  text,
  mediaUrl,
  buttons,
  theme = "dark",
}: {
  channel: string;
  text: string;
  mediaUrl?: string;
  buttons: Btn[][];
  theme?: "dark" | "light";
}) {
  const isDark = theme === "dark";

  return (
    <div className={`rounded-[24px] overflow-hidden border ${isDark ? "bg-[#0E1621] border-[#1A2A3A]" : "bg-[#E7EBF0] border-[#D1D7DE]"}`}>
      {/* TG header */}
      <div className={`flex items-center gap-3 px-4 py-3 border-b ${isDark ? "bg-[#17212B] border-[#242F3D]" : "bg-white border-[#E7EBF0]"}`}>
        <div className="h-9 w-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-[12px]">V</div>
        <div>
          <div className={`text-[14px] font-semibold ${isDark ? "text-white" : "text-black"}`}>{channel || "@VidelUpdates"}</div>
          <div className="text-[12px] text-[#8E8E93]">{isDark ? "Channel • Bot API 10.3" : "Channel • Preview"} • 12.4K members</div>
        </div>
        <span className="ml-auto text-[11px] px-2.5 py-1 rounded-full bg-[#0A84FF] text-white font-semibold">TG</span>
      </div>

      {/* Message bubble */}
      <div className={`p-4 ${isDark ? "bg-[#0E1621]" : "bg-[#E7EBF0]"}`}>
        <div
          className={`max-w-[88%] rounded-[18px] rounded-tl-[6px] shadow-[0_1px_2px_rgba(0,0,0,0.2)] overflow-hidden ${
            isDark ? "bg-[#182533] text-[#E6E6E6]" : "bg-white text-[#111]"
          }`}
        >
          {mediaUrl ? (
            <img
              src={mediaUrl}
              alt=""
              className="w-full h-auto max-h-[320px] object-cover"
              onError={e => ((e.target as HTMLImageElement).style.display = "none")}
            />
          ) : null}

          <div className="px-3.5 pt-3 pb-2">
            {text ? (
              <div
                className="text-[14px] leading-[1.45] whitespace-pre-wrap break-words"
                dangerouslySetInnerHTML={{ __html: renderHtml(text) }}
              />
            ) : (
              <p className="text-[13px] text-[#8E8E93] italic">Your formatted message will appear here…</p>
            )}
            <div className="mt-2 flex items-center justify-end gap-2 text-[11px] text-[#8E8E93]">
              <span>12:34</span>
              <span className="text-[#78E378]">✓✓</span>
            </div>
          </div>

          {buttons.length > 0 && (
            <div className={`px-2 pb-2 space-y-1.5 ${isDark ? "bg-[#182533]" : "bg-white"}`}>
              {buttons.map((row, ri) => (
                <div key={ri} className="flex gap-1.5">
                  {row.map((b, ci) => {
                    const c = COLOR_MAP[b.color] || COLOR_MAP.primary;
                    return (
                      <a
                        key={ci}
                        href={b.url}
                        target="_blank"
                        className="flex-1 flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-[10px] text-[13px] font-medium transition active:scale-[0.98]"
                        style={{ background: c.bg, color: c.fg }}
                      >
                        {b.text}
                      </a>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className={`mt-3 text-[11px] ${isDark ? "text-[#6B7C8D]" : "text-[#8E8E93]"}`}>
          ◍ Videl • Kurigram • Richgram — preview is 1:1 Telegram HTML rendering
        </p>
      </div>
    </div>
  );
}
