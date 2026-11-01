"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Copy, Check, Send, ShieldCheck } from "lucide-react";
import { usePlayerSession } from "@/lib/player";
import { RoomView } from "@/components/studio/RoomView";
import { inviteLink, telegramInvite, GAME_ART, type Lobby, type PlayerRef } from "@/lib/arcade";

/**
 * A shared room link, opened the way a link should open: in the browser.
 *
 * If this browser already holds a player cookie it goes straight to the table;
 * if it does not, the page is the invitation itself — the code, the game room
 * art, and one button that hands over to Telegram, which is the only place a
 * seat can be taken.
 */
export function InviteRoom({ code }: { code: string }) {
  const { player } = usePlayerSession();
  const [copied, setCopied] = useState(false);
  const [lobby, setLobby] = useState<Lobby | null>(null);

  useEffect(() => {
    if (!player) return;
    let alive = true;
    fetch("/api/arcade", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (alive && data?.ok) setLobby(data as Lobby);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [player]);

  async function copy() {
    const link = inviteLink(code, window.location.origin);
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* the field below is selectable when the clipboard is locked */
    }
  }

  // No spinner and no blank frame: the invitation is what this address *is*,
  // so it paints immediately, and only a browser that already holds a player
  // cookie swaps to the table once /api/session answers.
  if (player) {
    const back = () => {
      window.location.assign("/?tab=arcade");
    };
    return (
      <main className="ios-page">
        <RoomView
          code={code}
          player={{ id: player.id, name: player.name } as PlayerRef}
          lobby={lobby}
          onBack={back}
          onChanged={() => {}}
        />
      </main>
    );
  }

  return (
    <main className="ios-page invite-page">
      <div className="invite-stage">
        <img className="invite-hero" src="/invite/hero.jpg" alt="" aria-hidden decoding="async" />
        <div className="invite-mosaic" aria-hidden>
          {["chinese", "dots", "yacht", "ludo", "chess", "checkers", "gomoku", "connect4", "reversi", "tictactoe"].map((game) => (
            <img
              key={game}
              src={GAME_ART[game]}
              alt=""
              className="invite-mosaic-art"
              data-game={game}
              decoding="async"
              loading={game === "ludo" ? "eager" : "lazy"}
            />
          ))}
        </div>

        <div className="invite-card">
          <span className="arcade-kicker">
            <ShieldCheck size={12} aria-hidden /> Invitation
          </span>
          <h1 className="invite-title">A chair is waiting.</h1>
          <p className="invite-copy">
            Somebody opened a table and sent you the code. Nothing to install — the board
            lives on the server, and the table keeps your seat.
          </p>

          <div className="invite-code" aria-label="Room code">
            {code.split("").map((character, index) => (
              <span key={`${character}-${index}`}>{character}</span>
            ))}
          </div>

          <div className="invite-actions">
            <a className="ios-btn ios-btn-primary" href={telegramInvite(code)}>
              <Send size={15} aria-hidden /> Take a seat in Telegram
            </a>
            <button className="ios-btn ios-btn-glass" onClick={() => void copy()}>
              {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
              {copied ? "Link copied" : "Copy link"}
            </button>
          </div>

          <ol className="invite-steps">
            <li>
              <b>1</b> Open <span className="mono">@videlapp</span> in Telegram.
            </li>
            <li>
              <b>2</b> Pick the <span className="mono">Arcade</span> button — the room opens
              with you already signed in.
            </li>
            <li>
              <b>3</b> Type <span className="mono">{code}</span> if the tab did not open on its
              own.
            </li>
          </ol>

          <p className="invite-and">
            Signed in on this browser already?{" "}
            <Link href={`/?tab=arcade&room=${code}`} className="invite-inline">
              Open the table <ArrowRight size={11} aria-hidden />
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
