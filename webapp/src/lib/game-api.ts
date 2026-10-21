import { callBackend, unavailableBackend, type BackendResult } from "./backend";

/**
 * One shape for every arcade and manager answer: the backend's own body and
 * status, never a rewritten success. A 409 from a stale move must stay a 409
 * so the panel can reload instead of guessing.
 */
export function answer(result: BackendResult) {
  if (result.code === "NOT_CONFIGURED") return unavailableBackend();
  const status = result.ok ? 200 : result.status || 503;
  return Response.json(result.payload, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function forward(
  path: string,
  init: RequestInit = {},
  options: { timeoutMs?: number; attempts?: number } = {},
) {
  return answer(await callBackend(path, init, options));
}

export function jsonBody(body: unknown) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
