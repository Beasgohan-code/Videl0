import { NextRequest } from "next/server";

// Videl © 2026 — Channel Post API (Bot API 10.3)
// POST { chat_id, text, parse_mode?, media_url?, buttons? }
// Uses BOT_TOKEN server-side only. Supports text + photo + inline keyboard.

export const dynamic = "force-dynamic";

function getToken(): string {
  return process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || process.env.TG_BOT_TOKEN || "";
}

function tgApiUrl(method: string, token: string) {
  return `https://api.telegram.org/bot${token}/${method}`;
}

export async function POST(req: NextRequest) {
  const token = getToken();
  if (!token) return Response.json({ ok: false, error: "BOT_TOKEN not set in env" }, { status: 500 });

  let body: any;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const chat_id = String(body.chat_id || "").trim();
  const text = String(body.text || "").trim();
  const parse_mode = (body.parse_mode as string) || "HTML";
  const media_url = body.media_url ? String(body.media_url).trim() : undefined;
  const buttonsRaw = body.buttons ? String(body.buttons).trim() : undefined;

  if (!chat_id) return Response.json({ ok: false, error: "chat_id required (e.g. @channel or -100…)" }, { status: 400 });
  if (!text && !media_url) return Response.json({ ok: false, error: "text or media_url required" }, { status: 400 });

  // Parse buttons JSON → inline_keyboard
  let reply_markup: any = undefined;
  if (buttonsRaw) {
    try {
      const parsed = JSON.parse(buttonsRaw);
      const arr = Array.isArray(parsed) ? parsed : [parsed];
      // Normalize: support [{text,url}] or [[{text,url}]]
      const keyboard = Array.isArray(arr[0]) ? arr : [arr];
      const inline_keyboard = keyboard.map((row: any) =>
        (Array.isArray(row) ? row : [row]).map((b: any) => ({
          text: String(b.text || "Open"),
          url: String(b.url || b.href || "https://t.me/Videl0Bot"),
        }))
      );
      reply_markup = { inline_keyboard };
    } catch {
      // also support simple "Text | https://…" lines
      const lines = buttonsRaw.split("\n").filter(Boolean);
      if (lines.length) {
        reply_markup = {
          inline_keyboard: lines.map(line => {
            const [t, u] = line.split("|").map(s => s.trim());
            return [{ text: t || "Open", url: u || "https://t.me/Videl0Bot" }];
          }),
        };
      }
    }
  }

  try {
    let payload: any = {
      chat_id,
      parse_mode: parse_mode === "Markdown" ? "Markdown" : "HTML",
      disable_web_page_preview: false,
    };
    if (reply_markup) payload.reply_markup = reply_markup;

    let method = "sendMessage";
    if (media_url && /^https?:\/\//i.test(media_url)) {
      payload.caption = text;
      payload.photo = media_url;
      method = "sendPhoto";
      // For sendPhoto, parse_mode goes with caption
      payload.parse_mode = parse_mode === "Markdown" ? "Markdown" : "HTML";
      delete (payload as any).text;
      payload.caption = text;
    } else {
      payload.text = text;
    }

    const r = await fetch(tgApiUrl(method, token), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const j = await r.json();
    if (!j.ok) {
      return Response.json({ ok: false, error: j.description || "Telegram API error", raw: j }, { status: 400 });
    }
    return Response.json({ ok: true, chat_id, message_id: j.result?.message_id, via: "bot" });
  } catch (e: any) {
    return Response.json({ ok: false, error: String(e?.message || e) }, { status: 500 });
  }
}

export async function GET() {
  return Response.json({ ok: true, usage: "POST {chat_id, text, parse_mode?, media_url?, buttons?}", note: "Channel Post Studio — Bot API 10.3" });
}
