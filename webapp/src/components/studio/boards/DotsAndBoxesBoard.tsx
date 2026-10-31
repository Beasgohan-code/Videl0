"use client";
import type { CSSProperties } from "react";
import type { Room } from "@/lib/arcade";

const COLOURS = ["#fb7185", "#34d399", "#fbbf24", "#60a5fa"];
const ROWS = 5;
const COLS = 6;

/** 6×5 boxes, with each of the 71 edges drawn only once by the server. */
export function DotsAndBoxesBoard({ room, myTurn, busy, onMove }: {
  room: Room; myTurn: boolean; busy: boolean; onMove: (move: Record<string, unknown>) => void;
}) {
  const state = room.state as Record<string, unknown>;
  const h = (state.h as number[]) || [];
  const v = (state.v as number[]) || [];
  const owners = (state.owner as number[]) || [];
  const scores = (state.scores as number[]) || [];
  const legal = new Set((room.legal || []).map((move) => `${move.kind}:${move.index}`));
  const last = state.last as { kind?: string; index?: number; closed?: number[] } | null;
  return (
    <div className="arcade-dots-wrap">
      <div className="arcade-dots-grid" role="group" aria-label="Dots and Boxes lines">
        {Array.from({ length: (ROWS + 1) * (COLS + 1) }).map((_, index) => {
          const row = Math.floor(index / (COLS + 1));
          const col = index % (COLS + 1);
          return <i key={`dot-${index}`} className="arcade-dots-dot" style={{ gridRow: row * 2 + 1, gridColumn: col * 2 + 1 }} />;
        })}
        {Array.from({ length: ROWS * COLS }).map((_, index) => {
          const row = Math.floor(index / COLS);
          const col = index % COLS;
          const owner = owners[index] ?? -1;
          return (
            <span
              key={`box-${index}`}
              className="arcade-dots-box"
              style={{ gridRow: row * 2 + 2, gridColumn: col * 2 + 2, "--box": owner >= 0 ? `${COLOURS[owner]}48` : "transparent" } as CSSProperties}
              aria-label={owner >= 0 ? `box claimed by seat ${owner + 1}` : "unclaimed box"}
            >{owner >= 0 ? `${owner + 1}` : ""}</span>
          );
        })}
        {h.map((drawn, index) => {
          const row = Math.floor(index / COLS);
          const col = index % COLS;
          const enabled = myTurn && legal.has(`h:${index}`) && !busy;
          return (
            <button key={`h-${index}`} type="button" className="arcade-dots-edge arcade-dots-edge-h"
              style={{ gridRow: row * 2 + 1, gridColumn: col * 2 + 2, "--line": drawn ? "#c4b5fd" : "#9ca3af" } as CSSProperties}
              data-drawn={Boolean(drawn)} data-last={last?.kind === "h" && last.index === index}
              aria-label={`horizontal line ${index + 1}${drawn ? ", drawn" : ""}`} disabled={!enabled || Boolean(drawn)}
              onClick={() => onMove({ kind: "h", index })} />
          );
        })}
        {v.map((drawn, index) => {
          const row = Math.floor(index / (COLS + 1));
          const col = index % (COLS + 1);
          const enabled = myTurn && legal.has(`v:${index}`) && !busy;
          return (
            <button key={`v-${index}`} type="button" className="arcade-dots-edge arcade-dots-edge-v"
              style={{ gridRow: row * 2 + 2, gridColumn: col * 2 + 1, "--line": drawn ? (last?.kind === "v" && last.index === index ? COLOURS[Number(room.you.seat ?? 0)] : "#cbd5e1") : "#9ca3af" } as CSSProperties}
              data-drawn={Boolean(drawn)} data-last={last?.kind === "v" && last.index === index}
              aria-label={`vertical line ${index + 1}${drawn ? ", drawn" : ""}`} disabled={!enabled || Boolean(drawn)}
              onClick={() => onMove({ kind: "v", index })} />
          );
        })}
      </div>
      <div className="arcade-dots-scores">
        {scores.map((score, seat) => <span key={seat} data-you={room.you.seat === seat}>
          <i style={{ background: COLOURS[seat] }} /> Seat {seat + 1}<b>{score} boxes</b>
        </span>)}
      </div>
      <p className="arcade-board-hint">{myTurn ? "Draw a glowing edge. A box earns another line." : "Each player gets one line; closed boxes score."}</p>
    </div>
  );
}
