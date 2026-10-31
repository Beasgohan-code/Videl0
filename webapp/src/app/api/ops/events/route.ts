import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Versioned, 24-hour feed containing commands only; no member or chat IDs. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const result = await callBackend("/internal/ops/events", {}, { timeoutMs: 5_000, attempts: 1 });
  if (!result.ok || result.payload.schema_version !== 1 || !Array.isArray(result.payload.events)) {
    return Response.json({ ok: false, schema_version: 1, events: [] }, {
      status: result.status || 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
  const events = result.payload.events.slice(0, 20).flatMap((event: unknown) => {
    if (!event || typeof event !== "object") return [];
    const item = event as Record<string, unknown>;
    if (item.schema_version !== 1 || item.type !== "command" || typeof item.command !== "string" || !/^[a-z0-9_]{1,64}$/.test(item.command)) return [];
    const chatType = ["private", "group", "supergroup", "channel"].includes(String(item.chat_type)) ? item.chat_type : "unknown";
    const at = typeof item.at === "string" && Number.isFinite(Date.parse(item.at)) ? item.at : null;
    return [{ schema_version: 1, type: "command", command: item.command, chat_type: chatType, at }];
  });
  return Response.json({ ok: true, schema_version: 1, window_hours: 24, events }, {
    headers: { "Cache-Control": "no-store" },
  });
}
