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
