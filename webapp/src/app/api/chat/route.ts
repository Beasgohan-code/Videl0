import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Videl © 2026 — Web Chat API (real user + bot)
// POST { chat_id, text, as_user? } — send via Telegram Bot API (bot) or proxy to Pyrogram userbot
// GET ?chat_id=xxx — history from Supabase videl_webchat (if configured) or empty

function getToken(): string {
  return process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || process.env.TG_BOT_TOKEN || "";
}
function getPythonBackend(): string {
  // Flask backend that has Pyrogram STRING_SESSION userbot for "as user" mode
  return process.env.BACKEND_URL || process.env.PYTHON_BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "";
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const chat_id = searchParams.get("chat_id");
  if (!chat_id) return Response.json({ items: [], note: "provide ?chat_id=xxx" });

  if (!supabase) {
    return Response.json({ items: [], note: "Supabase not configured — stateless mode" });
  }
  try {
    const { data, error } = await supabase
      .from("videl_webchat")
      .select("*")
      .eq("chat_id", String(chat_id))
      .order("created_at", { ascending: false })
      .limit(30);
    if (error) return Response.json({ items: [], error: error.message });
    return Response.json({ items: data || [] });
  } catch (e: any) {
    return Response.json({ items: [], error: String(e) });
  }
}

export async function POST(req: Request) {
  const token = getToken();
  let body: any;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }
  const chat_id = String(body.chat_id || "").trim();
  const text = String(body.text || "").trim();
  const as_user = Boolean(body.as_user);

  if (!chat_id) return Response.json({ ok: false, error: "chat_id required" }, { status: 400 });
  if (!text) return Response.json({ ok: false, error: "text required" }, { status: 400 });

  // Demo guard: "muhehehe" is local-only, don't hit Telegram
  if (chat_id.toLowerCase() === "muhehehe") {
    // Optionally log to Supabase even for demo
    if (supabase) {
      try {
        await supabase.from("videl_webchat").insert({ chat_id, content: text, from: as_user ? "user" : "bot", via: as_user ? "userbot" : "bot" });
      } catch {}
    }
    return Response.json({ ok: true, chat_id, message_id: Date.now(), via: as_user ? "userbot-demo" : "bot-demo", note: "muhehehe demo — not sent to Telegram, set real chat_id" });
  }

  // If as_user, try proxy to Python backend which has STRING_SESSION
  if (as_user) {
    const backend = getPythonBackend();
    if (backend) {
      try {
        const r = await fetch(`${backend.replace(/\/$/, "")}/api/user/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id, text }),
        });
        const j = await r.json();
        if (j.ok) {
          if (supabase) {
            try {
              await supabase.from("videl_webchat").insert({ chat_id, content: text, from: "owner", via: "userbot" });
            } catch {}
          }
          return Response.json({ ok: true, chat_id, message_id: j.message_id || j.id, via: "userbot" });
        }
        // fallthrough to bot on backend error
      } catch (e: any) {
        // proceed to bot fallback, surface backend error as warning
      }
    } else {
      // No backend configured — inform but still allow bot fallback
      // We will attempt bot send below; append note
    }
  }

  // Bot path (always available if token set)
  if (!token) return Response.json({ ok: false, error: "BOT_TOKEN not set; cannot send as bot. Configure BOT_TOKEN or BACKEND_URL for userbot." }, { status: 500 });

  try {
    const url = `https://api.telegram.org/bot${token}/sendMessage`;
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id, text, parse_mode: "HTML" }),
    });
    const j = await r.json();
    if (!j.ok) {
      return Response.json({ ok: false, error: j.description || "Telegram API error", raw: j }, { status: 400 });
    }
    if (supabase) {
      try {
        await supabase.from("videl_webchat").insert({ chat_id, content: text, from: "owner", via: as_user ? "userbot-fallback-bot" : "bot" });
      } catch {}
    }
    return Response.json({ ok: true, chat_id, message_id: j.result?.message_id, via: as_user ? "bot-fallback" : "bot" });
  } catch (e: any) {
    return Response.json({ ok: false, error: String(e?.message || e) }, { status: 500 });
  }
}
