import test from "node:test";
import assert from "node:assert/strict";
import {GET} from "../src/app/api/summary/route";
test("public summary returns live aggregate counts, never private diagnostics",async()=>{
 const original=globalThis.fetch;const oldUrl=process.env.VIDEL_BACKEND_URL,oldSecret=process.env.WEBAPP_SECRET;
 process.env.VIDEL_BACKEND_URL="https://backend.example";process.env.WEBAPP_SECRET="test-only";
 globalThis.fetch=async()=>Response.json({ok:true,stats:{chats:14,users:15,plays:72,uptime:123,owner_username:"PRIVATE",services:{bot_token:true},secret:"DO_NOT_EXPOSE"}});
 try{const response=await GET();const body=await response.json();assert.equal(response.status,200);assert.deepEqual(body.stats,{chats:14,users:15,plays:72,uptime:123});assert.equal(body.source,"bot-mongodb");assert.ok(!JSON.stringify(body).includes("PRIVATE"));assert.ok(!JSON.stringify(body).includes("DO_NOT_EXPOSE"))}finally{globalThis.fetch=original;if(oldUrl===undefined)delete process.env.VIDEL_BACKEND_URL;else process.env.VIDEL_BACKEND_URL=oldUrl;if(oldSecret===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=oldSecret}
});
