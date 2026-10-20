import { cleanTelegramHtml, visibleLength } from "@/lib/telegram-format";
import { NextRequest } from "next/server";
import { ownerRequired } from "@/lib/auth";
import { backendUrl, internalSecret, unavailableBackend } from "@/lib/backend";
export const dynamic = "force-dynamic";
export async function POST(req:NextRequest){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 const multipart=req.headers.get("content-type")?.includes("multipart/form-data");
 let body:Record<string,unknown>;let image:File|null=null;
 try{
  if(Number(req.headers.get("content-length")||0)>4400000)return Response.json({ok:false,error:"Image upload is too large (4 MB maximum)"},{status:413});
  if(multipart){const form=await req.formData();body=Object.fromEntries(form.entries());const value=form.get("image");if(value instanceof File)image=value}
  else{body=await req.json();if(!body||typeof body!=="object"||Array.isArray(body))throw new Error("Invalid body")}
 }catch{return Response.json({ok:false,error:"A valid post request is required"},{status:400})}
 const chat_id=String(body.chat_id||"").trim(),text=cleanTelegramHtml(String(body.text||"").trim()),media_url=String(body.media_url||"").trim();
 if(image&&(!["image/jpeg","image/png","image/webp"].includes(image.type)||image.size>4*1024*1024))return Response.json({ok:false,error:"Use a JPEG, PNG or WebP image under 4 MB"},{status:400});
 if(!chat_id||(!text&&!media_url&&!image))return Response.json({ok:false,error:"Choose a destination and add text or an image"},{status:400});
 if(visibleLength(text)>(image||media_url?1024:4096))return Response.json({ok:false,error:image||media_url?"Image captions allow 1,024 visible characters":"Posts allow 4,096 visible characters"},{status:400});
 const headers:Record<string,string>={"X-Videl-Internal":secret};let outgoing:BodyInit;
 if(image){const form=new FormData();form.set("image",image,image.name);form.set("chat_id",chat_id);form.set("text",text);form.set("parse_mode","HTML");if(body.buttons)form.set("buttons",typeof body.buttons==="string"?body.buttons:JSON.stringify(body.buttons));outgoing=form}
 else{headers["Content-Type"]="application/json";outgoing=JSON.stringify({chat_id,text,parse_mode:"HTML",media_url,buttons:body.buttons})}
 try{const r=await fetch(`${backend}/internal/channel-post`,{method:"POST",headers,body:outgoing,cache:"no-store",signal:AbortSignal.timeout(25000)});const payload=await r.json();if(image&&r.status===400&&String(payload.error).includes("JSON"))return Response.json({ok:false,error:"The Render backend needs the latest image-upload update. Download your design in the meantime."},{status:503});return Response.json(payload,{status:r.status,headers:{"Cache-Control":"no-store"}})}catch{return Response.json({ok:false,error:"Backend could not confirm delivery. Check Telegram before retrying."},{status:503})}
}
export async function GET(req:Request){const denied=ownerRequired(req);if(denied)return denied;return Response.json({ok:true,usage:"POST JSON text/media_url, or multipart image + chat_id + text + buttons"})}
