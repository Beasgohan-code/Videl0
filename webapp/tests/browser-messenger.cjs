/* Offline Telegram-like navigation/scroll test; fixtures are not real Telegram history. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/tmp/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));let last=90,sends=0;
 function messages(first,end){return Array.from({length:end-first+1},(_,i)=>({chat_id:123,message_id:first+i,text:`Captured fixture ${first+i}: ${'Conversation text. '.repeat(5)}`,sender_id:123,sender_is_user:true,sender_name:'Contact',sender_username:'',is_bot:false,date:new Date(Date.UTC(2026,9,20,9,first+i)).toISOString(),edited:false,deleted:false,reply_to_id:null,thread_id:null,media:null}));}
 await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url());let body={ok:true};
  if(url.pathname==='/api/auth')body={ok:true,owner:true};
  else if(url.pathname==='/api/conversations')body={ok:true,chats:[{id:123,title:'Messenger fixture',type:'private'},{id:-100123,title:'Group fixture',type:'supergroup'}]};
  else if(url.pathname==='/api/inbox-workspace')body={ok:true,conversations:[],quick_replies:[]};
  else if(url.pathname==='/api/group-view'){
   if(request.method()==='POST'){const action=request.postDataJSON();assert.equal(action.chat_id,123);assert.equal(action.action,'send');assert.equal(action.as_user,undefined);sends++;body={ok:true,message_id:100,status:'confirmed'};}
   else body={ok:true,chat_id:Number(url.searchParams.get('chat_id')),is_private:true,items:url.searchParams.has('before')?messages(1,50):messages(51,last),has_more:!url.searchParams.has('before'),next_before:51,recording:true,retention_days:7,settings:{},capture_dropped:0};
  }
  await route.fulfill({json:body});
 });
 await page.goto((process.env.INBOX_URL||'http://127.0.0.1:3004')+'/?tab=chat');
 await page.getByRole('button',{name:/Messenger fixture/}).click();
 const log=page.getByRole('log');await log.getByText(/Captured fixture 90:/).waitFor();
 assert.equal(await page.getByRole('complementary',{name:'Chat info',exact:true}).isVisible(),false);
 const gap=()=>log.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight);
 assert.ok(await gap()<5,'initial message load lands at the latest message');
 await log.evaluate(node=>node.scrollTop=0);
 await page.getByRole('button',{name:'Jump to latest messages'}).waitFor();
 const topBefore=await log.evaluate(node=>node.scrollTop);
 last=91;await page.getByRole('button',{name:'Refresh messages',exact:true}).click();
 await log.getByText(/Captured fixture 91:/).waitFor({state:'attached'});
 assert.ok(Math.abs(await log.evaluate(node=>node.scrollTop)-topBefore)<5,'refresh must not pull reader away from older messages');
 const before=await log.evaluate(node=>({height:node.scrollHeight,top:node.scrollTop}));
 await page.getByRole('button',{name:'Load older messages',exact:true}).click();
 await log.getByText(/Captured fixture 1:/).waitFor({state:'attached'});
 const after=await log.evaluate(node=>({height:node.scrollHeight,top:node.scrollTop}));
 assert.ok(Math.abs(after.top-(before.top+after.height-before.height))<8,'prepending older history preserves the viewport');
 await page.getByRole('button',{name:'Jump to latest messages'}).click();assert.ok(await gap()<5);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.getByRole('complementary',{name:'Chats',exact:true}).isVisible(),false);
 assert.equal(await page.getByRole('textbox',{name:'Message as bot'}).isVisible(),true);
 await page.getByRole('button',{name:'Back to chats'}).click();
 assert.equal(await page.getByRole('textbox',{name:'Message as bot'}).isVisible(),false);
 assert.equal(await page.getByRole('complementary',{name:'Chats',exact:true}).isVisible(),true);
 await page.getByRole('button',{name:/Messenger fixture/}).click();
 await page.getByRole('textbox',{name:'Message as bot'}).fill('Mobile bot reply');
 await page.getByRole('button',{name:'Send as bot',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('textarea[aria-label="Message as bot"]').value==='');
 assert.equal(sends,1);
 await page.getByRole('button',{name:'Chat info and settings'}).click();
 await page.getByRole('heading',{name:'Chat info',exact:true}).waitFor();
 await page.getByRole('button',{name:'Close chat info',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
 const composerBox=await page.locator('.tg-composer').boundingBox();assert.ok(composerBox.y+composerBox.height<=844-60,'composer stays above app navigation');
 await page.screenshot({path:'/tmp/videl-messenger-mobile.png'});
 assert.deepEqual(errors,[]);console.log('Messenger desktop/mobile navigation, latest-first viewport, no scroll hijack, prepend anchoring, bot sending and hidden settings PASS (mocked APIs).');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
