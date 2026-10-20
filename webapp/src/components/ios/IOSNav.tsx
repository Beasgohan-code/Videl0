"use client";
import Link from "next/link";
import { useStudio } from "@/components/studio/StudioProvider";
import { BarChart3, Home, MessageCircle, Radio, Send, Settings2, Shield, Zap, Crown } from "lucide-react";
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
 const {tab}=useStudio(); const path=tab==="home"?"/":`/${tab}`;
 return <><aside className="fixed inset-y-0 left-0 z-50 hidden w-60 flex-col border-r border-indigo-300/10 bg-[#080b1a]/95 px-4 py-7 lg:flex">
  <Link href="/" className="flex items-center gap-3 px-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg shadow-indigo-600/25"><Crown size={23}/></span><span className="text-xl font-bold">Videl <span className="text-amber-300">👑</span><span className="mt-1 block text-[10px] font-medium uppercase tracking-[.25em] text-indigo-200/45">Telegram Studio</span></span></Link>
  <p className="mb-3 mt-10 px-3 text-[10px] font-semibold uppercase tracking-[.2em] text-white/30">Workspace</p>
  <nav aria-label="Main navigation" className="space-y-2">{tabs.map(t=><Link key={t.href} href={t.href==="/"?"/":`/?tab=${t.href.slice(1)}`} aria-current={selected(path,t.href)?"page":undefined} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${selected(path,t.href)?"border-indigo-400/30 bg-gradient-to-r from-blue-500/25 to-violet-500/15 text-white shadow-lg shadow-indigo-950/30":"border-transparent text-indigo-100/50 hover:bg-white/5 hover:text-white"}`}><t.icon size={18}/>{t.label}</Link>)}</nav>
  <div className="mt-auto rounded-2xl border border-indigo-300/10 bg-indigo-400/5 p-4"><p className="text-sm font-semibold">Your community. Connected.</p><p className="mt-2 text-xs leading-5 text-white/40">One studio for your Telegram operations.</p><Link href="/?tab=auth" className="mt-3 block text-xs text-indigo-300">Owner sign in →</Link></div>
 </aside><header className="flex h-16 items-center justify-between border-b border-indigo-200/10"><Link href="/" className="text-sm font-semibold tracking-wide">Videl 👑 <span className="font-normal text-indigo-200/40">/ Studio</span></Link><Link href="/?tab=auth" className="ios-btn ios-btn-glass text-xs"><Shield size={14}/> Owner access</Link></header></>;
}
export function IOSTabBar(){const {tab}=useStudio(); const path=tab==="home"?"/":`/${tab}`;return <nav aria-label="Mobile navigation" className="fixed inset-x-0 bottom-0 z-40 border-t border-indigo-300/15 bg-[#080b1a]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"><div className="flex overflow-x-auto px-2 py-2">{tabs.map(t=><Link key={t.href} href={t.href==="/"?"/":`/?tab=${t.href.slice(1)}`} aria-current={selected(path,t.href)?"page":undefined} className={`flex min-w-[76px] flex-1 flex-col items-center gap-1 rounded-xl px-2 py-2 ${selected(path,t.href)?"bg-indigo-400/15 text-indigo-200":"text-white/45"}`}><t.icon size={18}/><span className="whitespace-nowrap text-[9px]">{t.label}</span></Link>)}</div></nav>}
