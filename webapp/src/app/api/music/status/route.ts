import { ownerRequired } from "@/lib/auth";
import { callBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const taskId = new URL(req.url).searchParams.get("task_id") || "";
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(taskId)) {
    return Response.json({ ok: false, error: "Invalid music task ID" }, { status: 400 });
  }
  const result = await callBackend(
    `/internal/music/status?task_id=${encodeURIComponent(taskId)}`,
    {},
    { timeoutMs: 8_000, attempts: 1 },
  );
  return Response.json(result.payload, {
    status: result.status,
    headers: { "Cache-Control": "no-store" },
  });
}
