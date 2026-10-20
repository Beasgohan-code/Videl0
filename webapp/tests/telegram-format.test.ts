import test from "node:test";
import assert from "node:assert/strict";
import { telegramHtml, cleanTelegramHtml, previewHtml, editorHtml, safeLink, visibleLength } from "../src/lib/telegram-format";
test("selected text marks become Telegram formatting without exposing tags",()=>{
 assert.equal(telegramHtml({type:"text",text:"Hello & <friends>",marks:[{type:"bold"},{type:"italic"}]}),"<i><b>Hello &amp; &lt;friends&gt;</b></i>");
});
test("paragraphs, line breaks and lists stay readable",()=>{
 const paragraph = {type:"paragraph",content:[{type:"text",text:"Hello"},{type:"hardBreak"},{type:"text",text:"world"}]};
 const list = {type:"bulletList",content:[{type:"listItem",content:[{type:"paragraph",content:[{type:"text",text:"News"}]}]}]};
 assert.equal(telegramHtml({type:"doc",content:[paragraph,list]}),"Hello\nworld\n• News");
});
test("unsafe links and pasted active content are rejected",()=>{
 assert.equal(safeLink("javascript:alert(1)"),null);
 const html=cleanTelegramHtml('<script>alert(1)</script><b onclick="alert(2)">safe</b><a href="javascript:alert(1)">link</a><img src=x onerror=alert(1)>');
 assert.equal(html,'<b>safe</b><a>link</a>');
 assert.equal(telegramHtml({type:"text",text:"link",marks:[{type:"link",attrs:{href:"javascript:alert(1)"}}]}),"link");
});
test("entities round-trip without double escaping",()=>{
 assert.equal(previewHtml('<b>A &amp; B &lt; C</b>'),'<b>A &amp; B &lt; C</b>');
 assert.equal(visibleLength('<b>A &amp; B</b>'),5);
 assert.equal(visibleLength('😀'),2);
});
test("spoilers are supported in Telegram, editor and preview",()=>{
 const html=telegramHtml({type:"text",text:"secret",marks:[{type:"spoiler"}]});
 assert.equal(html,'<tg-spoiler>secret</tg-spoiler>');
 assert.equal(editorHtml(html),'<span data-spoiler="true">secret</span>');
 assert.equal(previewHtml(html),'<span class="post-spoiler">secret</span>');
});
test("links keep readable text and escape attribute values",()=>{
 assert.equal(telegramHtml({type:"text",text:"Read more",marks:[{type:"link",attrs:{href:"https://example.com/?a=1&b=2"}}]}),'<a href="https://example.com/?a=1&amp;b=2">Read more</a>');
});

test("real editor selection formats words and undo restores them",async()=>{
 const {JSDOM}=await import("jsdom");
 const dom=new JSDOM("<!doctype html><body><div id='editor'></div></body>",{url:"https://studio.example"});
 Object.defineProperty(globalThis,"window",{value:dom.window,configurable:true});
 Object.defineProperty(globalThis,"document",{value:dom.window.document,configurable:true});
 Object.defineProperty(globalThis,"navigator",{value:dom.window.navigator,configurable:true});
 Object.defineProperty(globalThis,"getComputedStyle",{value:dom.window.getComputedStyle.bind(dom.window),configurable:true});
 const {Editor}=await import("@tiptap/core");
 const {default:StarterKit}=await import("@tiptap/starter-kit");
 const editor=new Editor({element:document.getElementById("editor")!,extensions:[StarterKit],content:editorHtml("Hello world")});
 editor.commands.setTextSelection({from:1,to:6});
 editor.commands.toggleBold();
 assert.equal(telegramHtml(editor.getJSON()),"<b>Hello</b> world");
 editor.commands.undo();
 assert.equal(telegramHtml(editor.getJSON()),"Hello world");
 editor.commands.setTextSelection({from:7,to:12});
 editor.commands.toggleUnderline();
 editor.commands.setLink({href:"https://example.com"});
 assert.equal(telegramHtml(editor.getJSON()),'Hello <u><a href="https://example.com/">world</a></u>');
 editor.destroy();dom.window.close();
});
