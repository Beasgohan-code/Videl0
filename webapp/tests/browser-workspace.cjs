/* Offline browser fixture: verifies workspace interactions, not live Mongo/Telegram. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/tmp/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));let sends=0;const chats=new Map(),replies=[];
 function chat(cid){if(!chats.has(cid))chats.set(cid,{chat_id:cid,draft:'',notes:'',pinned:false,tags:[],last_reviewed_message_id:0,revisions:{draft:0,notes:0,organize:0}});return chats.get(cid);}
 await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url());let response={ok:true};
  if(url.pathname==='/api/auth')response={ok:true,owner:true};
  else if(url.pathname==='/api/conversations')response={ok:true,chats:[{id:123,title:'Workspace DM',type:'private'},{id:-100123,title:'Workspace group',type:'supergroup'}]};
  else if(url.pathname==='/api/group-view'){
   if(request.method()==='POST'){sends++;response={ok:true,status:'confirmed',message_id:99};}
   else{const cid=Number(url.searchParams.get('chat_id'));response={ok:true,chat_id:cid,is_private:cid>0,items:[{chat_id:cid,message_id:7,text:'Incoming fixture message',sender_id:123,sender_is_user:true,sender_name:'Test contact',sender_username:'',is_bot:false,date:new Date().toISOString(),edited:false,deleted:false,reply_to_id:null,thread_id:null,media:null}],recording:true,retention_days:7,settings:{},has_more:false,capture_dropped:0,visibility_note:'Fixture only'};}
  }else if(url.pathname==='/api/inbox-workspace'){
   if(request.method()==='GET')response=url.searchParams.has('chat_id')?{ok:true,chat:chat(Number(url.searchParams.get('chat_id')))}:{ok:true,conversations:[...chats.values()],quick_replies:replies};
   else{
    const body=request.postDataJSON();
    if(body.action==='save_reply'){replies.push({...body,revision:1});response={ok:true};}
    else{const row=chat(body.chat_id);if(body.action==='review')row.last_reviewed_message_id=body.message_id;
     else{assert.equal(body.revision,row.revisions[body.action]);if(body.action==='organize'){row.pinned=body.pinned;row.tags=body.tags;}else row[body.action]=body.value;row.revisions[body.action]++;}
     response={ok:true,chat:row};}
   }
  }
  await route.fulfill({json:response});
 });
 await page.goto((process.env.INBOX_URL||'http://127.0.0.1:3004')+'/?tab=chat');
 await page.getByRole('button',{name:/Workspace DM/}).click();
 await page.getByRole('button',{name:'Save draft',exact:true}).waitFor();
 const composer=page.getByRole('textbox',{name:'Message as bot'});
 await composer.fill('Draft shared across devices');await page.getByRole('button',{name:'Save draft',exact:true}).click();
 await page.getByText('27 saved text units',{exact:false}).waitFor();
 assert.equal(chat(123).draft,'Draft shared across devices');assert.equal(sends,0);
 await composer.fill('');await page.getByRole('button',{name:'Restore draft',exact:true}).click();assert.equal(await composer.inputValue(),'Draft shared across devices');
 await page.getByRole('textbox',{name:'Private conversation notes'}).fill('Private owner context');await page.getByRole('button',{name:/Save notes/}).click();
 await page.waitForFunction(()=>document.querySelector('[role="status"]')?.textContent?.includes('Saved'));
 assert.equal(chat(123).notes,'Private owner context');assert.equal(sends,0);
 await page.getByRole('button',{name:'Pin conversation in workspace'}).click();
 await page.getByRole('button',{name:'Unpin conversation in workspace'}).waitFor();assert.equal(chat(123).pinned,true);
 await page.getByRole('button',{name:'Mark loaded messages reviewed'}).click();
 await page.getByText('0 new incoming in loaded messages',{exact:false}).waitFor();assert.equal(sends,0);
 await page.getByRole('textbox',{name:'Saved reply title'}).fill('Welcome');await page.getByRole('textbox',{name:'Saved reply text'}).fill('A human-written saved reply');
 await page.getByRole('button',{name:'Create saved reply',exact:true}).click();await page.getByRole('button',{name:'Use',exact:true}).waitFor();
 await composer.fill('');await page.getByRole('button',{name:'Use',exact:true}).click();assert.equal(await composer.inputValue(),'A human-written saved reply');assert.equal(sends,0);
 await page.getByRole('button',{name:/Workspace group/}).click();await page.getByRole('button',{name:'Save draft',exact:true}).waitFor();assert.equal(await composer.inputValue(),'');
 await page.getByRole('button',{name:/Workspace DM/}).click();await page.getByRole('button',{name:'Restore draft',exact:true}).waitFor();
 await page.getByRole('button',{name:'Restore draft',exact:true}).click();assert.equal(await composer.inputValue(),'Draft shared across devices');
 await composer.press('Control+Enter');await page.waitForFunction(()=>document.querySelector('textarea[aria-label="Message as bot"]')?.value==='');assert.equal(sends,1);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),true);
 assert.deepEqual(errors,[]);console.log('Drafts, notes, pins, saved replies, review markers, chat isolation, keyboard send and mobile layout PASS (mocked APIs).');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
