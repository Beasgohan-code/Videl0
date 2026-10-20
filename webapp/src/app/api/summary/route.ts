import { ownerRequired } from "@/lib/auth";
import { GET as stats } from "../stats/route";
export const dynamic = "force-dynamic";
/** Legacy URL retained for owner dashboard; no public bot totals. */
export async function GET(req: Request) {
  const denied = ownerRequired(req);
  return denied || stats(req);
}
