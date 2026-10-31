import { cleanTelegramHtml, visibleLength } from "@/lib/telegram-format";
import { NextRequest } from "next/server";
import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
import { normalizeBroadcastButtons } from "@/lib/broadcast";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl(), secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  if (Number(req.headers.get("content-length") || 0) > 4_400_000)
    return Response.json({ ok: false, error: "Broadcast image upload is too large (4 MB maximum)" }, { status: 413 });

  const multipart = req.headers.get("content-type")?.includes("multipart/form-data");
  let body: Record<string, unknown>, image: File | null = null;
  try {
    if (multipart) {
      const form = await req.formData();
      body = Object.fromEntries(form.entries());
      const candidate = form.get("image");
      if (candidate instanceof File) image = candidate;
    } else {
      const parsed = await req.json();
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid body");
      body = parsed as Record<string, unknown>;
    }
  } catch {
    return Response.json({ ok: false, error: "A valid broadcast request is required" }, { status: 400 });
  }

  const text = cleanTelegramHtml(String(body.text || "").trim());
  const scope = String(body.scope || "chats").trim();
  let rawButtons: unknown = body.buttons;
  if (typeof rawButtons === "string") {
    try { rawButtons = JSON.parse(rawButtons); } catch { return Response.json({ ok: false, error: "Invalid button layout" }, { status: 400 }); }
  }
  const buttons = normalizeBroadcastButtons(rawButtons);
  if (!["chats", "users", "all"].includes(scope))
    return Response.json({ ok: false, error: "Choose a valid broadcast audience" }, { status: 400 });
  if (buttons === null)
    return Response.json({ ok: false, error: "Buttons must use secure HTTPS links, with up to eight buttons of 64 characters each" }, { status: 400 });
  if (image && (!["image/jpeg", "image/png", "image/webp"].includes(image.type) || image.size > 4 * 1024 * 1024))
    return Response.json({ ok: false, error: "Use a JPEG, PNG or WebP image under 4 MB" }, { status: 400 });
  if (!text && !image)
    return Response.json({ ok: false, error: "Add announcement text or an image" }, { status: 400 });
  if (visibleLength(text) > (image ? 1024 : 4096))
    return Response.json({ ok: false, error: image ? "Image captions allow 1,024 visible characters" : "Broadcast text is limited to 4,096 visible characters" }, { status: 400 });

  try {
    let outgoing: BodyInit;
    const headers: Record<string, string> = { "X-Videl-Internal": secret };
    if (image) {
      const form = new FormData();
      form.set("image", image, image.name || "broadcast-image");
      form.set("text", text);
      form.set("scope", scope);
      form.set("buttons", JSON.stringify(buttons));
      outgoing = form;
    } else {
      headers["Content-Type"] = "application/json";
      outgoing = JSON.stringify({ text, scope, buttons });
    }
    const response = await fetch(`${backend}/internal/broadcast`, {
      method: "POST", headers, body: outgoing, cache: "no-store", signal: AbortSignal.timeout(25000),
    });
    const payload = await response.json();
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false, error: "Broadcast delivery could not be confirmed. Check Telegram before retrying; some recipients may already have received it." }, { status: 503 });
  }
}
