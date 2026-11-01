"use client";
import { useEffect, useState } from "react";
import { ArrowLeft, Crown, RotateCcw, Share2, Trophy } from "lucide-react";
import { playerName, type Room } from "@/lib/arcade";

/**
 * The result card.
 *
 * When a game ends the board should not simply stop being interactive — it
 * should hand the players a verdict they can read at arm's length: who won,
 * how, the scoresheet if there is one, and the two things anybody wants next
 * (a rematch, or the door). The artwork behind it is picked by the *player's*
 * outcome, not the room's, so losing looks different from winning.
 */
const ART = {
  win: "/results/win.jpg",
  draw: "/results/draw.jpg",
  lose: "/results/lose.jpg",
} as const;

const REASON: Record<string, string> = {
  played: "Decided on the board",
  forfeit: "The clock ran out",
  resign: "A resignation",
  agreement: "Both players agreed",
};

/** Deterministic confetti: a seeded list, so the same win looks the same twice. */
function confetti(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const seed = (index * 9301 + 49297) % 233280;
    const ratio = seed / 233280;
    return {
      left: `${(ratio * 100).toFixed(2)}%`,
      delay: `${((index % 9) * 0.09).toFixed(2)}s`,
      duration: `${(1.6 + (index % 5) * 0.22).toFixed(2)}s`,
      tilt: `${Math.round(ratio * 70 - 35)}deg`,
      hue: index % 3,
    };
  });
}

export function ResultOverlay({
  room,
  busy,
  send,
  onBack,
  onShare,
}: {
  room: Room;
  busy: boolean;
  send: (payload: Record<string, unknown>) => Promise<unknown>;
  onBack: () => void;
  onShare: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);

  // A rematch is a *new room*, so the card must come back for the next game.
  useEffect(() => {
    if (room.status !== "done") setDismissed(false);
  }, [room.status, room.code]);

  if (room.status !== "done" || dismissed) return null;

  const mine = room.you.seat;
  const drawn = room.winner === "draw";
  const won = typeof room.winner === "number" && room.winner === mine;
  const outcome = drawn ? "draw" : won ? "win" : "lose";
  const winners = room.seats.filter((seat) => seat.seat === room.winner);
  const headline = drawn
    ? "A draw."
    : winners.length
      ? `${winners[0].name} wins.`
      : "The game finished.";
  const detail = drawn
    ? mine !== null
      ? "Neither side could force the point."
      : "Neither side could force the point."
    : won
      ? "Clean work. The rematch button is right there."
      : mine === null
        ? "The table is finished; open a room of your own."
        : "Take the rematch — the board is already warm.";
  const log = (room.state.log as string[]) || [];
  const reason = room.end_reason ? REASON[room.end_reason] : "";

  return (
    <div className="result" data-outcome={outcome} role="dialog" aria-label="Game result">
      <div className="result-art" aria-hidden>
        <img src={ART[outcome]} alt="" decoding="async" />
      </div>
      {outcome === "win" ? (
        <div className="result-confetti" aria-hidden>
          {confetti(24).map((piece, index) => (
            <i
              key={index}
              style={{
                left: piece.left,
                animationDelay: piece.delay,
                animationDuration: piece.duration,
                transform: `rotate(${piece.tilt})`,
              }}
              data-hue={piece.hue}
            />
          ))}
        </div>
      ) : null}

      <div className="result-body">
        <span className="result-badge">
          {drawn ? <Share2 size={13} aria-hidden /> : won ? <Trophy size={13} aria-hidden /> : <Crown size={13} aria-hidden />}
          {drawn ? "Draw" : won ? "You won" : mine === null ? "Finished" : "You lost"}
        </span>
        <h2 className="result-headline">{headline}</h2>
        <p className="result-detail">{detail}</p>
        {reason ? <p className="result-reason">{reason}</p> : null}

        <div className="result-seats">
          {room.seats.map((seat) => (
            <span key={seat.user} className="result-seat" data-winner={seat.seat === room.winner}>
              <i>{(seat.name || "?").slice(0, 1).toUpperCase()}</i>
              {seat.name}
              {seat.seat === mine ? <em>you</em> : null}
            </span>
          ))}
        </div>

        {log.length ? (
          <ol className="result-log" aria-label="Scoresheet">
            {log.slice(-16).map((san, index) => (
              <li key={`${index}-${san}`}>{san}</li>
            ))}
          </ol>
        ) : null}

        <div className="result-actions">
          {room.you.is_host ? (
            <button
              className="ios-btn ios-btn-primary"
              disabled={busy}
              onClick={() => void send({ action: "rematch" })}
            >
              <RotateCcw size={15} aria-hidden /> Rematch
            </button>
          ) : (
            <span className="result-wait">The host can start a rematch.</span>
          )}
          <button className="ios-btn ios-btn-glass" onClick={onShare}>
            <Share2 size={14} aria-hidden /> Share the table
          </button>
          <button className="ios-btn ios-btn-glass" onClick={onBack}>
            <ArrowLeft size={14} aria-hidden /> Arcade
          </button>
          <button className="result-dismiss" onClick={() => setDismissed(true)}>
            Keep looking at the board
          </button>
        </div>
      </div>
    </div>
  );
}

/** True when the room is over but the overlay is dismissed. */
export function resultHeadline(room: Room): string {
  if (room.winner === "draw") return "A draw.";
  if (typeof room.winner === "number") {
    const seat = room.seats.find((entry) => entry.seat === room.winner);
    return `${seat ? seat.name : playerName(room, null)} wins.`;
  }
  return "The game finished.";
}
