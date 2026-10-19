"use client";
import { useEffect, useRef } from "react";

export type ChatMsg = {
  id: string;
  chat_id: string;
  from: "you" | "bot" | "user";
  text: string;
  time: string;
  via?: string;
};

export function ChatView({
  msgs,
  typing = false,
  onClear,
}: {
  msgs: ChatMsg[];
  typing?: boolean;
  onClear?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [msgs, typing]);

  // Group by date label (simple)
  return (
    <div ref={ref} className="flex-1 overflow-auto bg-[#000] p-4 space-y-3">
      <div className="flex justify-center">
        <span className="px-3 py-1 rounded-full bg-[var(--ios-fill)] text-[11px] font-medium text-[var(--ios-label-secondary)]">
          Today • Videl • Encrypted • Owner-only
        </span>
      </div>

      {msgs.map((m) => {
        const me = m.from === "you";
        return (
          <div key={m.id} className={`flex ${me ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[78%] rounded-[20px] px-4 py-3 text-[15px] leading-5 shadow-sm ${
                me
                  ? "bg-[#0A84FF] text-white rounded-br-[6px]"
                  : "bg-[#1E1E22] text-white rounded-bl-[6px] border border-[var(--ios-border)]"
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{m.text}</div>
              <div className={`mt-1 flex items-center gap-1.5 text-[11px] ${me ? "text-white/70 justify-end" : "text-[var(--ios-label-secondary)]"}`}>
                <span>{m.time}</span>
                <span>• {m.via || m.from}</span>
                {me && <span className="ml-1">✓✓</span>}
              </div>
            </div>
          </div>
        );
      })}

      {typing && (
        <div className="flex justify-start">
          <div className="bg-[#1E1E22] border border-[var(--ios-border)] rounded-[20px] rounded-bl-[6px] px-4 py-3 flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-white/60 animate-bounce [animation-delay:-0.3s]" />
            <span className="h-2 w-2 rounded-full bg-white/60 animate-bounce [animation-delay:-0.15s]" />
            <span className="h-2 w-2 rounded-full bg-white/60 animate-bounce" />
          </div>
        </div>
      )}

      {onClear && msgs.length > 4 && (
        <div className="flex justify-center pt-2">
          <button onClick={onClear} className="ios-pill">Clear</button>
        </div>
      )}
    </div>
  );
}
