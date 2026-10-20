import test from "node:test";
import assert from "node:assert/strict";
import {GET,POST} from "../src/app/api/group-view/route";
import {ownerMarker} from "../src/lib/auth";
import {telegramMessageLink,groupId,textUnits} from "../src/lib/group-view";

test('group inbox guards every proxy method before contacting the backend',async()=>{
 const old=globalThis.fetch;let calls=0;globalThis.fetch=async()=>{calls++;throw new Error('unexpected backend')};
 try {for(const [method,handler] of [['GET',GET],['POST',POST]] as const){
  const response=await handler(new Request('https://studio.test/api/group-view',{method}));
  assert.equal(response.status,401);
 }assert.equal(calls,0);}finally{globalThis.fetch=old;}
});
test('group inbox rejects cross-site writes even with an owner cookie',async()=>{
 const old=process.env.WEBAPP_SECRET;process.env.WEBAPP_SECRET='offline-viewer';
 try{const response=await POST(new Request('https://studio.test/api/group-view',{method:'POST',headers:{cookie:`videl_owner=${ownerMarker()}`,origin:'https://elsewhere.test'}}));assert.equal(response.status,403);}
 finally{if(old===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=old;}
});
test('group inbox proxy forwards only allowlisted filters and keeps the secret server-side',async()=>{
 const env={secret:process.env.WEBAPP_SECRET,backend:process.env.VIDEL_BACKEND_URL},oldFetch=globalThis.fetch;
 process.env.WEBAPP_SECRET='offline-viewer';process.env.VIDEL_BACKEND_URL='https://render.test';
 let endpoint='',headers:HeadersInit|undefined;
 globalThis.fetch=async(input,options)=>{endpoint=String(input);headers=options?.headers;return Response.json({ok:true,items:[]});};
 try{
  const response=await GET(new Request('https://studio.test/api/group-view?chat_id=-100123&q=a%26b&sender=123&token=malicious',{headers:{cookie:`videl_owner=${ownerMarker()}`}}));
  assert.equal(response.status,200);assert.ok(endpoint.includes('q=a%26b'));assert.ok(!endpoint.includes('token='));
  assert.equal(new Headers(headers).get('X-Videl-Internal'),'offline-viewer');
  assert.ok(!(await response.text()).includes('offline-viewer'));assert.equal(response.headers.get('cache-control'),'no-store');
 }finally{globalThis.fetch=oldFetch;for(const [key,value] of [['WEBAPP_SECRET',env.secret],['VIDEL_BACKEND_URL',env.backend]]){if(value===undefined)delete process.env[key!];else process.env[key!]=value;}}
});
test('group inbox cannot activate personal-account sending',async()=>{
 const env={secret:process.env.WEBAPP_SECRET,backend:process.env.VIDEL_BACKEND_URL};
 process.env.WEBAPP_SECRET='offline-viewer';process.env.VIDEL_BACKEND_URL='https://render.test';
 try{const response=await POST(new Request('https://studio.test/api/group-view',{method:'POST',headers:{cookie:`videl_owner=${ownerMarker()}`},body:JSON.stringify({as_user:true})}));assert.equal(response.status,400);}
 finally{for(const [key,value] of [['WEBAPP_SECRET',env.secret],['VIDEL_BACKEND_URL',env.backend]]){if(value===undefined)delete process.env[key!];else process.env[key!]=value;}}
});
test('group inbox validates destinations, Telegram links and UTF16 limits',()=>{
 assert.equal(groupId('-100123'),-100123);for(const value of ['123','@group','-1.5','-9007199254740993','--123'])assert.equal(groupId(value),null);
 assert.equal(telegramMessageLink(-100123456,42),'https://t.me/c/123456/42');
 assert.equal(telegramMessageLink(-123,42),null);assert.equal(telegramMessageLink(-100123,0),null);
 assert.equal(textUnits('😀'.repeat(2048)),4096);
});
