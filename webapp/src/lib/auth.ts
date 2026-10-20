import crypto from "node:crypto";

export function ownerMarker(): string | null {
  const secret = process.env.WEBAPP_SECRET || "";
  if (!secret) return null;
  return crypto.createHmac("sha256", secret).update("videl-owner-cookie-v1").digest("hex");
}

export function validOwnerCookie(req: Request): boolean {
  const expected = ownerMarker();
  if (!expected) return false;
  const cookieHeader = req.headers.get("cookie") || "";
  const received = cookieHeader.split(";").map(part => part.trim()).find(part => part.startsWith("videl_owner="))?.slice("videl_owner=".length) || "";
  if (!/^[a-f0-9]{64}$/i.test(received)) return false;
  return crypto.timingSafeEqual(Buffer.from(received, "hex"), Buffer.from(expected, "hex"));
}

export function ownerRequired(req: Request): Response | null {
  return validOwnerCookie(req) ? null : Response.json({ ok: false, error: "Owner authentication required" }, { status: 401 });
}
