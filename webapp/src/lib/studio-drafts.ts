import { visibleLength, plainPostText } from "./telegram-format";
import type {ImageDesign} from "./image-design";
import type {ButtonRow} from "./post-buttons";
export type BrandLayout={ratio:ImageDesign["ratio"];geometry:boolean;pattern:ImageDesign["pattern"];align:ImageDesign["align"]};
export type BrandKit={id:string;name:string;background:string;accent:string;color:string;font:ImageDesign["font"];layout?:BrandLayout};
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
export const BRAND_KEY="videl_brand_kits_v1";
export const VERSION_KEY="videl_post_versions_v1";
export function parseBrandKits(value:unknown):BrandKit[]{
 if(!Array.isArray(value))return [];
 return value.slice(0,20).flatMap(item=>{
  if(!item||typeof item!=="object")return [];
  const {id,name,background,accent,color,font}=item;
  if(typeof id!=="string"||typeof name!=="string"||!name.trim()||![background,accent,color].every(c=>typeof c==="string"&&/^#[0-9a-f]{6}$/i.test(c))||!["Georgia","Arial","monospace"].includes(font))return [];
  const layout=parseBrandLayout((item as {layout?:unknown}).layout);
  return [{id:id.slice(0,128),name:name.trim().slice(0,40),background,accent,color,font,...(layout?{layout}:{})}];
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
