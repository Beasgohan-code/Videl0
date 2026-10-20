import { callBackend, type BackendResult } from "@/lib/backend";
import { BULK_LIMIT, PRESET_ORDER, SETTING_KEYS } from "@/lib/group-admin";

/** How the group manager asks the Render backend for things. */

export const groupTimeout = { timeoutMs: 20000, attempts: 2 };

export function groupError(result: BackendResult): Response {
  const payload = result.payload as Record<string, unknown>;
  const message = String(payload.error || result.hint || "The bot backend did not answer");
  const headers: Record<string, string> = { "Cache-Control": "no-store" };
  if (result.code === "WAKING") headers["Retry-After"] = "5";
  // A 404 from an old Flask build is an HTML page, not JSON: the route does
  // not exist yet, which means Render is still running the previous release.
  if (result.html && (result.status === 404 || result.status === 405)) {
    return Response.json(
      {
        ok: false,
        code: "BACKEND_UPDATE_REQUIRED",
        error: "This panel needs the updated bot backend. Redeploy the Render service, then retry.",
      },
      { status: 501, headers },
    );
  }
  if (result.code === "WAKING") {
    return Response.json({ ok: false, code: "BACKEND_WAKING", error: message }, { status: 503, headers });
  }
  const status = result.status >= 400 ? result.status : 502;
  return Response.json(
    { ok: false, code: String(payload.code || result.code || "BACKEND_ERROR"), error: message },
    { status, headers },
  );
}

export async function groupCall(path: string, init?: RequestInit): Promise<Response> {
  const result = await callBackend(path, init, groupTimeout);
  if (!result.ok) return groupError(result);
  return Response.json(result.payload, { status: 200, headers: { "Cache-Control": "no-store" } });
}

export function parseChatId(value: unknown): number | null {
  const id = typeof value === "string" && value.trim() ? Number(value) : value;
  if (typeof id !== "number" || !Number.isSafeInteger(id) || id >= 0 || !id) return null;
  return id;
}

export function isSettingPatch(value: unknown): value is Record<string, boolean> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entries = Object.entries(value as Record<string, unknown>);
  if (!entries.length) return false;
  return entries.every(([key, item]) => SETTING_KEYS.includes(key) && typeof item === "boolean");
}

export function isActionBody(value: unknown): value is { action: string; [key: string]: unknown } {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value) && typeof (value as { action?: unknown }).action === "string";
}

export function validBulk(body: unknown): { chatIds: number[]; action: "preset" | "settings"; preset?: string; settings?: Record<string, boolean> } | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as { chat_ids?: unknown; action?: unknown; preset?: unknown; settings?: unknown };
  if (!Array.isArray(raw.chat_ids) || raw.chat_ids.length === 0 || raw.chat_ids.length > BULK_LIMIT) return null;
  const chatIds = raw.chat_ids.map(parseChatId);
  if (chatIds.some((id) => id === null)) return null;
  if (raw.action === "preset") {
    if (typeof raw.preset !== "string" || !PRESET_ORDER.includes(raw.preset as (typeof PRESET_ORDER)[number])) return null;
    return { chatIds: chatIds as number[], action: "preset", preset: raw.preset };
  }
  if (raw.action === "settings") {
    if (!isSettingPatch(raw.settings)) return null;
    return { chatIds: chatIds as number[], action: "settings", settings: raw.settings };
  }
  return null;
}
