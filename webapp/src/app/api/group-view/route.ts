import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";

async function proxy(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const source = new URL(req.url);
  const params = new URLSearchParams();
  for (const key of ["chat_id", "before", "q", "sender", "info"]) {
    const value = source.searchParams.get(key);
    if (value !== null) params.set(key, value);
  }
  let body: string | undefined;
  if (req.method === "POST") {
    const raw = await req.text();
    if (raw.length > 20000) return Response.json({ ok: false, error: "Request body is too large" }, { status: 413 });
    try {
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object" || Array.isArray(data) || "as_user" in data) throw new Error();
      body = JSON.stringify(data);
    } catch {
      return Response.json({ ok: false, error: "A bot-only JSON action is required" }, { status: 400 });
    }
  }
  // Reads are safe to retry through a Render cold start; writes are not.
  const result = await callBackend(
    `/internal/group-view${params.size ? `?${params}` : ""}`,
    { method: req.method, headers: { "Content-Type": "application/json" }, body },
    req.method === "GET" ? { timeoutMs: 22000, attempts: 2 } : { timeoutMs: 55000, attempts: 1 },
  );
  if (result.html) {
    return Response.json(
      {
        ok: false,
        code: "BACKEND_UPDATE_REQUIRED",
        error: "The bot backend does not have the Bot Inbox API yet. Deploy the latest backend code before using message history or moderation.",
      },
      { status: 503 },
    );
  }
  if (!result.ok) {
    const payload = result.payload as Record<string, unknown>;
    // Real backend answers (for example "Chat not found") pass through intact.
    if (payload && Object.keys(payload).length)
      return Response.json(payload, { status: result.status, headers: { "Cache-Control": "no-store" } });
    return Response.json(
      { ok: false, code: result.code === "WAKING" ? "BACKEND_WAKING" : "BACKEND_UNREACHABLE", error: result.hint || "The bot backend did not answer. Check Telegram before repeating a submitted action." },
      { status: result.status, headers: { "Cache-Control": "no-store", ...(result.code === "WAKING" ? { "Retry-After": "5" } : {}) } },
    );
  }
  return Response.json(result.payload, { status: 200, headers: { "Cache-Control": "no-store" } });
}
export const GET = proxy;
export const POST = proxy;
