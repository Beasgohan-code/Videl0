/**
 * Release identity shared by the Settings panel and its route.
 *
 * Two deployments serve this product: the Next.js panel on Vercel and the bot
 * backend on Render. When they drift, features fail in confusing ways — the
 * panel offers a switch the running backend has never heard of. This module
 * makes the drift visible instead of discoverable by trial and error.
 */

export type ReleaseCheck = {
  web: string;
  backend: string | null;
  backendStatus: "ok" | "unreachable" | "not_configured";
  drift: "unknown" | "same" | "different";
  latencyMs: number | null;
  checkedAt: string;
  hint: string;
};

/** Vercel exposes the commit being served; short and lowercase for display. */
export function webRevision(value: string | undefined | null): string {
  const trimmed = (value || "").trim();
  return /^[0-9a-f]{7,40}$/i.test(trimmed) ? trimmed.slice(0, 7).toLowerCase() : "local";
}

/** Render reports its own revision, sometimes as a full sha and sometimes short. */
export function backendRevision(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return /^[0-9a-f]{7,40}$/i.test(trimmed) ? trimmed.slice(0, 7).toLowerCase() : null;
}

/**
 * Compare the two revisions. "unknown" is a real answer: without a backend
 * revision we must not claim the deployments match.
 */
export function compareRevisions(
  web: string,
  backend: string | null,
): ReleaseCheck["drift"] {
  if (!backend || web === "local") return "unknown";
  return web === backend ? "same" : "different";
}

export function buildReleaseCheck({
  web,
  backend,
  status,
  latencyMs,
  checkedAt,
}: {
  web: string;
  backend: string | null;
  status: ReleaseCheck["backendStatus"];
  latencyMs: number | null;
  checkedAt: string;
}): ReleaseCheck {
  const drift = compareRevisions(web, backend);
  const hint =
    status === "not_configured"
      ? "VIDEL_BACKEND_URL is not set in Vercel, so the panel cannot read the backend revision."
      : status === "unreachable"
        ? "The Render service did not answer. It may be waking from sleep; refresh in a minute."
        : drift === "same"
          ? "Panel and backend are serving the same commit."
          : drift === "different"
            ? "The panel and the bot backend are on different commits. Redeploy the one that is behind."
            : "The backend did not report a revision. Redeploy Render to publish one.";
  return { web, backend, backendStatus: status, drift, latencyMs, checkedAt, hint };
}

/** Short badge text; never louder than the evidence allows. */
export function driftLabel(check: ReleaseCheck): string {
  if (check.backendStatus === "not_configured") return "Backend not configured";
  if (check.backendStatus === "unreachable") return "Backend unreachable";
  if (check.drift === "same") return "In sync";
  if (check.drift === "different") return "Drifted";
  return "Revision unknown";
}
