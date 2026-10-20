import test from 'node:test';
import assert from 'node:assert/strict';
import {ownerMarker} from '../src/lib/auth';
import {GET as conversations} from '../src/app/api/conversations/route';
import {GET as groupView} from '../src/app/api/group-view/route';
import {GET as workspace} from '../src/app/api/inbox-workspace/route';

test('old backend route 404s explain rollout, but real JSON not-found responses remain intact',async()=>{
 const previousFetch=globalThis.fetch;
 const previousSecret=process.env.WEBAPP_SECRET,previousBackend=process.env.VIDEL_BACKEND_URL;
 process.env.WEBAPP_SECRET='offline-rollout';process.env.VIDEL_BACKEND_URL='https://backend.test';
 try{
  for(const handler of [conversations,groupView,workspace]){
   const request=()=>new Request('https://studio.test/api/test',{headers:{cookie:`videl_owner=${ownerMarker()}`}});
   globalThis.fetch=async()=>new Response('<h1>Not found</h1>',{status:404,headers:{'content-type':'text/html'}});
   const missingRoute=await handler(request());assert.equal(missingRoute.status,503);
   assert.equal((await missingRoute.json()).code,'BACKEND_UPDATE_REQUIRED');
   globalThis.fetch=async()=>Response.json({ok:false,error:'Chat not found'},{status:404});
   const missingChat=await handler(request());assert.equal(missingChat.status,404);
   assert.deepEqual(await missingChat.json(),{ok:false,error:'Chat not found'});
  }
 }finally{
  globalThis.fetch=previousFetch;
  for(const [key,value] of [['WEBAPP_SECRET',previousSecret],['VIDEL_BACKEND_URL',previousBackend]] as const){if(value===undefined)delete process.env[key];else process.env[key]=value;}
 }
});
