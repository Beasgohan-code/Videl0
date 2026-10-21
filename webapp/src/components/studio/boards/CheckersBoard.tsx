"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  chainLanding,
  chainsFrom,
  checkerSeat,
  isCrowned,
  isDarkSquare,
  seatColour,
  type Room,
} from "@/lib/arcade";

/**
 * Checkers, drawn as a real board rather than a grid of buttons.
 *
 * The server gives the legal chains — never a destination list the client
 * invented — so a tap can only ever send a move that already existed. A chain
 * that would jump twice is one tap: the piece is lifted, every possible landing
 * is marked, and the whole chain goes to the server at once.
 */
export function CheckersBoard({
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
  const last = room.state.last as
    | { from: number; to: number; captures: number; crowned: boolean }
    | null;
  const legal = room.legal || [];
  const [picked, setPicked] = useState<number | null>(null);

  // A fresh board, someone else's turn, or a move that landed invalidates any
  // half-finished pick. Leaving it selected would send a chain from a board
  // that no longer exists.
  useEffect(() => {
    setPicked(null);
  }, [room.version, room.turn]);

  const mine = room.you.seat;
  const forced = legal.length > 0 && legal.every((entry) => Number(entry.captures) > 0);
  const options = useMemo(
    () => (picked === null ? [] : chainsFrom(legal, picked)),
    [legal, picked],
  );
  const paths = useMemo(() => {
    // Every square a picked chain travels through, for the dotted preview.
    const seen = new Set<number>();
    options.forEach((chain) => chain.to.slice(0, -1).forEach((cell) => seen.add(cell)));
    return seen;
  }, [options]);
  const doomed = useMemo(() => {
    // The pieces this tap would lift off the board, previewed before it lands.
    const seen = new Set<number>();
    options.forEach((chain) => chain.via.forEach((cell) => cell !== null && seen.add(Number(cell))));
    return seen;
  }, [options]);

  const take = useCallback(
    (target: number) => {
      if (picked === null || busy) return;
      const chain = chainLanding(legal, picked, target);
      if (!chain) return;
      setPicked(null);
      onMove({ from: picked, to: chain.to });
    },
    [busy, legal, onMove, picked],
  );

  return (
    <div className="checkers">
      <div className="checkers-frame">
        <div className="checkers-board" role="grid" aria-label="Checkers board">
          {Array.from({ length: 64 }, (_, index) => {
            const cell = board[index] || 0;
            const seat = checkerSeat(cell);
            const own = myTurn && seat !== null && seat === mine;
            const chainHere = own ? chainsFrom(legal, index) : [];
            const canPick = chainHere.length > 0 && !busy;
            const target = picked !== null && options.some((chain) => chain.to[chain.to.length - 1] === index);
            const through = paths.has(index);
            const chainPreview = target
              ? options.find((chain) => chain.to[chain.to.length - 1] === index)
              : undefined;
            return (
              <div
                key={index}
                className="checkers-cell"
                data-dark={isDarkSquare(index)}
                data-target={target}
                data-through={through}
                data-last={last ? last.from === index || last.to === index : false}
                data-doomed={doomed.has(index)}
                role="gridcell"
                aria-label={
                  cell
                    ? `square ${index + 1}, ${seat === 0 ? "bone" : "ink"} ${isCrowned(cell) ? "king" : "man"}`
                    : `empty square ${index + 1}`
                }
              >
                {cell ? (
                  <button
                    type="button"
                    disabled={!canPick}
                    onClick={() => setPicked(index)}
                    className="checkers-piece"
                    data-seat={seat}
                    data-king={isCrowned(cell)}
                    data-picked={picked === index}
                    data-live={canPick}
                    data-forced={canPick && forced}
                    style={{ "--piece": seatColour(room.game, seat ?? 0) } as CSSProperties}
                    aria-label={
                      own
                        ? `your ${isCrowned(cell) ? "king" : "man"}${chainHere.length ? `, ${chainHere.length} move${chainHere.length > 1 ? "s" : ""}` : ""}`
                        : `${seat === 0 ? "bone" : "ink"} ${isCrowned(cell) ? "king" : "man"}`
                    }
                  >
                    <span className="checkers-piece-top" aria-hidden>
                      {isCrowned(cell) ? "♛" : ""}
                    </span>
                  </button>
                ) : null}
                {target ? (
                  <button
                    type="button"
                    onClick={() => take(index)}
                    disabled={busy}
                    className="checkers-landing"
                    data-captures={chainPreview?.captures || 0}
                    aria-label={`land on square ${index + 1}${
                      chainPreview?.captures ? `, taking ${chainPreview.captures}` : ""
                    }`}
                  >
                    {chainPreview && chainPreview.captures > 1 ? (
                      <b aria-hidden>{chainPreview.captures}×</b>
                    ) : null}
                  </button>
                ) : null}
                {through && !target ? <span className="checkers-path" aria-hidden /> : null}
              </div>
            );
          })}
        </div>
        <span className="checkers-stud" data-corner="tl" aria-hidden />
        <span className="checkers-stud" data-corner="tr" aria-hidden />
        <span className="checkers-stud" data-corner="bl" aria-hidden />
        <span className="checkers-stud" data-corner="br" aria-hidden />
      </div>

      <p className="checkers-hint" data-alert={forced && myTurn}>
        {!myTurn ? (
          "Waiting for the other chair."
        ) : picked === null ? (
          forced ? (
            <>
              <b>A capture is on the board.</b> Take it — the longest chain is the only
              legal one.
            </>
          ) : (
            "Pick one of your pieces, then the square it lands on."
          )
        ) : options.length === 0 ? (
          "That piece has no legal move."
        ) : options.length === 1 ? (
          options[0].captures > 1
            ? `Jump ${options[0].captures} pieces — tap the ringed square.`
            : "Tap the ringed square."
        ) : (
          `${options.length} legal landings — pick one.`
        )}
      </p>
    </div>
  );
}
