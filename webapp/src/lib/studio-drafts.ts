import { visibleLength, plainPostText } from "./telegram-format";
import type {ImageDesign} from "./image-design";
import type {ButtonRow} from "./post-buttons";
export type BrandLayout={ratio:ImageDesign["ratio"];geometry:boolean;pattern:ImageDesign["pattern"];align:ImageDesign["align"]};
export type BrandKit={id:string;name:string;background:string;accent:string;color:string;font:ImageDesign["font"];layout?:BrandLayout;logoData?:string;logoCorner?:ImageDesign["logoCorner"];footer?:string};
const RATIOS=["landscape","square","portrait"] as const;
const PATTERNS=["rings","grid","dots"] as const;
/** A layout is optional: older kits still load and simply keep the current arrangement. */
export function parseBrandLayout(value:unknown):BrandLayout|undefined{
 if(!value||typeof value!=="object")return undefined;
 const {ratio,geometry,pattern,align}=value as Record<string,unknown>;
 if(!RATIOS.includes(ratio as (typeof RATIOS)[number]))return undefined;
 if(typeof geometry!=="boolean")return undefined;
 if(!PATTERNS.includes(pattern as (typeof PATTERNS)[number]))return undefined;
 if(align!=="left"&&align!=="center")return undefined;
 return {ratio:ratio as BrandLayout["ratio"],geometry,pattern:pattern as BrandLayout["pattern"],align};
}
/** A logo is only accepted as a bounded image data URL, never a remote URL. */
export function parseBrandLogo(value:unknown):string|undefined{
 if(typeof value!=="string")return undefined;
 return /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value)&&value.length<=300000?value:undefined;
}
export function parseBrandCorner(value:unknown):ImageDesign["logoCorner"]|undefined{
 return ["tl","tr","bl","br"].includes(String(value))?(value as ImageDesign["logoCorner"]):undefined;
}
export function parseBrandFooter(value:unknown):string|undefined{
 if(typeof value!=="string")return undefined;
 const clean=value.replace(/[\u0000-\u001f\u007f]/g," ").trim().slice(0,160);
 return clean||undefined;
}
/** Downscale a picked logo so a kit stays small enough for localStorage. */
export async function readLogoFile(file:File):Promise<string>{
 if(!["image/png","image/jpeg","image/webp"].includes(file.type))throw new Error("Choose a PNG, JPEG or WebP logo.");
 if(file.size>8*1024*1024)throw new Error("Choose a logo smaller than 8 MB.");
 const url=URL.createObjectURL(file);
 try{
  const image=await new Promise<HTMLImageElement>((resolve,reject)=>{const item=new Image();item.onload=()=>resolve(item);item.onerror=()=>reject(new Error("That logo could not be opened."));item.src=url});
  const scale=Math.min(1,256/Math.max(image.naturalWidth,image.naturalHeight));
  const canvas=document.createElement("canvas");
  canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));
  canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
  const ctx=canvas.getContext("2d");
  if(!ctx)throw new Error("Logo rendering is unavailable in this browser.");
  ctx.drawImage(image,0,0,canvas.width,canvas.height);
  const data=canvas.toDataURL("image/png");
  if(!parseBrandLogo(data))throw new Error("That logo is too large to store. Try a simpler image.");
  return data;
 }finally{URL.revokeObjectURL(url)}
}
export const BRAND_KEY="videl_brand_kits_v1";
export const VERSION_KEY="videl_post_versions_v1";
export function parseBrandKits(value:unknown):BrandKit[]{
 if(!Array.isArray(value))return [];
 return value.slice(0,20).flatMap(item=>{
  if(!item||typeof item!=="object")return [];
  const {id,name,background,accent,color,font}=item;
  if(typeof id!=="string"||typeof name!=="string"||!name.trim()||![background,accent,color].every(c=>typeof c==="string"&&/^#[0-9a-f]{6}$/i.test(c))||!["Georgia","Arial","monospace"].includes(font))return [];
  const layout=parseBrandLayout((item as {layout?:unknown}).layout);
  const logoData=parseBrandLogo((item as {logoData?:unknown}).logoData);
  const logoCorner=parseBrandCorner((item as {logoCorner?:unknown}).logoCorner);
  const footer=parseBrandFooter((item as {footer?:unknown}).footer);
  return [{id:id.slice(0,128),name:name.trim().slice(0,40),background,accent,color,font,
    ...(layout?{layout}:{}),...(logoData?{logoData}:{}),...(logoCorner?{logoCorner}:{}),...(footer?{footer}:{})}];
 });
}
export type PostCheck={label:string;state:"pass"|"warning"|"error";detail:string};
/** Structural checks only; no link requests or claims about remote availability. */
export function postChecks(text:string,media:boolean,buttons:ButtonRow[]):PostCheck[]{
 const length=visibleLength(text),limit=media?1024:4096;
 const checks:PostCheck[]=[{label:"Message length",state:length>limit?"error":!length&&!media?"error":"pass",detail:`${length} / ${limit} characters`}];
 checks.push({label:"Template placeholders",state:/\b(?:your (?:event|date|time|first|second)|add (?:date|your|meeting)|insert here)\b/i.test(plainPostText(text))?"warning":"pass",detail:"Check sample names, dates and instructions before publishing."});
 checks.push({label:"Link structure",state: /href=["'](?:http:\/\/)/i.test(text)?"warning":"pass",detail:"Prefer HTTPS links. Destination availability is not checked."});
 if(media)checks.push({label:"Image context",state:length?"pass":"warning",detail:"A descriptive caption helps readers understand the image."});
 checks.push({label:"Native buttons",state:buttons.some(row=>row.some(b=>!!b.iconId))?"warning":"pass",detail:"Colors depend on the Telegram client; custom emoji icons require eligibility."});
 return checks;
}
