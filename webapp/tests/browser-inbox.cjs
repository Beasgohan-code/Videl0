/* UI-only fixture checks. Never connects to Telegram or creates real messages. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/tmp/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));let textSends=0,uploads=0;
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url());let body={ok:true};
  if(url.pathname==='/api/auth')body={ok:true,owner:true};
  else if(url.pathname==='/api/conversations')body={ok:true,chats:[{id:123,title:'Test bot DM',type:'private'},{id:-100123456,title:'Test group',type:'supergroup'}]};
  else if(url.pathname==='/api/group-view'){
   if(req.method()==='POST'){const action=req.postDataJSON();assert.equal(action.chat_id,123);assert.equal(action.action,'send');assert.equal(action.text,'Hello from the bot');assert.equal(action.as_user,undefined);textSends++;body={ok:true,status:'confirmed'};}
   else{const id=Number(url.searchParams.get('chat_id'));body={ok:true,chat_id:id,is_private:id>0,items:[{chat_id:id,message_id:7,text:'Fixture message, not a live Telegram conversation',sender_id:123,sender_is_user:true,sender_name:'Test contact',sender_username:'test',is_bot:false,date:new Date().toISOString(),edited:false,deleted:false,reply_to_id:null,thread_id:null,media:null}],recording:true,retention_days:7,settings:{},has_more:false,capture_dropped:0,visibility_note:'Browser-test fixture only'};}
  }else if(url.pathname==='/api/inbox-media'&&req.method()==='POST'){assert.ok(req.headers()['content-type'].includes('multipart/form-data'));uploads++;body={ok:true,status:'confirmed'};}
  await route.fulfill({json:body});
 });
 await page.goto((process.env.INBOX_URL||'http://127.0.0.1:3004')+'/?tab=chat');
 await page.getByRole('heading',{name:'Bot inbox',exact:true}).waitFor();
 await page.getByRole('button',{name:/Test bot DM/}).click();
 await page.getByText('Fixture message, not a live Telegram conversation',{exact:true}).waitFor();
 await page.getByRole('textbox',{name:'Message as bot'}).fill('Hello from the bot');
 await page.getByRole('button',{name:'Send as bot',exact:true}).click();
 await page.getByRole('textbox',{name:'Message as bot'}).filter({hasText:''}).waitFor();
 await page.waitForFunction(()=>document.querySelector('textarea[aria-label="Message as bot"]')?.value==='');
 assert.equal(textSends,1);
 await page.locator('input[type=file]').setInputFiles({name:'test.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j42kAAAAASUVORK5CYII=','base64')});
 await page.getByAltText('Attachment preview').waitFor();
 await page.getByRole('button',{name:'Send as bot',exact:true}).click();
 await page.waitForFunction(()=>!document.querySelector('img[alt="Attachment preview"]'));assert.equal(uploads,1);
 await page.getByRole('button',{name:'Message 7 actions'}).click();
 await page.getByRole('heading',{name:'Message details'}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Mute 10 min',exact:true}).count(),0);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),true);
 assert.deepEqual(errors,[]);
 console.log('Bot inbox desktop/mobile, DM text, multipart attachment, and private-chat control checks PASS (mocked APIs).');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
