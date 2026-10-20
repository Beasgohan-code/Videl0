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
  return Response.json({ ok: false, error: "Videl backend URL is not configured" }, { status: 503 });
}
