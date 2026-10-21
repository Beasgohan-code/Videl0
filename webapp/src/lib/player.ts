"use client";
import { useCallback, useEffect, useState } from "react";
import { telegramLaunchData } from "./telegram-launch";

export type Stat = {
  wins: number;
  losses: number;
  draws: number;
  rating: number;
  games: number;
};

export type Player = {
  id: number;
  name: string;
  username?: string | null;
  photo_url?: string | null;
  stats?: Record<string, Stat>;
};

/** The signed launch payload Telegram hands to a Mini App, if this is one. */
export function launchData(): string {
  const sdk = (window as unknown as { Telegram?: { WebApp?: { initData?: string } } })
    .Telegram?.WebApp?.initData;
  return telegramLaunchData(
    sdk,
    window.location.search,
    window.location.hash,
  );
}

export async function loadSession(): Promise<Player | null> {
  const response = await fetch("/api/session", { cache: "no-store" });
  if (!response.ok) return null;
  const data = await response.json();
  return data?.player ?? null;
}

export async function signIn(): Promise<Player> {
  const initData = launchData();
  if (!initData)
    throw new Error(
      "Open Videl inside Telegram to sign in. The arcade uses your Telegram account, not a password.",
    );
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData }),
    cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok)
    throw new Error(data.error || "Telegram could not confirm who you are. Try again.");
  return data.player as Player;
}

export async function signOut(): Promise<void> {
  await fetch("/api/session", { method: "DELETE", cache: "no-store" }).catch(() => {});
}

/**
 * One hook for both public screens. `undefined` means "still checking",
 * `null` means "signed out" — the difference is what stops a sign-in card
 * flashing for a player who is already signed in.
 */
export function usePlayerSession() {
  const [player, setPlayer] = useState<Player | null | undefined>(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    loadSession()
      .then((value) => {
        if (alive) setPlayer(value);
      })
      .catch(() => {
        if (alive) setPlayer(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const enter = useCallback(async () => {
    setError("");
    try {
      const value = await signIn();
      setPlayer(value);
      return value;
    } catch (failure) {
      setError((failure as Error).message);
      return null;
    }
  }, []);

  const leave = useCallback(async () => {
    await signOut();
    setPlayer(null);
  }, []);

  return { player, error, signIn: enter, signOut: leave };
}
