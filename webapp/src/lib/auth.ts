import crypto from "node:crypto";

export function ownerMarker(): string | null {
  const secret = process.env.WEBAPP_SECRET || "";
  if (!secret) return null;
  return crypto
    .createHmac("sha256", secret)
    .update("videl-owner-cookie-v1")
    .digest("hex");
}

export function validOwnerCookie(req: Request): boolean {
  const expected = ownerMarker();
  if (!expected) return false;
  const cookieHeader = req.headers.get("cookie") || "";
  return cookieHeader.split(";").some((part) => {
    const [name, ...rest] = part.trim().split("=");
    if (name !== "videl_owner" && name !== "videl_owner_embedded") return false;
    const received = rest.join("=");
    return (
      /^[a-f0-9]{64}$/i.test(received) &&
      crypto.timingSafeEqual(
        Buffer.from(received, "hex"),
        Buffer.from(expected, "hex"),
      )
    );
  });
}

export function ownerRequired(req: Request): Response | null {
  const origin = req.headers.get("origin");
  if (
    !["GET", "HEAD", "OPTIONS"].includes(req.method) &&
    ((origin && origin !== new URL(req.url).origin) ||
      req.headers.get("sec-fetch-site") === "cross-site")
  )
    return Response.json(
      { ok: false, error: "Cross-site requests are not allowed" },
      { status: 403 },
    );
  return validOwnerCookie(req)
    ? null
    : Response.json(
        { ok: false, error: "Owner authentication required" },
        { status: 401 },
      );
}
