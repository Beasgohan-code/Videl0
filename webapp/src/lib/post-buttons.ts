export const BUTTON_STYLES = ["default", "primary", "success", "danger"] as const;
export type ButtonStyle = (typeof BUTTON_STYLES)[number];
export type PostButton = { text: string; url: string; copyText?: string; style?: ButtonStyle; iconId?: string };
export type ButtonRow = PostButton[];
export const buttonClasses: Record<ButtonStyle,string> = {default:"bg-slate-600/70 text-white",primary:"bg-blue-600 text-white",success:"bg-emerald-600 text-white",danger:"bg-rose-600 text-white"};
export function parseButtons(value: unknown): ButtonRow[] {
 if (!Array.isArray(value)) return [];
 return value.slice(0,8).flatMap(row=>{
  if(!Array.isArray(row))return [];
  const buttons: PostButton[]=row.slice(0,8).flatMap((item:any)=>{
   if(!item||typeof item.text!=="string"||!item.text.trim()||item.text.length>64)return [];
   const copy=typeof item.copyText==="string"&&item.copyText.length>0&&item.copyText.length<=256?item.copyText:undefined;
   let url="";
   if(!copy){try{const parsed=new URL(item.url);if(parsed.protocol!=="https:"||parsed.username||parsed.password||String(item.url).length>2048)return [];url=String(item.url).trim()}catch{return []}}
   const button:PostButton={text:item.text.trim(),url};
   if(copy)button.copyText=copy;
   if(BUTTON_STYLES.includes(item.style)&&item.style!=="default")button.style=item.style;
   if(typeof item.iconId==="string"&&/^[1-9][0-9]{0,18}$/.test(item.iconId)&&BigInt(item.iconId)<=BigInt("9223372036854775807"))button.iconId=item.iconId;
   return [button];
  });
  return buttons.length?[buttons]:[];
 });
}
