"use client";
import { useEffect, useRef } from "react";
import { useTelegram } from "@/components/TelegramProvider";
import Link from "next/link";
import { useStudio } from "@/components/studio/StudioProvider";
import { BarChart3, Home, MessageCircle, Radio, Send, Settings2, Shield, Zap, Crown, MoreHorizontal, X, ChevronRight } from "lucide-react";
const tabs = [
  {href:"/",label:"Home",icon:Home},
  {href:"/chat",label:"Smart Chat",icon:MessageCircle},
  {href:"/post",label:"Post Studio",icon:Radio},
  {href:"/groups",label:"Group Manager",icon:Shield},
  {href:"/automation",label:"Automation",icon:Zap},
  {href:"/analytics",label:"Analytics",icon:BarChart3},
  {href:"/broadcast",label:"Broadcast",icon:Send},
  {href:"/settings",label:"Bot Settings",icon:Settings2},
];
function selected(path:string, href:string) {
  if(href==="/") return path==="/" || path==="/dashboard";
  if(href==="/post") return path==="/post" || path==="/dashboard/channel";
  if(href==="/chat") return path==="/chat" || path==="/dashboard/chat";
  return path===href;
}
export function IOSNav(){
 const {tab}=useStudio(); const telegram=useTelegram(); const path=tab==="home"?"/":`/${tab}`;
 return <><aside className="fixed inset-y-0 left-0 z-50 hidden w-60 flex-col border-r border-indigo-300/10 bg-[#080b1a]/95 px-4 py-7 lg:flex">
  <Link href="/" className="flex items-center gap-3 px-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg shadow-indigo-600/25"><Crown size={23}/></span><span className="text-xl font-bold">Videl<span className="mt-1 block text-[10px] font-medium uppercase tracking-[.25em] text-indigo-200/45">Telegram Studio</span></span></Link>
  <p className="mb-3 mt-10 px-3 text-[10px] font-semibold uppercase tracking-[.2em] text-white/30">Workspace</p>
  <nav aria-label="Main navigation" className="space-y-2">{tabs.map(t=><Link key={t.href} href={t.href==="/"?"/":`/?tab=${t.href.slice(1)}`} aria-current={selected(path,t.href)?"page":undefined} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${selected(path,t.href)?"border-indigo-400/30 bg-gradient-to-r from-blue-500/25 to-violet-500/15 text-white shadow-lg shadow-indigo-950/30":"border-transparent text-indigo-100/50 hover:bg-white/5 hover:text-white"}`}><t.icon size={18}/>{t.label}</Link>)}</nav>
  <div className="mt-auto rounded-2xl border border-indigo-300/10 bg-indigo-400/5 p-4"><p className="text-sm font-semibold">Your community. Connected.</p><p className="mt-2 text-xs leading-5 text-white/40">One studio for your Telegram operations.</p><Link href="/?tab=auth" className="mt-3 block text-xs text-indigo-300">Owner sign in →</Link></div>
 </aside><header className="flex h-16 items-center justify-between border-b border-indigo-200/10"><div className="flex items-center gap-2 text-xs"><Link href="/" className="font-semibold tracking-wide">Videl Studio</Link><ChevronRight size={12} className="text-white/25"/><span className="text-indigo-100/45">{tabs.find(t=>selected(path,t.href))?.label||"Owner access"}</span></div><Link href="/?tab=auth" className="ios-btn ios-btn-glass text-xs"><Shield size={14}/> {telegram.authenticated?telegram.user?.first_name||"Owner":"Sign in"}</Link></header></>;
}
export function IOSTabBar(){
 const {tab,open}=useStudio();const dialog=useRef<HTMLDialogElement>(null);const path=tab==="home"?"/":`/${tab}`;
 useEffect(()=>{dialog.current?.close()},[tab]);
 function go(href:string){open((href==="/"?"home":href.slice(1)) as Parameters<typeof open>[0]);dialog.current?.close();window.scrollTo({top:0,behavior:"smooth"})}
 return <><nav aria-label="Mobile navigation" className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-[#0c1222]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"><div className="mx-auto flex max-w-xl px-2 py-2">{tabs.slice(0,4).map(t=><button key={t.href} onClick={()=>go(t.href)} aria-current={selected(path,t.href)?"page":undefined} className={`flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl px-1 py-2 ${selected(path,t.href)?"bg-white/[0.07] text-indigo-100":"text-white/40"}`}><t.icon size={19}/><span className="whitespace-nowrap text-[9px]">{t.label}</span></button>)}<button onClick={()=>dialog.current?.showModal()} aria-label="More Studio tools" aria-haspopup="dialog" className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-1 py-2 ${tabs.slice(4).some(t=>selected(path,t.href))?"bg-white/[0.07] text-indigo-100":"text-white/40"}`}><MoreHorizontal size={19}/><span className="text-[9px]">More</span></button></div></nav>
 <dialog ref={dialog} aria-labelledby="studio-more-title" className="studio-more-dialog" onClick={e=>{if(e.target===e.currentTarget)dialog.current?.close()}}><section className="rounded-t-3xl border border-white/10 bg-[#101829] p-5 pb-[calc(1.5rem+env(safe-area-inset-bottom))]"><div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-[.2em] text-indigo-200/40">Your workspace</p><h2 id="studio-more-title" className="mt-2 text-lg font-semibold">More from Videl</h2></div><button onClick={()=>dialog.current?.close()} aria-label="Close tools menu" className="rounded-full bg-white/5 p-2 text-white/60"><X size={18}/></button></div><div className="grid grid-cols-2 gap-3">{tabs.slice(4).map(t=><button key={t.href} onClick={()=>go(t.href)} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-left text-xs text-indigo-100/75"><t.icon size={19} className="text-indigo-300"/>{t.label}</button>)}</div><button onClick={()=>go("/auth")} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-white/5 p-3 text-xs text-indigo-200/70"><Shield size={15}/> Owner access</button></section></dialog></>;
}
