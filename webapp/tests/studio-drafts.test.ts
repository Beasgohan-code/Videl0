import test from "node:test";
import assert from "node:assert/strict";
import {parseBrandKits,postChecks} from "../src/lib/studio-drafts";
test("brand kits allow only safe colors and supported fonts",()=>{
 const kit={id:"one",name:"Editorial",background:"#eeeeee",accent:"#123456",color:"#000000",font:"Georgia"};
 assert.deepEqual(parseBrandKits([kit]),[kit]);
 assert.deepEqual(parseBrandKits([{...kit,accent:"url(javascript:bad)"},{...kit,font:"custom"},null]),[]);
 assert.equal(parseBrandKits(Array(25).fill(kit)).length,20);
});
test("publishing checklist catches length and sample content without fetching links",()=>{
 assert.equal(postChecks("a".repeat(1025),true,[])[0].state,"error");
 assert.equal(postChecks("",false,[])[0].state,"error");
 assert.ok(postChecks("Your event starts soon",false,[]).some(c=>c.label==="Template placeholders"&&c.state==="warning"));
 assert.ok(postChecks('<a href="http://example.com">Visit</a>',false,[]).some(c=>c.label==="Link structure"&&c.state==="warning"));
 assert.ok(postChecks("",true,[]).some(c=>c.label==="Image context"&&c.state==="warning"));
});
