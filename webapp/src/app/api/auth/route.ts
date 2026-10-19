import { NextRequest } from "next/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";

function verify(user: any, botToken: string): boolean {
  if (!user?.hash || !botToken) return false;
  const { hash, ...rest } = user;
  const str = Object.keys(rest).sort().map(k => `${k}=${rest[k]}`).join("\n");
  const secret = crypto.createHash("sha256").update(botToken).digest();
  const calc = crypto.createHmac("sha256", secret).update(str).digest("hex");
  return calc === hash;
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.id) return Response.json({ ok: false, error: "Missing user" }, { status: 400 });

  const token = process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "";
  const ownerId = process.env.OWNER_ID || process.env.NEXT_PUBLIC_OWNER_ID || "";

  if (!token) return Response.json({ ok: false, error: "BOT_TOKEN not set" }, { status: 500 });
  if (!ownerId) return Response.json({ ok: false, error: "OWNER_ID not set" }, { status: 500 });

  const ok = verify(body, token);
  if (!ok) return Response.json({ ok: false, error: "Invalid hash — check BOT_TOKEN / domain at @BotFather /setdomain" }, { status: 401 });

  const isOwner = String(body.id) === String(ownerId);
  if (!isOwner) return Response.json({ ok: false, error: `Not owner. You: ${body.id}, owner: ${ownerId}` }, { status: 403 });

  // Simple owner session: set httpOnly cookie (1 year)
  const res = Response.json({ ok: true, user: body, owner: true });
  // We store a signed marker; real check is client + this endpoint
  const marker = crypto.createHmac("sha256", token).update(String(body.id)).digest("hex");
  res.headers.set("Set-Cookie", `videl_owner=${marker}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000`);
  return res;
}

export async function GET(req: NextRequest) {
  const token = process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "";
  const ownerId = process.env.OWNER_ID || "";
  const ck = req.cookies.get("videl_owner")?.value;
  if (!ck || !token || !ownerId) return Response.json({ ok: false, owner: false });
  const expect = crypto.createHmac("sha256", token).update(String(ownerId)).digest("hex");
  return Response.json({ ok: ck === expect, owner: ck === expect });
}
