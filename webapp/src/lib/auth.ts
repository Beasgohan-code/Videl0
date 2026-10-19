/**
 * Videl — Telegram Login verification + Owner gate
 * Verifies Telegram Login Widget hash via HMAC_SHA256 with BOT_TOKEN
 * Only OWNER_ID can access dashboard; others get guest view
 */

import crypto from "crypto";

export type TgUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

export function verifyTelegramAuth(data: TgUser, botToken: string): boolean {
  if (!data.hash || !botToken) return false;
  const { hash, ...rest } = data;
  const checkString = Object.keys(rest)
    .sort()
    .map((k) => `${k}=${(rest as any)[k]}`)
    .join("\n");
  const secret = crypto.createHash("sha256").update(botToken).digest();
  const hmac = crypto.createHmac("sha256", secret).update(checkString).digest("hex");
  return hmac === hash;
}

export function isOwnerId(userId: number, ownerId: number): boolean {
  if (!ownerId || !userId) return false;
  return String(userId) === String(ownerId);
}

export function getOwnerIdFromEnv(): number {
  const v = process.env.OWNER_ID || process.env.NEXT_PUBLIC_OWNER_ID || "";
  return parseInt(v, 10) || 0;
}

// Client helper: read stored tg user
export function getStoredUser(): TgUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("videl_tg_user");
    if (!raw) return null;
    return JSON.parse(raw) as TgUser;
  } catch { return null; }
}

export function storeUser(user: TgUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem("videl_tg_user", JSON.stringify(user));
}

export function clearUser() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("videl_tg_user");
}
