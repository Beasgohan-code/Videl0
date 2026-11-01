"use client";
import { useMemo } from "react";
import { GOMOKU_SIZE, type Room } from "@/lib/arcade";

/**
 * Five in a Row on a 15×15 lattice.
 *
 * The whole board is one SVG: 225 buttons would swallow a phone's tap budget
 * and zoom the page on every misplaced press. One surface reads the tap
 * coordinate, which means a stone lands where the thumb actually touched.
 */
const SIZE = 480;
const PAD = 22;
const STEP = (SIZE - PAD * 2) / (GOMOKU_SIZE - 1);

function point(index: number): { x: number; y: number } {
  const row = Math.floor(index / GOMOKU_SIZE);
  const col = index % GOMOKU_SIZE;
  return { x: PAD + col * STEP, y: PAD + row * STEP };
}

export function GomokuBoard({
  room,
  myTurn,
  busy,
  onMove,
}: {
  room: Room;
  myTurn: boolean;
  busy: boolean;
  onMove: (move: Record<string, unknown>) => void;
}) {
  const board = (room.state.board as number[]) || [];
  const winning = useMemo(() => new Set(((room.state.line as number[]) || []).map(Number)), [room.state.line]);
  const last = room.state.last as { cell: number; player: number } | null;

  function strike(event: React.MouseEvent<HTMLDivElement>) {
    if (!myTurn || busy) return;
    const box = event.currentTarget.getBoundingClientRect();
    const scale = SIZE / box.width;
    const x = (event.clientX - box.left) * scale;
    const y = (event.clientY - box.top) * scale;
    const col = Math.round((x - PAD) / STEP);
    const row = Math.round((y - PAD) / STEP);
    if (col < 0 || col >= GOMOKU_SIZE || row < 0 || row >= GOMOKU_SIZE) return;
    // A near miss still means the intersection the thumb was closest to.
    if (Math.hypot(x - (PAD + col * STEP), y - (PAD + row * STEP)) > STEP * 0.72) return;
    const cell = row * GOMOKU_SIZE + col;
    if (board[cell]) return;
    onMove({ cell });
  }

  return (
    <div className="gomoku">
      <div className="gomoku-frame">
        <div
          className="gomoku-board"
          onClick={strike}
          data-live={myTurn && !busy}
          role="grid"
          aria-label="Five in a Row board"
        >
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden>
            <defs>
              <radialGradient id="gomoku-black" cx="34%" cy="28%">
                <stop offset="0%" stopColor="#5b6478" />
                <stop offset="58%" stopColor="#161b2a" />
                <stop offset="100%" stopColor="#05070d" />
              </radialGradient>
              <radialGradient id="gomoku-white" cx="34%" cy="28%">
                <stop offset="0%" stopColor="#ffffff" />
                <stop offset="62%" stopColor="#e7e9f2" />
                <stop offset="100%" stopColor="#a9aec2" />
              </radialGradient>
            </defs>
            {Array.from({ length: GOMOKU_SIZE }, (_, index) => (
              <g key={`grid-${index}`} stroke="rgba(24, 18, 10, 0.32)" strokeWidth={1}>
                <line x1={PAD} y1={PAD + index * STEP} x2={SIZE - PAD} y2={PAD + index * STEP} />
                <line x1={PAD + index * STEP} y1={PAD} x2={PAD + index * STEP} y2={SIZE - PAD} />
              </g>
            ))}
            {[3, 7, 11].map((row) =>
              [3, 7, 11].map((col) => (
                <circle key={`star-${row}-${col}`} cx={PAD + col * STEP} cy={PAD + row * STEP} r={2.6} fill="rgba(24, 18, 10, 0.55)" />
              )),
            )}
            {board.map((value, cell) => {
              if (!value) return null;
              const { x, y } = point(cell);
              return (
                <circle
                  key={`stone-${cell}`}
                  cx={x}
                  cy={y}
                  r={STEP * 0.44}
                  fill={value === 1 ? "url(#gomoku-black)" : "url(#gomoku-white)"}
                  stroke={winning.has(cell) ? "#f5d67b" : "rgba(0, 0, 0, 0.35)"}
                  strokeWidth={winning.has(cell) ? 2.6 : 0.7}
                  className="gomoku-stone"
                  data-win={winning.has(cell)}
                  data-last={last ? last.cell === cell : false}
                />
              );
            })}
          </svg>
        </div>
      </div>
      <p className="gomoku-hint">
        {!myTurn
          ? "Watching the other chair."
          : `Tap an intersection — ${board.filter(Boolean).length} of ${GOMOKU_SIZE * GOMOKU_SIZE} played.`}
      </p>
    </div>
  );
}
