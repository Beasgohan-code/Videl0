"use client";
import { createContext, useContext, useEffect, useState } from "react";
export const sections = ["home","chat","post","groups","automation","analytics","broadcast","settings","auth"] as const;
export type Section = typeof sections[number];
const legacy: Record<string,Section> = {"/":"home","/dashboard":"home","/dashboard/chat":"chat","/chat":"chat","/dashboard/channel":"post","/post":"post","/groups":"groups","/automation":"automation","/analytics":"analytics","/broadcast":"broadcast","/settings":"settings","/auth":"auth"};
const StudioContext = createContext<{tab:Section;open:(tab:Section)=>void}>({tab:"home",open:()=>{}});
export function StudioProvider({children}:{children:React.ReactNode}){
 const [tab,setTab]=useState<Section>("home");
 useEffect(()=>{
   const initial = new URLSearchParams(window.location.search).get("tab");
   if(sections.includes(initial as Section))setTab(initial as Section);
   // Deep links choose a panel, but the workspace itself always stays at the root URL.
   if(initial){const url=new URL(window.location.href);url.searchParams.delete("tab");window.history.replaceState(window.history.state,"",url.pathname+url.search+url.hash)}
 },[]);
 function capture(e:React.MouseEvent<HTMLDivElement>){
   if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
   const a=(e.target as Element).closest("a");if(!a||a.target==="_blank"||a.hasAttribute("download"))return;
   const url=new URL(a.href,window.location.href);if(url.origin!==window.location.origin)return;
   const target=url.searchParams.get("tab") as Section|null;
   const next=target&&sections.includes(target)?target:legacy[url.pathname];
   if(next){e.preventDefault();e.stopPropagation();setTab(next);window.scrollTo({top:0,behavior:"smooth"});}
 }
 return <StudioContext.Provider value={{tab,open:setTab}}><div onClickCapture={capture}>{children}</div></StudioContext.Provider>
}
export function useStudio(){return useContext(StudioContext)}
