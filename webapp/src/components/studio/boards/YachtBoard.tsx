"use client";
import { useMemo } from "react";
import type { Room } from "@/lib/arcade";

const NAMES: Record<string, string> = {
  ones: "Ones", twos: "Twos", threes: "Threes", fours: "Fours", fives: "Fives", sixes: "Sixes",
  three_kind: "Three of a kind", four_kind: "Four of a kind", full_house: "Full house",
  small_straight: "Small straight", large_straight: "Large straight", yacht: "Yacht", chance: "Chance",
};

/** The server supplies dice, score previews, turn and all accepted choices. */
export function YachtBoard({ room, myTurn, busy, onMove }: {
  room: Room; myTurn: boolean; busy: boolean; onMove: (move: Record<string, unknown>) => void;
}) {
  const state = room.state as Record<string, unknown>;
  const dice = (state.dice as number[]) || [0, 0, 0, 0, 0];
  const kept = (state.kept as boolean[]) || [];
  const rolls = Number(state.rolls || 0);
  const scores = (state.scores as (number | null)[][]) || [];
  const totals = (state.totals as number[]) || [];
  const categories = (state.categories as string[]) || Object.keys(NAMES);
  const preview = (state.preview as Record<string, number>) || {};
  const legal = room.legal || [];
  const canRoll = myTurn && legal.some((entry) => entry.action === "roll");
  const canScore = useMemo(() => new Set(legal.filter((entry) => entry.action === "score").map((entry) => String(entry.category))), [legal]);

  return (
    <div className="arcade-yacht">
      <div className="arcade-yacht-head">
        <span>Roll {rolls} / 3</span>
        <span>{myTurn ? "Your dice" : `${room.seats.find((seat) => seat.seat === room.turn)?.name || "Player"}'s turn`}</span>
      </div>
      <div className="arcade-yacht-dice" role="group" aria-label="Your five dice">
        {dice.map((value, index) => {
          const canHold = myTurn && rolls > 0 && rolls < 3 && !busy;
          return <button key={index} type="button" onClick={() => onMove({ action: "hold", index })}
            disabled={!canHold} aria-pressed={Boolean(kept[index])}
            aria-label={`Die ${index + 1}: ${value || "not rolled"}${kept[index] ? ", held" : ""}`}
            data-held={Boolean(kept[index])} data-value={value || undefined}>
            {value ? <span aria-hidden>{"⚀⚁⚂⚃⚄⚅"[value - 1]}</span> : "·"}
          </button>;
        })}
      </div>
      {myTurn && rolls === 0 ? <p className="arcade-board-hint">Roll to begin your turn. Tap dice to hold between rolls.</p> : null}
      {canRoll ? <button type="button" className="ios-btn ios-btn-primary arcade-yacht-roll" disabled={busy} onClick={() => onMove({ action: "roll" })}>🎲 Roll{rolls ? " again" : ""}</button> : null}
      <div className="arcade-yacht-cards">
        {scores.map((row, seat) => (
          <section key={seat} data-you={room.you.seat === seat} aria-label={`Seat ${seat + 1} scorecard`}>
            <h3><span>Seat {seat + 1}{room.you.seat === seat ? " · you" : ""}</span><b>{totals[seat] || 0}</b></h3>
            <div className="arcade-yacht-categories">
              {categories.map((category, index) => {
                const value = row[index];
                const active = seat === room.you.seat && canScore.has(category) && !busy;
                return <button key={category} type="button" disabled={!active}
                  onClick={() => onMove({ action: "score", category })}
                  data-open={value === null} data-live={active}>
                  <span>{NAMES[category] || category}</span>
                  <b>{value === null ? (active ? (preview[category] ?? 0) : "—") : value}</b>
                </button>;
              })}
            </div>
          </section>
        ))}
      </div>
      <p className="arcade-board-hint">One score per box. Reach 63 in Ones–Sixes for the 35-point upper bonus.</p>
    </div>
  );
}
