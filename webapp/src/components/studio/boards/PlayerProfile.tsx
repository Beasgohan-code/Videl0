"use client";
import { useState } from "react";
import { UserRound } from "lucide-react";
import { initials } from "@/lib/arcade";

type PublicPlayer = {
  id: number;
  name: string;
  username?: string | null;
  stats?: Record<string, { wins: number; losses: number; draws: number; rating: number; games: number }>;
};

/** Telegram photo through our signed proxy, with a profile card on demand. */
export function PlayerProfile({ id, name, game, size = 30 }: {
  id: number;
  name: string;
  game: string;
  size?: number;
}) {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<PublicPlayer | null>(null);
  const [error, setError] = useState("");

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (profile || loading) return;
    setLoading(true);
    try {
      const response = await fetch(`/api/arcade/player/${id}`, { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok || !data.player) throw new Error(data.error || "Profile unavailable");
      setProfile(data.player as PublicPlayer);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const stat = profile?.stats?.[game];
  return (
    <span className="arcade-profile-wrap">
      <button
        type="button"
        className="arcade-seat-avatar arcade-profile-trigger"
        onClick={() => void toggle()}
        aria-label={`View ${name}'s player profile`}
        aria-expanded={open}
        style={{ width: size, height: size }}
      >
        {!failed ? (
          <img
            src={`/api/arcade/avatar/${id}`}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
          />
        ) : <>{initials(name) || <UserRound size={14} />}</>}
      </button>
      {open ? (
        <span className="arcade-profile-card" role="dialog" aria-label={`${name}'s profile`}>
          <b>{profile?.name || name}</b>
          {profile?.username ? <small>@{profile.username}</small> : null}
          {loading ? <small>Loading player card…</small> : null}
          {error ? <small>{error}</small> : null}
          {stat ? (
            <small>{stat.wins}W · {stat.losses}L · {stat.draws}D{["connect4", "reversi", "tictactoe"].includes(game) ? ` · ${stat.rating} rating` : ""}</small>
          ) : profile && !loading ? <small>No {game} results yet</small> : null}
          <button type="button" onClick={() => setOpen(false)} aria-label="Close player profile">×</button>
        </span>
      ) : null}
    </span>
  );
}
