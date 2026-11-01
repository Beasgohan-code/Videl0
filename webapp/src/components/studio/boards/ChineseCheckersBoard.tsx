"use client";
import { useMemo, useState } from "react";
import type { Room } from "@/lib/arcade";

const COLOURS = ["#fb7185", "#fbbf24", "#34d399", "#60a5fa", "#c084fc", "#fb923c"];

/** 121 server-owned holes; the board never invents geometry or destinations. */
export function ChineseCheckersBoard({ room, myTurn, busy, onMove }: {
  room: Room; myTurn: boolean; busy: boolean; onMove: (move: Record<string, unknown>) => void;
}) {
  const state = room.state as Record<string, unknown>;
  const holes = (state.holes as number[][]) || [];
  const camps = (state.camps as number[][]) || [];
  const pegs = (state.pegs as number[][]) || [];
  const legal = room.legal || [];
  const byHole = useMemo(() => {
    const occupied = new Map<number, number>();
    pegs.forEach((row, seat) => row.forEach((hole) => occupied.set(Number(hole), seat)));
    return occupied;
  }, [pegs]);
  const [selected, setSelected] = useState<number | null>(null);
  const destinations = new Set(legal.filter((move) => Number(move.from) === selected).map((move) => Number(move.to)));
  const chosen = useMemo(() => new Set(legal.map((move) => Number(move.from))), [legal]);
  const ownPegs = room.you.seat === null ? new Set<number>() : new Set(pegs[room.you.seat] || []);
  const last = state.last as { from?: number; to?: number } | null;

  return (
    <div className="arcade-chinese-wrap">
      <div className="arcade-chinese-board" role="group" aria-label="Chinese Checkers star board">
        {holes.map(([row, x2], index) => {
          const seat = byHole.get(index);
          const targetSeat = camps.findIndex((camp) => camp.includes(index));
          const canGo = myTurn && selected !== null && destinations.has(index) && !busy;
          const movablePeg = myTurn && chosen.has(index) && ownPegs.has(index) && !busy;
          return (
            <button
              key={index}
              type="button"
              className="arcade-chinese-hole"
              style={{
                gridRow: row + 1,
                gridColumn: x2 + 13,
                "--peg": seat === undefined ? (targetSeat >= 0 ? COLOURS[targetSeat] : "#cbd5e1") : COLOURS[seat],
              } as React.CSSProperties}
              data-occupied={seat !== undefined}
              data-own={seat !== undefined && seat === room.you.seat}
              data-target={targetSeat >= 0}
              data-last={index === Number(last?.to)}
              aria-label={`hole ${index + 1}${seat === undefined ? " empty" : ` seat ${seat + 1} peg`}${movablePeg ? ", select peg" : ""}`}
              disabled={!canGo && !movablePeg}
              onClick={() => {
                if (canGo && selected !== null) {
                  onMove({ from: selected, to: index });
                  setSelected(null);
                } else if (movablePeg) setSelected(index);
              }}
            >
              <span />
            </button>
          );
        })}
      </div>
      <div className="arcade-chinese-players" aria-label="Player camps">
        {(state.homes as number[] || []).map((camp, seat) => (
          <span key={seat} data-you={room.you.seat === seat}>
            <i style={{ background: COLOURS[camp] }} /> Seat {seat + 1} → camp {Number((state.targets as number[])[seat]) + 1}
          </span>
        ))}
      </div>
      <p className="arcade-board-hint">Select a glowing peg, then an empty highlighted hole. Jump chains can turn.</p>
    </div>
  );
}
