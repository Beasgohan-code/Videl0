import { ownerRequired } from "@/lib/auth";
import { groupCall, validBulk } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

/** Apply one preset or protection patch to up to 15 served groups. */
export async function POST(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const body = await req.json().catch(() => null);
  const selection = validBulk(body);
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
