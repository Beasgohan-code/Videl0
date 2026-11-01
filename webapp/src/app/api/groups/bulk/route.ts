import { ownerRequired } from "@/lib/auth";
import { groupCall, validBulk } from "@/lib/group-backend";
import { readJsonLimited } from "@/lib/request-body";

export const dynamic = "force-dynamic";

/** Apply one preset or protection patch to up to 15 served groups. */
export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const parsed = await readJsonLimited(req, 16 * 1024);
  if (!parsed.ok)
    return Response.json(
      { ok: false, error: parsed.status === 413 ? "Bulk updates are limited to 16 KB" : "A valid JSON request is required" },
      { status: parsed.status },
    );
  const selection = validBulk(parsed.value);
  if (!selection)
    return Response.json(
      { ok: false, error: "Choose 1–15 groups and a preset or protection change" },
      { status: 400 },
    );
  return groupCall("/internal/chats/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_ids: selection.chatIds,
      action: selection.action,
      ...(selection.preset ? { preset: selection.preset } : {}),
      ...(selection.settings ? { settings: selection.settings } : {}),
    }),
  });
}
