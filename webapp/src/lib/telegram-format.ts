import { decodeHTML } from "entities";
import sanitizeHtml from "sanitize-html";
export type RichNode = {type?:string;text?:string;attrs?:Record<string,unknown>;marks?:{type:string;attrs?:Record<string,unknown>}[];content?:RichNode[]};
export function escapeText(text:string){return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
export function safeLink(value:string){try{const url=new URL(value);return ["https:","http:","tg:"].includes(url.protocol)?url.href:null}catch{return null}}
/** Serialize structured editor content into Telegram-supported HTML only. */
export function telegramHtml(node:RichNode):string{
 if(node.type==="text"){
  let text=escapeText(node.text||"");
  for(const mark of node.marks||[]){
   const tags:Record<string,string>={bold:"b",italic:"i",underline:"u",strike:"s",code:"code",spoiler:"tg-spoiler"};
   if(tags[mark.type])text=`<${tags[mark.type]}>${text}</${tags[mark.type]}>`;
   if(mark.type==="link"){const href=safeLink(String(mark.attrs?.href||""));if(href)text=`<a href="${escapeText(href)}">${text}</a>`}
  }
  return text;
 }
 if(node.type==="hardBreak")return "\n";
 const children=node.content||[];
 if(node.type==="doc"||node.type==="blockquote"||node.type==="listItem"){
  const text=children.map(telegramHtml).join("\n");
  return node.type==="blockquote"?`<blockquote>${text}</blockquote>`:text;
 }
 if(node.type==="bulletList"||node.type==="orderedList")return children.map((child,i)=>`${node.type==="orderedList"?`${i+1}.`:"•"} ${telegramHtml(child)}`).join("\n");
 const text=children.map(telegramHtml).join("");
 if(node.type==="heading")return `<b>${text}</b>`;
 if(node.type==="codeBlock")return `<pre>${escapeText(children.map(c=>c.text||"").join(""))}</pre>`;
 return text;
}
const allowedTags=["b","strong","i","em","u","s","del","code","pre","blockquote","tg-spoiler","a"];
export function cleanTelegramHtml(value:string){return sanitizeHtml(value,{allowedTags,allowedAttributes:{a:["href"]},allowedSchemes:["https","http","tg"],allowProtocolRelative:false})}
export function editorHtml(value:string){return cleanTelegramHtml(value).replace(/\n/g,"<br>").replace(/<tg-spoiler>/g,'<span data-spoiler="true">').replace(/<\/tg-spoiler>/g,"</span>")}
export function previewHtml(value:string){return cleanTelegramHtml(value).replace(/\n/g,"<br>").replace(/<tg-spoiler>/g,'<span class="post-spoiler">').replace(/<\/tg-spoiler>/g,"</span>")}
export function plainPostText(value:string){return decodeHTML(sanitizeHtml(value,{allowedTags:[],allowedAttributes:{}}))}
export function visibleLength(value:string){return plainPostText(value).length}
