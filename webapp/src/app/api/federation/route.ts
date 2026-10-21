import { ownerRequired } from "@/lib/auth";
import { groupCall } from "@/lib/group-backend";

export const dynamic = "force-dynamic";

/** Every federation the bot knows, with its groups and ban totals. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  return groupCall("/internal/federation");
}
