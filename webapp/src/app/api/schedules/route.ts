import {ownerRequired} from "@/lib/auth";
import {backendUrl,internalSecret,unavailableBackend} from "@/lib/backend";
import {cleanTelegramHtml} from "@/lib/telegram-format";
export const dynamic="force-dynamic";
async function proxy(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 let body:Record<string,unknown>|undefined;
 if(req.method!=="GET"){
  try{if(Number(req.headers.get("content-length")||0)>131072)throw new Error();body=await req.json();if(!body||typeof body!=="object"||Array.isArray(body))throw new Error();if(req.method==="POST"){if(!body.schedule_at||!body.request_id)throw new Error();body={...body,text:cleanTelegramHtml(String(body.text||"")),parse_mode:"HTML"}}}catch{return Response.json({ok:false,error:"A valid schedule request is required"},{status:400})}
 }
 try{
  const response=await fetch(`${backend}/internal/scheduled-posts`,{method:req.method,headers:{"X-Videl-Internal":secret,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined,cache:"no-store",signal:AbortSignal.timeout(15000)});
  return Response.json(await response.json(),{status:response.status,headers:{"Cache-Control":"no-store"}});
 }catch{return Response.json({ok:false,error:"Queue status unconfirmed. Refresh before retrying."},{status:503})}
}
export const GET=proxy;export const POST=proxy;export const DELETE=proxy;
