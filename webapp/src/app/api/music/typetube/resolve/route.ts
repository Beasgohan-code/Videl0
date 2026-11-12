import { ownerRequired } from "@/lib/auth";
import { typeTubeResolveRoute } from "@/lib/typetube-routes";
import { getTypeTubeClient } from "@/server/typetube";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  return typeTubeResolveRoute(req, getTypeTubeClient);
}
