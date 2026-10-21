import test from "node:test";
import assert from "node:assert/strict";
import {GET,POST,DELETE} from "../src/app/api/schedules/route";
import {ownerMarker} from "../src/lib/auth";
test("scheduled publishing routes reject unauthenticated requests before backend access",async()=>{
 for(const [method,handler] of [["GET",GET],["POST",POST],["DELETE",DELETE]] as const){
  const response=await handler(new Request("https://studio.example/api/schedules",{method}));
  assert.equal(response.status,401);
 }
});
test("schedule writes reject cross-site authenticated requests",async()=>{
 const old=process.env.WEBAPP_SECRET;process.env.WEBAPP_SECRET="offline-test";
 try{const response=await POST(new Request("https://studio.example/api/schedules",{method:"POST",headers:{cookie:`videl_owner=${ownerMarker()}`,origin:"https://attacker.example"}}));assert.equal(response.status,403)}finally{if(old===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=old}
});

test("a malformed repeat or timezone is refused before the queue is called",async()=>{
 const old=process.env.WEBAPP_SECRET,oldBackend=process.env.BACKEND_URL,oldSecret=process.env.INTERNAL_SECRET;
 process.env.WEBAPP_SECRET="offline-test";process.env.BACKEND_URL="https://backend.example";process.env.INTERNAL_SECRET="internal";
 let calls=0;const original=globalThis.fetch;
 globalThis.fetch=(async()=>{calls+=1;return Response.json({ok:true})}) as typeof fetch;
 try{
  for(const body of [
   {schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",repeat:["daily"]},
   {schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",repeat:"hourly"},
   {schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",repeat:"daily",timezone:{}},
   {schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",repeat:"daily",timezone:"Asia/Kolkata",wall_time:"9am"},
   {schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",wall_time:"09:00"},
  ]){
   const response=await POST(new Request("https://studio.example/api/schedules",{method:"POST",headers:{cookie:`videl_owner=${ownerMarker()}`,"content-type":"application/json"},body:JSON.stringify(body)}));
   assert.equal(response.status,400,JSON.stringify(body));
   assert.equal((await response.json()).ok,false);
  }
  assert.equal(calls,0,"a refused body must never reach the queue");
 }finally{
  globalThis.fetch=original;
  if(old===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=old;
  if(oldBackend===undefined)delete process.env.BACKEND_URL;else process.env.BACKEND_URL=oldBackend;
  if(oldSecret===undefined)delete process.env.INTERNAL_SECRET;else process.env.INTERNAL_SECRET=oldSecret;
 }
});

test("a valid zoned series is forwarded unchanged",async()=>{
 const old=process.env.WEBAPP_SECRET,oldBackend=process.env.BACKEND_URL,oldSecret=process.env.INTERNAL_SECRET;
 process.env.WEBAPP_SECRET="offline-test";process.env.BACKEND_URL="https://backend.example";process.env.INTERNAL_SECRET="internal";
 let sent:Record<string,unknown>|undefined;const original=globalThis.fetch;
 globalThis.fetch=(async(_url:string,init?:RequestInit)=>{sent=JSON.parse(String(init?.body||"{}"));return Response.json({ok:true,job_id:"x"})}) as typeof fetch;
 try{
  const body={schedule_at:"2026-10-21T03:30:00Z",request_id:"00000000-0000-4000-8000-000000000000",text:"hi",repeat:"daily",timezone:"Asia/Kolkata",wall_time:"09:00"};
  const response=await POST(new Request("https://studio.example/api/schedules",{method:"POST",headers:{cookie:`videl_owner=${ownerMarker()}`,"content-type":"application/json"},body:JSON.stringify(body)}));
  assert.equal(response.status,200);
  assert.equal(sent?.timezone,"Asia/Kolkata");
  assert.equal(sent?.wall_time,"09:00");
  assert.equal(sent?.repeat,"daily");
 }finally{
  globalThis.fetch=original;
  if(old===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=old;
  if(oldBackend===undefined)delete process.env.BACKEND_URL;else process.env.BACKEND_URL=oldBackend;
  if(oldSecret===undefined)delete process.env.INTERNAL_SECRET;else process.env.INTERNAL_SECRET=oldSecret;
 }
});
