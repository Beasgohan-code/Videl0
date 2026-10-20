import crypto from "node:crypto";
import { OWNER_ID } from "./access";
const TTL = 86400;
function sign(value: string): string | null {
  const secret = process.env.WEBAPP_SECRET;
  return secret
    ? crypto
        .createHmac("sha256", secret)
        .update(`videl-session-v2:${value}`)
        .digest("hex")
    : null;
}
/** Rotatable, expiring session bound to the one allowed Telegram account. */
export function ownerMarker(
  now = Math.floor(Date.now() / 1000),
): string | null {
  const value = Buffer.from(
    JSON.stringify({
      sub: OWNER_ID,
      iat: now,
      exp: now + TTL,
      nonce: crypto.randomBytes(16).toString("hex"),
    }),
  ).toString("base64url");
  const signature = sign(value);
  return signature ? `${value}.${signature}` : null;
}
export function validOwnerCookie(
  req: Request,
  now = Math.floor(Date.now() / 1000),
): boolean {
  return (req.headers.get("cookie") || "").split(";").some((part) => {
    const [name, ...rest] = part.trim().split("=");
    if (!["videl_owner", "videl_owner_embedded"].includes(name)) return false;
    const token = rest.join("=");
    if (token.length > 1024) return false;
    const [value, signature, extra] = token.split(".");
    if (
      !value ||
      extra !== undefined ||
      !/^[a-f0-9]{64}$/.test(signature || "")
    )
      return false;
    const expected = sign(value);
    if (
      !expected ||
      !crypto.timingSafeEqual(
        Buffer.from(signature, "hex"),
        Buffer.from(expected, "hex"),
      )
    )
      return false;
    try {
      const session = JSON.parse(Buffer.from(value, "base64url").toString());
      return (
        session.sub === OWNER_ID &&
        Number.isSafeInteger(session.iat) &&
        Number.isSafeInteger(session.exp) &&
        session.iat <= now + 60 &&
        session.exp > now &&
        session.exp - session.iat === TTL
      );
    } catch {
      return false;
    }
  });
}
export function crossSiteRequest(req: Request): boolean {
  const origin = req.headers.get("origin");
  return !!(
    (origin && origin !== new URL(req.url).origin) ||
    req.headers.get("sec-fetch-site") === "cross-site"
  );
}
export function ownerRequired(req: Request): Response | null {
  if (!["GET", "HEAD", "OPTIONS"].includes(req.method) && crossSiteRequest(req))
    return Response.json(
      { ok: false, error: "Cross-site requests are not allowed" },
      { status: 403 },
    );
  return validOwnerCookie(req)
    ? null
    : Response.json(
        { ok: false, error: "Owner authentication required" },
        { status: 401, headers: { "Cache-Control": "no-store" } },
      );
}
