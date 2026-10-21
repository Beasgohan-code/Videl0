import {ownerRequired} from "@/lib/auth";
import {backendUrl,internalSecret,unavailableBackend} from "@/lib/backend";
import {cleanTelegramHtml} from "@/lib/telegram-format";
export const dynamic="force-dynamic";
async function proxy(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 let body:Record<string,unknown>|undefined;
 if(req.method!=="GET"){
  try{if(Number(req.headers.get("content-length")||0)>131072)throw new Error("A valid schedule request is required");body=await req.json();if(!body||typeof body!=="object"||Array.isArray(body))throw new Error("A valid schedule request is required");if(req.method==="POST"){if(!body.schedule_at||!body.request_id||typeof body.schedule_at!=="string")throw new Error("A valid schedule request is required");
   // The queue repeats and zones are typed: refuse a shape it would only
   // discover halfway through a write, with a sentence the owner can act on.
   const repeat=body.repeat??null;
   if(repeat!==null&&repeat!==""&&repeat!=="none"&&repeat!=="daily"&&repeat!=="weekly")throw new Error("Choose a daily or weekly repeat");
   const zone=body.timezone??null;
   if(zone!==null&&(typeof zone!=="string"||!zone.trim()||zone.length>64))throw new Error("Choose a valid timezone");
   const wall=body.wall_time??null;
   if(wall!==null&&(typeof wall!=="string"||!/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(wall)))throw new Error("Use a 24-hour HH:MM wall time");
   if(wall!==null&&zone===null)throw new Error("A wall time needs a timezone");
   body={...body,text:cleanTelegramHtml(String(body.text||"")),parse_mode:"HTML"}}}catch(error){return Response.json({ok:false,error:error instanceof Error&&error.message?error.message:"A valid schedule request is required"},{status:400})}
 }
 try{
  const response=await fetch(`${backend}/internal/scheduled-posts`,{method:req.method,headers:{"X-Videl-Internal":secret,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined,cache:"no-store",signal:AbortSignal.timeout(15000)});
  return Response.json(await response.json(),{status:response.status,headers:{"Cache-Control":"no-store"}});
 }catch{return Response.json({ok:false,error:"Queue status unconfirmed. Refresh before retrying."},{status:503})}
}
export const GET=proxy;export const POST=proxy;export const DELETE=proxy;
