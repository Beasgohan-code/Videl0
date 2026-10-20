import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";

async function proxy(req: Request) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const backend = backendUrl(), secret = internalSecret();
  if (!backend || !secret) return unavailableBackend();
  const source = new URL(req.url);
  const params = new URLSearchParams();
  for (const key of ["chat_id", "before", "q", "sender"]) {
    const value = source.searchParams.get(key);
    if (value !== null) params.set(key, value);
  }
  let body: string | undefined;
  if (req.method === "POST") {
    const raw = await req.text();
    if (raw.length > 20000) return Response.json({ok:false,error:"Request body is too large"},{status:413});
    try {
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object" || Array.isArray(data) || "as_user" in data) throw new Error();
      body = JSON.stringify(data);
    } catch { return Response.json({ok:false,error:"A bot-only JSON action is required"},{status:400}); }
  }
  try {
    const response = await fetch(`${backend}/internal/group-view${params.size ? `?${params}` : ""}`, {
      method:req.method, headers:{"Content-Type":"application/json","X-Videl-Internal":secret},
      body, cache:"no-store", signal:AbortSignal.timeout(req.method === "GET" ? 15000 : 55000),
    });
    if(response.status===404&&!response.headers.get('content-type')?.includes('application/json'))return Response.json({ok:false,code:'BACKEND_UPDATE_REQUIRED',error:'The bot backend does not have the Bot Inbox API yet. Deploy the latest backend code before using message history or moderation.'},{status:503});
    return Response.json(await response.json(),{status:response.status,headers:{"Cache-Control":"no-store"}});
  } catch {
    return Response.json({ok:false,error:"Backend response unconfirmed. Check Telegram before repeating a submitted action."},{status:503});
  }
}
export const GET = proxy;
export const POST = proxy;
