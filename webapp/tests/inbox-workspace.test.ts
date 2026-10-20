import test from 'node:test';
import assert from 'node:assert/strict';
import {GET,POST} from '../src/app/api/inbox-workspace/route';
import {ownerMarker} from '../src/lib/auth';
import {tagsFromInput,orderConversations,loadedNewMessages} from '../src/lib/inbox-workspace';
import type {GroupMessage} from '../src/lib/group-view';

test('workspace endpoints never contact a backend for guests',async()=>{
 for(const [method,handler] of [['GET',GET],['POST',POST]] as const)assert.equal((await handler(new Request('https://studio.test/api/inbox-workspace',{method}))).status,401);
});
test('workspace updates reject cross-site owner requests',async()=>{
 const previous=process.env.WEBAPP_SECRET;process.env.WEBAPP_SECRET='offline-workspace';
 try{const result=await POST(new Request('https://studio.test/api/inbox-workspace',{method:'POST',headers:{cookie:`videl_owner=${ownerMarker()}`,origin:'https://untrusted.test'}}));assert.equal(result.status,403);}
 finally{if(previous===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=previous;}
});
test('conversation pin ordering is stable and does not mutate source data',()=>{
 const items=[{id:1,title:'Zulu'},{id:2,title:'Alpha'},{id:3,title:'Beta'}];
 const result=orderConversations(items,[{chat_id:1,pinned:true,tags:[],last_reviewed_message_id:0}]);
 assert.deepEqual(result.map(item=>item.id),[1,2,3]);assert.deepEqual(items.map(item=>item.id),[1,2,3]);
});
test('comma separated tags normalize blanks and duplicates',()=>{
 assert.deepEqual(tagsFromInput('support, urgent, support, ,'),['support','urgent']);
});
test('workspace new-count uses loaded incoming messages, not fake Telegram read receipts',()=>{
 const items=[{message_id:1,is_bot:false,deleted:false},{message_id:2,is_bot:false,deleted:false},{message_id:3,is_bot:true,deleted:false},{message_id:4,is_bot:false,deleted:true}] as GroupMessage[];
 assert.equal(loadedNewMessages(items,1),1);assert.equal(loadedNewMessages(items,4),0);
});
