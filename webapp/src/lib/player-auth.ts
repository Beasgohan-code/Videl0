import crypto from "node:crypto";

/**
 * The public arcade's identity: a Telegram account, proved by the Mini App.
 *
 * This is deliberately a *different* cookie and a different signing prefix
 * from the owner session. A player token can never satisfy `validOwnerCookie`,
 * and the owner token is not accepted here — the two powers never mix.
 */
export const PLAYER_COOKIE = "videl_player";
export const PLAYER_COOKIE_EMBEDDED = "videl_player_embedded";
const TTL = 30 * 86400;
const PREFIX = "videl-player-v1:";

export type Player = {
  id: number;
  name: string;
  username?: string | null;
  photo_url?: string | null;
};

function sign(value: string): string | null {
  const secret = process.env.WEBAPP_SECRET;
  return secret
    ? crypto.createHmac("sha256", secret).update(PREFIX + value).digest("hex")
    : null;
}

export function playerMarker(
  player: Player,
  now = Math.floor(Date.now() / 1000),
): string | null {
  const value = Buffer.from(
    JSON.stringify({
      sub: player.id,
      name: player.name,
      iat: now,
      exp: now + TTL,
      nonce: crypto.randomBytes(12).toString("hex"),
    }),
  ).toString("base64url");
  const signature = sign(value);
  return signature ? `${value}.${signature}` : null;
}

export function playerCookies(player: Player): string[] {
  const marker = playerMarker(player);
  if (!marker) return [];
  return [
    `${PLAYER_COOKIE}=${marker}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${TTL}`,
    `${PLAYER_COOKIE_EMBEDDED}=${marker}; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=${TTL}`,
  ];
}

export function clearedPlayerCookies(): string[] {
  return [
    `${PLAYER_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
    `${PLAYER_COOKIE_EMBEDDED}=; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=0`,
  ];
}

export function validPlayer(
  req: Request,
  now = Math.floor(Date.now() / 1000),
): Player | null {
  const header = req.headers.get("cookie") || "";
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (![PLAYER_COOKIE, PLAYER_COOKIE_EMBEDDED].includes(name)) continue;
    const token = rest.join("=");
    if (token.length > 2048) continue;
    const [value, signature, extra] = token.split(".");
    if (!value || extra !== undefined || !/^[a-f0-9]{64}$/.test(signature || "")) continue;
    const expected = sign(value);
    if (
      !expected ||
      !crypto.timingSafeEqual(Buffer.from(signature, "hex"), Buffer.from(expected, "hex"))
    )
      continue;
    try {
      const session = JSON.parse(Buffer.from(value, "base64url").toString());
      if (
        !Number.isSafeInteger(session.sub) ||
        session.sub <= 0 ||
        !Number.isSafeInteger(session.iat) ||
        !Number.isSafeInteger(session.exp) ||
        session.iat > now + 60 ||
        session.exp <= now ||
        session.exp - session.iat !== TTL
      )
        continue;
      return { id: session.sub, name: String(session.name || "Player").slice(0, 64) };
    } catch {
      continue;
    }
  }
  return null;
}

export function crossSite(req: Request): boolean {
  const origin = req.headers.get("origin");
  return Boolean(
    (origin && origin !== new URL(req.url).origin) ||
      req.headers.get("sec-fetch-site") === "cross-site",
  );
}

/** The player or a ready-made refusal. State changes also refuse cross-site. */
export function playerRequired(req: Request): { player: Player } | { denied: Response } {
  if (!["GET", "HEAD", "OPTIONS"].includes(req.method) && crossSite(req))
    return {
      denied: Response.json(
        { ok: false, error: "Cross-site requests are not allowed" },
        { status: 403 },
      ),
    };
  const player = validPlayer(req);
  if (!player)
    return {
      denied: Response.json(
        { ok: false, error: "Sign in with Telegram to play", code: "SIGN_IN" },
        { status: 401, headers: { "Cache-Control": "no-store" } },
      ),
    };
  return { player };
}

/**
 * The backend trusts this assertion instead of a bare user id, so a request
 * that reaches it without passing through this app cannot name anyone.
 */
export function actorHeaders(playerId: number, now = Math.floor(Date.now() / 1000)): Record<string, string> {
  const secret = process.env.WEBAPP_SECRET?.trim();
  if (!secret) return {};
  const expires = now + 50;
  const signature = crypto
    .createHmac("sha256", secret)
    .update(`${playerId}|${expires}`)
    .digest("hex");
  return {
    "X-Videl-Actor": String(playerId),
    "X-Videl-Actor-Exp": String(expires),
    "X-Videl-Actor-Sig": signature,
  };
}
