import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";
/** Public aggregate totals only. Private diagnostics and records stay owner-only. */
export async function GET(){
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 try{
  const r=await fetch(`${backend}/internal/stats`,{headers:{"X-Videl-Internal":secret},cache:"no-store",signal:AbortSignal.timeout(12000)});
  const d=await r.json();if(!r.ok||!d.ok)return Response.json({ok:false,error:d.error||"Live MongoDB totals unavailable"},{status:503});
  const source=d.stats;
  if(!source||![source.chats,source.users,source.plays].every(n=>Number.isSafeInteger(n)&&n>=0))return Response.json({ok:false,error:"Backend did not return valid live counts"},{status:502});
  return Response.json({ok:true,stats:{chats:source.chats,users:source.users,plays:source.plays,uptime:source.uptime},measured_at:new Date().toISOString(),source:"bot-mongodb"},{headers:{"Cache-Control":"no-store"}});
 }catch{return Response.json({ok:false,error:"Cannot reach the bot backend for live totals"},{status:503})}
}
