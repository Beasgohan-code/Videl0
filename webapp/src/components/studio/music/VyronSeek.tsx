"use client";

/**
 * Adapted from VYRON's deterministic waveform seek control.
 * Copyright (c) 2026 Beasgohan-code. MIT License; see webapp/VYRON-LICENSE.md.
 * Source: https://github.com/Beasgohan-code/VYRON/tree/main/frontend
 */
function hashOf(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) | 0;
  return Math.abs(hash);
}

function peaksFor(seed: number, count: number): number[] {
  let value = seed || 1;
  return Array.from({ length: count }, () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return 0.18 + (value / 0xffffffff) * 0.82;
  });
}

export function VyronSeek({
  trackKey,
  position,
  duration,
  onSeek,
}: {
  trackKey: string;
  position: number;
  duration: number;
  onSeek: (seconds: number) => void;
}) {
  const total = Number.isFinite(duration) && duration > 0 ? duration : 0;
  const current = Number.isFinite(position) ? Math.max(0, Math.min(position, total)) : 0;
  const progress = total ? (current / total) * 100 : 0;
  const bars = peaksFor(hashOf(trackKey), 72);

  return (
    <div className="vyron-waveform" aria-label="Playback position">
      <div className="vyron-waveform-bars" aria-hidden="true">
        {bars.map((height, index) => <span key={index} style={{ height: `${Math.round(height * 100)}%`, opacity: index / bars.length <= progress / 100 ? 0.95 : 0.27 }} />)}
      </div>
      <input
        aria-label="Seek track"
        type="range"
        min={0}
        max={total || 1}
        step={0.1}
        value={current}
        disabled={!total}
        onChange={(event) => onSeek(Number(event.target.value))}
      />
    </div>
  );
}
