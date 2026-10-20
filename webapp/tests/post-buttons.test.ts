import test from "node:test";
import assert from "node:assert/strict";
import {parseButtons} from "../src/lib/post-buttons";
import {draftDocument,importDraftDocument} from "../src/lib/post-drafts";
test("native button actions, styles and icons survive portable draft roundtrip",()=>{
 const buttons=parseButtons([[{text:"Join",url:"https://example.com",style:"success",iconId:"5368324170671202286"},{text:"Copy code",copyText:"JOIN2026",style:"primary"}]]);
 const draft={id:"portable",chatId:"",text:"<b>Welcome</b>",parseMode:"HTML" as const,mediaUrl:"",buttons,savedAt:new Date().toISOString()};
 assert.deepEqual(importDraftDocument(JSON.parse(draftDocument(draft))),draft);
 assert.equal(buttons[0][1].copyText,"JOIN2026");
 assert.equal(buttons[0][0].style,"success");
});
test("import rejects unknown versions and malformed content",()=>{
 assert.throws(()=>importDraftDocument({format:"videl-post",version:2,draft:{}}));
 assert.throws(()=>importDraftDocument({format:"videl-post",version:1,draft:{}}));
});
test("unsafe links and oversized copy actions never enter a keyboard",()=>{
 assert.deepEqual(parseButtons([[{text:"Bad",url:"javascript:alert(1)"},{text:"Auth",url:"https://user:pass@example.com"},{text:"Copy",copyText:"a".repeat(257)}]]),[]);
 const result=parseButtons([[{text:"Safe",url:"https://example.com",iconId:"9223372036854775808",style:"arbitrary"}]]);
 assert.equal(result[0][0].iconId,undefined);
 assert.equal(result[0][0].style,undefined);
 assert.deepEqual(parseButtons([[{text:"Emoji",copyText:"😀".repeat(129)}]]),[]);
});
