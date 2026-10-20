export function backendUrl(): string | null {
  const configured = process.env.VIDEL_BACKEND_URL?.trim().replace(/\/+$/, "");
  if (configured) return configured;
  if (process.env.VERCEL) return null;
  return `http://127.0.0.1:${process.env.VIDEL_BACKEND_PORT || "10000"}`;
}

export function internalSecret(): string {
  return process.env.WEBAPP_SECRET?.trim() || "";
}

export function unavailableBackend() {
  return Response.json(
    { ok: false, code: "BACKEND_NOT_CONFIGURED", error: "Videl backend URL is not configured. Set VIDEL_BACKEND_URL in Vercel." },
    { status: 503 },
  );
}

/**
 * Why a backend call failed, in words the UI can act on:
 *  - NOT_CONFIGURED  a Vercel env var is missing
 *  - WAKING          Render's free instance is starting (typical 10–50 s)
 *  - REJECTED        the backend answered but refused the shared secret
 *  - UNREACHABLE     the backend answered with a server error
 */
export type BackendCode = "NOT_CONFIGURED" | "WAKING" | "REJECTED" | "UNREACHABLE";

export type BackendResult = {
  ok: boolean;
  status: number;
  payload: Record<string, unknown>;
  text?: string;
  html?: boolean;
  code?: BackendCode;
  hint?: string;
  attempts: number;
  ms: number;
};

const HINTS: Record<BackendCode, string> = {
  NOT_CONFIGURED: "Add VIDEL_BACKEND_URL and WEBAPP_SECRET in Vercel → Settings → Environment Variables, then redeploy the frontend.",
  WAKING: "The Render free instance sleeps when idle. It is starting now — this usually takes 20–50 seconds; retrying automatically.",
  REJECTED: "The backend rejected WEBAPP_SECRET. Copy the same value from Render into Vercel (or delete and recreate it), then redeploy both.",
  UNREACHABLE: "The backend answered with an error. Open Render → Logs for the deploy and confirm the service is live and MongoDB is connected.",
};

function isWakeFailure(error: unknown) {
  const name = (error as { name?: string } | null)?.name;
  return name === "TimeoutError" || name === "AbortError";
}

/**
 * Call the Render backend with cold-start aware timeouts.
 *
 * Render's free tier suspends idle services; the first request after a sleep
 * can take far longer than a default timeout. Retrying once with a long budget
 * turns "backend unreachable" into a normal, slightly slower request.
 */
export async function callBackend(
  path: string,
  init: RequestInit = {},
  { timeoutMs = 12000, attempts = 1 }: { timeoutMs?: number; attempts?: number } = {},
): Promise<BackendResult> {
  const started = Date.now();
  const backend = backendUrl();
  const secret = internalSecret();
  if (!backend || !secret) {
    return { ok: false, status: 503, payload: { ok: false, code: "BACKEND_NOT_CONFIGURED", error: "Videl backend URL or WEBAPP_SECRET is not configured." }, code: "NOT_CONFIGURED", hint: HINTS.NOT_CONFIGURED, attempts: 0, ms: 0 };
  }
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= Math.max(1, attempts); attempt++) {
    try {
      const response = await fetch(`${backend}${path}`, {
        ...init,
        headers: { ...(init.headers || {}), "X-Videl-Internal": secret },
        cache: "no-store",
        signal: AbortSignal.timeout(timeoutMs),
      });
      const text = await response.text().catch(() => "");
      let payload: Record<string, unknown> = {};
      try {
        payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      } catch {
        payload = {};
      }
      const html = /^\s*<(?:!doctype|html|h1)/i.test(text);
      if (response.status === 401 || response.status === 403) {
        return { ok: false, status: response.status, payload, text, html, code: "REJECTED", hint: HINTS.REJECTED, attempts: attempt, ms: Date.now() - started };
      }
      return { ok: response.ok && payload.ok !== false, status: response.status, payload, text, html, attempts: attempt, ms: Date.now() - started };
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await new Promise((resolve) => setTimeout(resolve, 900 * attempt));
    }
  }
  const code: BackendCode = isWakeFailure(lastError) ? "WAKING" : "UNREACHABLE";
  return {
    ok: false,
    status: 503,
    payload: { ok: false, code: code === "WAKING" ? "BACKEND_WAKING" : "BACKEND_UNREACHABLE", error: HINTS[code] },
    code,
    hint: HINTS[code],
    attempts: Math.max(1, attempts),
    ms: Date.now() - started,
  };
}
