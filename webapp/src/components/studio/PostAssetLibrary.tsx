"use client";
import { useState } from "react";
import { ArrowDownToLine, Check, ImagePlus, Search } from "lucide-react";
const assets = [
 {id:"community",title:"Community notes",category:"Community"},
 {id:"announcement",title:"Something new",category:"Announcements"},
 {id:"event",title:"Save the date",category:"Events"},
 {id:"welcome",title:"You belong here",category:"Community"},
 {id:"launch",title:"A new chapter",category:"Announcements"},
 {id:"weekly",title:"The weekly edit",category:"Editorial"},
 {id:"ocean",title:"Room to breathe",category:"Editorial"},
 {id:"milestone",title:"Look how far",category:"Announcements"},
 {id:"workshop",title:"Learn together",category:"Events"},
 {id:"spotlight",title:"In the spotlight",category:"Community"},
 {id:"minimal",title:"Less, but better",category:"Editorial"},
 {id:"thankyou",title:"Better, together",category:"Community"},
];
export function PostAssetLibrary({selected,onSelect,disabled=false}:{selected:string;onSelect:(path:string)=>void;disabled?:boolean}){
 const [category,setCategory]=useState("All");const [search,setSearch]=useState("");
 const filtered=assets.filter(a=>(category==="All"||a.category===category)&&`${a.title} ${a.category}`.toLowerCase().includes(search.toLowerCase()));
 return <section className="post-asset-library mt-5" aria-label="Post cover library">
  <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="post-eyebrow">THE COMMUNITY COLLECTION</p><h2 className="post-serif mt-2 text-2xl">A good story deserves a good cover.</h2><p className="mt-2 text-xs leading-5 text-stone-400">12 original PNG covers. Ready to attach, download or make part of your next post.</p></div><label className="relative"><Search size={14} className="absolute left-3 top-3.5 text-stone-400"/><input aria-label="Search cover library" className="ios-input !pl-9 text-xs" placeholder="Find a cover…" value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
  <div className="my-5 flex flex-wrap gap-2">{["All","Community","Announcements","Events","Editorial"].map(c=><button key={c} aria-pressed={category===c} onClick={()=>setCategory(c)} className={`rounded-full border px-3 py-1.5 text-[11px] transition ${c===category?"border-[#b5c4a5]/40 bg-[#b5c4a5]/15 text-[#d7e2ca]":"border-white/10 text-stone-400 hover:text-white"}`}>{c}</button>)}</div>
  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{filtered.map(a=>{const path=`/post-assets/${a.id}.png`;const active=selected.endsWith(path);return <article key={a.id} className={`overflow-hidden rounded-2xl border bg-[#1c201e] ${active?"border-[#b5c4a5]/60":"border-white/10"}`}><button disabled={disabled} onClick={()=>onSelect(path)} className="group block w-full overflow-hidden disabled:opacity-40" aria-label={`Use ${a.title} cover`}><img src={path} alt={`${a.title} editorial cover`} width={1200} height={675} loading="lazy" className="aspect-video w-full object-cover transition duration-300 group-hover:scale-[1.03]"/></button><div className="flex items-center justify-between gap-3 p-4"><div><p className="text-[9px] uppercase tracking-[.15em] text-stone-500">{a.category}</p><h3 className="mt-1 text-xs font-medium text-stone-200">{a.title}</h3></div><div className="flex gap-1"><a href={path} download={`${a.id}-cover.png`} aria-label={`Download ${a.title}`} className="rounded-lg p-2 text-stone-400 hover:bg-white/5 hover:text-white"><ArrowDownToLine size={15}/></a><button disabled={disabled} onClick={()=>onSelect(path)} aria-label={`Attach ${a.title}`} className="rounded-lg bg-[#b5c4a5]/10 p-2 text-[#c5d6b3] disabled:opacity-40">{active?<Check size={15}/>:<ImagePlus size={15}/>}</button></div></div></article>})}</div>
  {!filtered.length&&<p role="status" className="rounded-xl border border-white/10 p-6 text-sm text-stone-400">No covers match your search. Try another category.</p>}
  <p className="mt-4 text-[10px] leading-5 text-stone-500">1200 × 675 px · Original Videl artwork · Ready-to-use images, not an image generator. Text on each cover is fixed; your post caption is editable.</p>
 </section>
}
