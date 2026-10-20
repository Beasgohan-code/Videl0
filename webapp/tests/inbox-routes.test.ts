import test from 'node:test';
import assert from 'node:assert/strict';
import {GET as contacts} from '../src/app/api/conversations/route';
import {GET as media,POST as upload} from '../src/app/api/inbox-media/route';
import {ownerMarker} from '../src/lib/auth';
import {conversationId} from '../src/lib/group-view';
test('bot contacts and binary media endpoints deny unauthenticated requests',async()=>{
 for(const [method,handler] of [['GET',contacts],['GET',media],['POST',upload]] as const){
  assert.equal((await handler(new Request('https://studio.test/api/inbox-media',{method}))).status,401);
 }
});
test('voice/photo/video uploads reject cross-site owner requests',async()=>{
 const secret=process.env.WEBAPP_SECRET;process.env.WEBAPP_SECRET='offline-inbox';
 try{assert.equal((await upload(new Request('https://studio.test/api/inbox-media',{method:'POST',headers:{cookie:`videl_owner=${ownerMarker()}`,origin:'https://attacker.test'}}))).status,403);}
 finally{if(secret===undefined)delete process.env.WEBAPP_SECRET;else process.env.WEBAPP_SECRET=secret;}
});
test('multipart proxy preserves reply and attachment data but not arbitrary fields',async()=>{
 const env={secret:process.env.WEBAPP_SECRET,backend:process.env.VIDEL_BACKEND_URL},old=globalThis.fetch;
 process.env.WEBAPP_SECRET='offline-inbox';process.env.VIDEL_BACKEND_URL='https://backend.test';
 let forwarded:FormData|undefined;
 globalThis.fetch=async(_url,options)=>{forwarded=options?.body as FormData;return Response.json({ok:true,status:'confirmed'});};
 try{
  const form=new FormData();form.set('file',new Blob(['OggS-test'],{type:'audio/ogg'}),'voice.ogg');form.set('kind','voice');form.set('chat_id','123');form.set('message_id','4');form.set('request_id','test-id');form.set('secret_url','https://bad.test');
  const response=await upload(new Request('https://studio.test/api/inbox-media',{method:'POST',headers:{cookie:`videl_owner=${ownerMarker()}`},body:form}));
  assert.equal(response.status,200);assert.equal(forwarded?.get('kind'),'voice');assert.equal(forwarded?.get('message_id'),'4');assert.ok(forwarded?.get('file') instanceof Blob);assert.equal(forwarded?.get('secret_url'),null);
 }finally{globalThis.fetch=old;for(const [key,value] of [['WEBAPP_SECRET',env.secret],['VIDEL_BACKEND_URL',env.backend]]){if(value===undefined)delete process.env[key!];else process.env[key!]=value;}}
});
test('conversation IDs accept bot DMs and groups, never account usernames or URLs',()=>{
 assert.equal(conversationId('123'),123);assert.equal(conversationId('-100123'),-100123);
 for(const value of ['0','https://x.test','@account','1.2','9007199254740993'])assert.equal(conversationId(value),null);
});
