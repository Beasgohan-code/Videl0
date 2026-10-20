import {ownerRequired} from '@/lib/auth';
import {backendUrl,internalSecret,unavailableBackend} from '@/lib/backend';
export const dynamic='force-dynamic';
async function proxy(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 const params=new URLSearchParams(),cid=new URL(req.url).searchParams.get('chat_id');if(cid!==null)params.set('chat_id',cid);
 let body:string|undefined;
 if(req.method==='POST'){
  const raw=await req.text();if(raw.length>20000)return Response.json({ok:false,error:'Request too large'},{status:413});
  try{const data=JSON.parse(raw);if(!data||typeof data!=='object'||Array.isArray(data))throw new Error();body=JSON.stringify(data);}
  catch{return Response.json({ok:false,error:'A JSON workspace action is required'},{status:400});}
 }
 try{
  const response=await fetch(`${backend}/internal/inbox-workspace${params.size?`?${params}`:''}`,{method:req.method,headers:{'Content-Type':'application/json','X-Videl-Internal':secret},body,cache:'no-store',signal:AbortSignal.timeout(15000)});
  if(response.status===404&&!response.headers.get('content-type')?.includes('application/json'))return Response.json({ok:false,code:'BACKEND_UPDATE_REQUIRED',error:'Workspace storage requires the updated bot backend. Deploy the latest backend code; editor text has not been saved or sent.'},{status:503});
  return Response.json(await response.json(),{status:response.status,headers:{'Cache-Control':'no-store'}});
 }catch{return Response.json({ok:false,error:'Workspace save was not confirmed. Refresh before retrying; nothing was sent to Telegram.'},{status:503});}
}
export const GET=proxy;export const POST=proxy;
