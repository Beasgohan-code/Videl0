import {ownerRequired} from '@/lib/auth';
import {backendUrl,internalSecret,unavailableBackend} from '@/lib/backend';
export const dynamic='force-dynamic';
export async function GET(req:Request){
 const denied=ownerRequired(req);if(denied)return denied;
 const backend=backendUrl(),secret=internalSecret();if(!backend||!secret)return unavailableBackend();
 try{const response=await fetch(`${backend}/internal/bot-conversations`,{headers:{'X-Videl-Internal':secret},cache:'no-store',signal:AbortSignal.timeout(12000)});if(response.status===404&&!response.headers.get('content-type')?.includes('application/json'))return Response.json({ok:false,code:'BACKEND_UPDATE_REQUIRED',error:'Bot Inbox frontend is updated, but the bot backend is still on an older release. Deploy the latest repository code to the backend to enable conversations and message capture.'},{status:503});return Response.json(await response.json(),{status:response.status,headers:{'Cache-Control':'no-store'}});}
 catch{return Response.json({ok:false,error:'Bot conversations unavailable.'},{status:503});}
}
