import {ownerRequired} from '@/lib/auth';
import {backendUrl,internalSecret,unavailableBackend} from '@/lib/backend';
export const dynamic='force-dynamic';
export async function GET(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 const source=new URL(req.url),params=new URLSearchParams();
 for(const key of ['chat_id','message_id']){const value=source.searchParams.get(key);if(value)params.set(key,value);}
 try{const response=await fetch(`${backend}/internal/inbox-media?${params}`,{headers:{'X-Videl-Internal':secret},cache:'no-store',signal:AbortSignal.timeout(30000)});
  const headers=new Headers({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
  headers.set('Content-Type',response.headers.get('content-type')||'application/octet-stream');
  const disposition=response.headers.get('content-disposition');if(disposition)headers.set('Content-Disposition',disposition);
  return new Response(response.body,{status:response.status,headers});
 }catch{return Response.json({ok:false,error:'Attachment unavailable.'},{status:503});}
}
export async function POST(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 if(Number(req.headers.get('content-length')||0)>4*1024*1024+65536)return Response.json({ok:false,error:'Uploads are limited to 4 MB.'},{status:413});
 try{const incoming=await req.formData(),file=incoming.get('file');
  if(!(file instanceof Blob)||file.size===0||file.size>4*1024*1024||incoming.has('as_user'))return Response.json({ok:false,error:'Choose a bot attachment of up to 4 MB.'},{status:400});
  const body=new FormData();body.set('file',file,'upload');
  for(const key of ['chat_id','kind','text','message_id','request_id']){const value=incoming.get(key);if(typeof value==='string')body.set(key,value);}
  const response=await fetch(`${backend}/internal/inbox-media`,{method:'POST',headers:{'X-Videl-Internal':secret},body,cache:'no-store',signal:AbortSignal.timeout(60000)});
  return Response.json(await response.json(),{status:response.status,headers:{'Cache-Control':'no-store'}});
 }catch{return Response.json({ok:false,error:'Attachment delivery unconfirmed. Check Telegram before resending.'},{status:503});}
}
