import { backendUrl } from "@/lib/backend";
export const dynamic = "force-dynamic";
export async function GET() {
  const backend = backendUrl();
  if (!backend) return Response.json({ status: "error", service: "Videl", error: "Videl backend URL is not configured" }, { status: 503 });
  try {
    const response = await fetch(`${backend}/health`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    const payload = await response.json();
    return Response.json(payload, { status: response.ok ? 200 : 503, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ status: "error", service: "Videl", error: "Backend health endpoint is unreachable" }, { status: 503 }); }
}
