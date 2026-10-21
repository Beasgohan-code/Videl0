"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { PIECE_NAME, moveTo, movesFrom, ownsSquare, squareAt, type Room } from "@/lib/arcade";

/**
 * Chess, drawn as a board you can read at a glance.
 *
 * The pieces are SVG, not font glyphs: an emoji king renders as a different
 * drawing on every phone, and at 40px a real silhouette reads instantly. Ivory
 * and onyx are the two seats; the accent is a warming tint, never a hue change,
 * so the board still looks like a board.
 */
const SHAPES: Record<string, string> = {
  k: "M12 2.6 13.4 6h2.9l-2 2.6 1.3 3.4H10.4l1.3-3.4-2-2.6h2.9zM9.8 13h4.4l.7 6H9.1zM7.6 20.4h8.8V22H7.6z",
  q: "M12 2.4 13 5.4l1.4-2 .8 3.4 1.6-1.6.3 3.6-.9 3.2H8.8L7.9 8.8l.3-3.6 1.6 1.6.8-3.4 1.4 2zM9.5 13.6h5l.5 5.4H9zM7.6 20.4h8.8V22H7.6z",
  r: "M8.4 3h1.6v2h1.4V3h1.2v2h1.4V3h1.6v4.2l-1.3 1.1v7.1h1.2V20H8.3v-4.6h1.3V8.3L8.4 7.2zM8.2 20.4h7.6V22H8.2z",
  b: "M12 2.4c1.5 0 2.3 1.2 2.3 2.3 0 .8-.4 1.2-.4 1.6 0 .5 1.2 1 1.8 2.2.7 1.4.6 3.3-.2 4.4h-7c-.8-1.1-.9-3-.2-4.4.6-1.2 1.8-1.7 1.8-2.2 0-.4-.4-.8-.4-1.6C9.7 3.6 10.5 2.4 12 2.4zM9.6 14h4.8l.6 5.3H9zM7.6 20.4h8.8V22H7.6z",
  n: "M9.4 21c-.2-2.6.2-4.7 1.3-6.4.6-1 1.4-1.9 1.6-2.9-1.2.6-2.1 1.5-2.9 2.6l-1.3-1c.9-2 2.2-3.6 3.9-4.9L11.4 6l.8-2.5 1.2 1.7 1.9-.9.6 1.9c2.2 1.1 3.5 3 3.7 5.6.2 2.9-.4 5.9-.9 9.2zM8.6 20.4h8.6V22H8.6z",
  p: "M12 3.4a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM10.3 9.5h3.4c.9 1.4 1.1 3 .6 4.6h-4.6c-.5-1.6-.3-3.2.6-4.6zM9.4 15.2h5.2l.8 4.4H8.6zM7.4 20.4h9.2V22H7.4z",
};

export function ChessBoard({
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
  const board = (room.state.board as string[]) || [];
  const last = room.state.last as { from: number; to: number; san: string } | null;
  const legal = room.legal || [];
  const [picked, setPicked] = useState<number | null>(null);
  const [promote, setPromote] = useState<{ from: number; to: number } | null>(null);
  const seat = room.you.seat;
  // Black sees its own pieces at the bottom; a board that is upside down for
  // half the players is the oldest unforced mistake in digital chess.
  const [flipped, setFlipped] = useState(seat === 1);
  const [cursor, setCursor] = useState(52);
  const grid = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setPicked(null);
    setPromote(null);
  }, [room.version, room.turn]);

  const destinations = useMemo(() => {
    if (picked === null) return new Map<number, Record<string, unknown>[]>();
    const map = new Map<number, Record<string, unknown>[]>();
    for (const move of movesFrom(legal, picked)) {
      const to = Number(move.to);
      map.set(to, [...(map.get(to) || []), move]);
    }
    return map;
  }, [legal, picked]);

  function tap(square: number) {
    if (busy || !myTurn) return;
    if (promote) return;
    const options = destinations.get(square);
    if (picked !== null && options?.length) {
      const chosen = options[0];
      if (options.some((move) => move.promote)) {
        // A promotion is a question: ask, never guess.
        setPromote({ from: picked, to: square });
        return;
      }
      onMove({ from: chosen.from, to: chosen.to });
      setPicked(null);
      return;
    }
    if (ownsSquare(board, square, seat)) {
      setPicked(picked === square ? null : square);
      return;
    }
    setPicked(null);
  }

  function crown(piece: string) {
    if (!promote) return;
    onMove({ from: promote.from, to: promote.to, promote: piece });
    setPromote(null);
    setPicked(null);
  }

  /**
   * Arrow keys walk the board, Enter picks a piece or plays the move. It is a
   * small thing that makes the board usable without a mouse — and a chess
   * board that only responds to taps is a chess board you cannot play on a
   * laptop without hunching over the trackpad.
   */
  function key(event: React.KeyboardEvent) {
    const step: Record<string, number> = { ArrowUp: -8, ArrowDown: 8, ArrowLeft: -1, ArrowRight: 1 };
    if (step[event.key]) {
      event.preventDefault();
      const delta = step[event.key];
      // Horizontal moves must not wrap onto the next row.
      if (Math.abs(delta) === 1 && Math.abs(cursor % 8 - (cursor + delta) % 8) !== 1) return;
      setCursor((square) => Math.max(0, Math.min(63, square + delta)));
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      tap(cursor);
      return;
    }
    if (event.key === "Escape") {
      setPicked(null);
      setPromote(null);
    }
  }

  const captured = useMemo(() => {
    // Anything the opponent started with that is no longer on the board.
    const start = "rnbqkbnrpppppppppppppppp".split("");
    const counts: Record<string, number> = {};
    board.forEach((piece) => {
      if (piece && piece !== ".") counts[piece] = (counts[piece] || 0) + 1;
    });
    const gone: string[] = [];
    for (const piece of new Set(start)) {
      const missing = Math.max(0, (piece === "p" ? 8 : 1) - (counts[piece] || 0));
      for (let index = 0; index < missing; index += 1) gone.push(piece);
    }
    return gone;
  }, [board]);

  const checking = Boolean(room.state.check) && room.status === "playing";
  const log = (room.state.log as string[]) || [];
  const order = flipped ? Array.from({ length: 64 }, (_, index) => 63 - index) : null;

  return (
    <div className="chess">
      <div className="chess-seats" aria-hidden={!checking}>
        {checking ? <span className="chess-alert">Check</span> : <span />}
        <span className="chess-tray" aria-label="Captured pieces">
          {captured.slice(0, 15).map((piece, index) => (
            <svg key={`${piece}-${index}`} viewBox="0 0 24 24" className="chess-tray-piece" data-dark={piece === piece.toLowerCase()}>
              <path d={SHAPES[piece.toLowerCase()]} />
            </svg>
          ))}
        </span>
      </div>

      <div className="chess-frame">
        <div
          className="chess-board"
          role="grid"
          aria-label="Chess board"
          ref={grid}
          tabIndex={0}
          onKeyDown={key}
          data-cursor-active={cursor >= 0}
        >
          {Array.from({ length: 64 }, (_, visual) => {
            const square = order ? order[visual] : visual;
            const row = Math.floor(visual / 8);
            const col = visual % 8;
            const { row: fileRow } = squareAt(square);
            const piece = board[square] || ".";
            const dark = (row + col) % 2 === 1;
            const mine = ownsSquare(board, square, seat) && myTurn;
            const target = destinations.get(square);
            const lastMove = last && (last.from === square || last.to === square);
            return (
              <button
                key={square}
                type="button"
                onClick={() => tap(square)}
                disabled={busy || !myTurn}
                className="chess-square"
                data-dark={dark}
                data-last={Boolean(lastMove)}
                data-picked={picked === square}
                data-target={Boolean(target)}
                data-capture={Boolean(target && piece !== ".")}
                data-cursor={cursor === square}
                role="gridcell"
                aria-label={`${"abcdefgh"[col]}${8 - row}${
                  piece !== "." ? `, ${PIECE_NAME[piece.toLowerCase()]} of ${piece === piece.toUpperCase() ? "ivory" : "onyx"}` : ""
                }${target ? ", legal move" : ""}`}
              >
                {piece !== "." ? (
                  <span className="chess-piece" data-side={piece === piece.toUpperCase() ? "ivory" : "onyx"} data-live={mine}>
                    <svg viewBox="0 0 24 24" aria-hidden>
                      <path d={SHAPES[piece.toLowerCase()]} />
                    </svg>
                  </span>
                ) : null}
                {target && piece === "." ? <span className="chess-dot" aria-hidden /> : null}
                {target && piece !== "." ? <span className="chess-ring" aria-hidden /> : null}
                {col === 0 ? <span className="chess-file" aria-hidden>{8 - fileRow}</span> : null}
                {row === 7 ? <span className="chess-rank" aria-hidden>{"abcdefgh"[square % 8]}</span> : null}
              </button>
            );
          })}
        </div>
      </div>

      {promote ? (
        <div className="chess-promote" role="dialog" aria-label="Choose a promotion">
          <p>Promote to</p>
          <div>
            {["q", "r", "b", "n"].map((piece) => (
              <button key={piece} onClick={() => crown(piece)} className="chess-promote-btn">
                <svg viewBox="0 0 24 24" aria-hidden>
                  <path d={SHAPES[piece]} />
                </svg>
                {PIECE_NAME[piece]}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="chess-foot">
        <button
          type="button"
          className="chess-flip"
          onClick={() => setFlipped((value) => !value)}
          aria-label="Flip the board"
          title="Flip the board"
        >
          <RefreshCw size={12} aria-hidden /> Flip
        </button>
        {log.length ? (
          <ol className="chess-log" aria-label="Move list">
            {log.map((san, index) => (
              <li key={`${index}-${san}`} data-latest={index === log.length - 1}>
                <i>{Math.floor(index / 2) + 1}{index % 2 === 0 ? "." : "…"}</i>
                {san}
              </li>
            ))}
          </ol>
        ) : (
          <p className="chess-log-empty">The scoresheet writes itself as you play.</p>
        )}
      </div>

      <p className="chess-hint">
        {!myTurn ? (
          room.state.last ? `Last move ${String((room.state.last as { san?: string }).san || "")}` : "Waiting for the other chair."
        ) : picked === null ? (
          "Pick a piece — its legal moves light up."
        ) : destinations.size === 0 ? (
          "That piece has no legal move."
        ) : (
          `${destinations.size} legal ${destinations.size === 1 ? "move" : "moves"}.`
        )}
      </p>
    </div>
  );
}
