"use client";

import { useId, useState } from "react";

/**
 * Adapted from VYRON's frontend album-cover component.
 * Copyright (c) 2026 Beasgohan-code. MIT License; see webapp/VYRON-LICENSE.md.
 * Source: https://github.com/Beasgohan-code/VYRON/tree/main/frontend
 */
export type CoverTrack = {
  video_id?: string;
  title?: string;
  thumbnail?: string | null;
};

function hashOf(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) | 0;
  return Math.abs(hash);
}

function monogram(value: string): string {
  const parts = value.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "V";
}

export function VyronCover({
  track,
  className = "",
  rounded = 18,
}: {
  track?: CoverTrack | null;
  className?: string;
  rounded?: number;
}) {
  const [broken, setBroken] = useState(false);
  const unique = useId().replace(/:/g, "");
  const seed = hashOf(String(track?.video_id ?? track?.title ?? "vyron"));
  const variant = seed % 4;
  const hue = seed % 360;
  const hue2 = (hue + 48 + (seed % 60)) % 360;
  const hue3 = (hue + 168) % 360;
  const first = `vyron-cover-a-${unique}`;
  const second = `vyron-cover-b-${unique}`;
  const third = `vyron-cover-c-${unique}`;

  return (
    <span
      className={`vyron-cover ${className}`}
      data-art={variant}
      style={{ borderRadius: rounded }}
      aria-hidden="true"
    >
      <svg className="vyron-cover-art" viewBox="0 0 100 100" preserveAspectRatio="none" focusable="false">
        <defs>
          <linearGradient id={first} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={`hsl(${hue} 78% 58%)`} />
            <stop offset="1" stopColor={`hsl(${hue2} 72% 42%)`} />
          </linearGradient>
          <radialGradient id={second} cx="0.2" cy="0.15" r="0.9">
            <stop offset="0" stopColor={`hsl(${hue3} 84% 62%)`} stopOpacity=".95" />
            <stop offset=".55" stopColor={`hsl(${hue2} 70% 40%)`} stopOpacity=".55" />
            <stop offset="1" stopColor="transparent" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={third} cx="0.85" cy="0.9" r="0.75">
            <stop offset="0" stopColor={`hsl(${hue} 90% 68%)`} stopOpacity=".75" />
            <stop offset="1" stopColor="transparent" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="100" height="100" fill={`hsl(${hue2} 40% 9%)`} />
        <rect width="100" height="100" fill={`url(#${second})`} />
        {variant === 0 && <>
          <circle cx="24" cy="72" r="34" fill={`url(#${first})`} opacity=".85" />
          <circle cx="74" cy="30" r="26" fill={`url(#${third})`} opacity=".9" />
          <rect y="54" width="100" height="46" fill="#000" opacity=".22" />
        </>}
        {variant === 1 && <>
          <rect width="100" height="100" fill={`url(#${first})`} opacity=".55" />
          {[46, 38, 30, 22, 14, 7].map((radius, index) => <circle key={radius} cx="62" cy="42" r={radius} fill="none" stroke={`hsl(${(hue + index * 24) % 360} 95% 78%)`} strokeOpacity={0.16 + index * 0.1} strokeWidth={index === 0 ? 1.1 : 0.7} />)}
          <circle cx="62" cy="42" r="9" fill={`hsl(${hue3} 92% 70%)`} opacity=".9" />
          <path d="M0 78 L100 58 L100 100 L0 100 Z" fill="#000" opacity=".3" />
        </>}
        {variant === 2 && <>
          <rect width="100" height="100" fill={`url(#${first})`} opacity=".6" />
          <g transform="rotate(-24 50 50)">{[8, 26, 44, 62, 80, 98].map((x, index) => <rect key={x} x={x} y="-20" width={index % 2 ? 5 : 11} height="140" fill={`hsl(${(hue + index * 40) % 360} 90% ${index % 2 ? 72 : 52}%)`} opacity={index % 2 ? .35 : .22} />)}</g>
          <circle cx="78" cy="22" r="13" fill={`hsl(${hue3} 96% 74%)`} opacity=".85" />
        </>}
        {variant === 3 && <>
          <rect width="100" height="100" fill={`url(#${first})`} opacity=".35" />
          <g fill={`hsl(${hue3} 92% 78%)`} opacity=".5">{Array.from({ length: 49 }, (_, index) => <circle key={index} cx={10 + (index % 7) * 13.5} cy={10 + Math.floor(index / 7) * 13.5} r={(index % 3) * .9 + .8} />)}</g>
          <circle cx="74" cy="74" r="30" fill={`url(#${third})`} />
          <rect width="100" height="100" fill={`url(#${second})`} opacity=".45" />
        </>}
      </svg>
      {track?.thumbnail && !broken && <img className="vyron-cover-img" src={track.thumbnail} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />}
      <span className="vyron-cover-mono">{monogram(track?.title ?? "VYRON")}</span>
      <span className="vyron-cover-sheen" />
    </span>
  );
}
