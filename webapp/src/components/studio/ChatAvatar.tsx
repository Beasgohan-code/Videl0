"use client";
import { useState } from "react";

const PALETTE = [
  "linear-gradient(135deg,#5b7cfa,#22d3ee)",
  "linear-gradient(135deg,#f472b6,#8b5cf6)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#10b981,#3b82f6)",
  "linear-gradient(135deg,#06b6d4,#6366f1)",
  "linear-gradient(135deg,#a855f7,#ec4899)",
  "linear-gradient(135deg,#14b8a6,#84cc16)",
  "linear-gradient(135deg,#fb7185,#fbbf24)",
];

/**
 * Telegram-style chat avatar: the real profile photo when the bot can read it,
 * deterministic gradient initials otherwise. The photo is fetched through the
 * owner-only proxy so no token ever reaches the browser.
 */
export function ChatAvatar({
  id,
  title,
  size = 40,
  className = "",
  hasPhoto = true,
}: {
  id: number;
  title: string;
  size?: number;
  className?: string;
  hasPhoto?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const initials = (title || "?").trim().slice(0, 2).toUpperCase() || "?";
  const showPhoto = hasPhoto && !failed && Number.isSafeInteger(id) && id !== 0;
  return (
    <span
      className={`tg-avatar ${className}`}
      style={{
        width: size,
        height: size,
        backgroundImage: PALETTE[Math.abs(id) % PALETTE.length],
        fontSize: Math.max(10, Math.round(size * 0.32)),
      }}
      aria-hidden="true"
    >
      <span className="tg-avatar-initials">{initials}</span>
      {showPhoto && (
        <img
          src={`/api/chat-photo?chat_id=${id}`}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="tg-avatar-photo"
        />
      )}
    </span>
  );
}
