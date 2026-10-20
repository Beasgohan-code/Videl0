import test from "node:test";
import assert from "node:assert/strict";
import { initialDesign, designSize, wrapDesignText, paintDesign } from "../src/lib/image-design";
test("canvas sizes are valid Telegram photo dimensions",()=>{
 assert.deepEqual(designSize("landscape"),[1200,675]);assert.deepEqual(designSize("square"),[1080,1080]);assert.deepEqual(designSize("portrait"),[1080,1350]);
});
test("text wraps long words and respects explicit line breaks",()=>{
 const lines=wrapDesignText("Hello world\nABCDEFGHIJ",50,text=>text.length*10);
 assert.deepEqual(lines,["Hello","world","ABCDE","FGHIJ"]);
});
test("renderer uses customized words, typeface and colors rather than a fixed image",()=>{
 const printed:string[]=[];const ctx:any={clearRect(){},fillRect(){},save(){},restore(){},beginPath(){},arc(){},stroke(){},measureText:(s:string)=>({width:s.length*15}),fillText:(s:string)=>printed.push(s)};
 paintDesign(ctx,{...initialDesign,title:"My custom event",subtitle:"Friday at six",label:"YOUR INVITE",font:"Arial",background:"#123456",color:"#abcdef"},null);
 assert.ok(printed.includes("My custom event"));assert.ok(printed.includes("Friday at six"));assert.ok(printed.includes("YOUR INVITE"));assert.ok(!printed.includes(initialDesign.title));assert.equal(ctx.fillStyle,"#abcdef");
});
