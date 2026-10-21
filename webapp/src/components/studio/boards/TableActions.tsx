"use client";
import { useState } from "react";
import { Flag, Handshake, Loader2 } from "lucide-react";
import { playerName, type Room } from "@/lib/arcade";

/**
 * The two ways a two-player game can end without a move.
 *
 * A resign button is irreversible, so it asks once, in place, with the same
 * finger that pressed it — no dialog that steals the board out from under the
 * player. A draw offer is reversible, so it is a single press and the other
 * seat gets the yes/no. Both are hidden in games that cannot use them.
 */
export function TableActions({
  room,
  busy,
  send,
}: {
  room: Room;
  busy: boolean;
  send: (payload: Record<string, unknown>) => Promise<unknown>;
}) {
  const [confirming, setConfirming] = useState(false);
  const mine = room.you.seat;
  const seated = mine !== null;
  const offer = room.draw_offer ?? null;

  if (!seated || room.seat_count !== 2) return null;

  if (room.status !== "playing") {
    if (room.status !== "done") return null;
    const reason = room.end_reason;
    if (!reason) return null;
    // Seat numbers and user ids are different things: the resigned seat is
    // 1 - winner, and the name belongs to whoever holds that seat.
    const loserSeat = room.winner === 0 || room.winner === 1 ? 1 - Number(room.winner) : null;
    const loser = room.seats.find((seat) => seat.seat === loserSeat);
    const text =
      reason === "resign"
        ? `${loser ? loser.name : "The other player"} resigned.`
        : reason === "agreement"
          ? "Both players agreed to a draw."
          : "";
    if (!text) return null;
    return <p className="table-verdict">{text}</p>;
  }

  if (offer !== null && offer !== mine) {
    return (
      <div className="table-draw" role="status">
        <Handshake size={15} aria-hidden />
        <span>{playerName(room, room.seats.find((seat) => seat.seat === offer)?.user ?? null)} offers a draw.</span>
        <button className="ios-btn ios-btn-primary px-3 py-1.5 text-xs" disabled={busy} onClick={() => void send({ action: "draw", accept: true })}>
          Accept
        </button>
        <button className="ios-btn ios-btn-glass px-3 py-1.5 text-xs" disabled={busy} onClick={() => void send({ action: "draw", accept: false })}>
          Keep playing
        </button>
      </div>
    );
  }

  return (
    <div className="table-actions">
      <button
        type="button"
        className="ios-btn ios-btn-glass px-3 py-1.5 text-xs"
        disabled={busy || offer === mine}
        onClick={() => void send({ action: "draw", accept: false })}
      >
        <Handshake size={13} aria-hidden />
        {offer === mine ? "Draw offered…" : "Offer a draw"}
      </button>
      {confirming ? (
        <span className="table-confirm">
          <span>Give the game away?</span>
          <button
            type="button"
            className="ios-btn ios-btn-glass px-3 py-1.5 text-xs"
            disabled={busy}
            onClick={() => void send({ action: "resign" })}
          >
            {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : null} Yes, resign
          </button>
          <button type="button" className="table-cancel" onClick={() => setConfirming(false)}>
            cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="table-resign"
          onClick={() => setConfirming(true)}
          disabled={busy}
        >
          <Flag size={13} aria-hidden /> Resign
        </button>
      )}
    </div>
  );
}
