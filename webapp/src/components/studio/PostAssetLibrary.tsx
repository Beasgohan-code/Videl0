"use client";
import { useEffect, useState, useRef } from "react";
import { ArrowDownToLine, Check, ImagePlus, Search, Trash2, Upload, Sparkles, Heart } from "lucide-react";

const STORAGE_KEY="videl_custom_assets_v1";

type CustomAsset={id:string; title:string; category:string; dataUrl:string; createdAt:string};

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
 const [category,setCategory]=useState("All");
 const [search,setSearch]=useState("");
 const [custom,setCustom]=useState<CustomAsset[]>([]);
 const [notice,setNotice]=useState("");
 const fileRef=useRef<HTMLInputElement>(null);
 const [tab,setTab]=useState<"collection"|"yours">("collection");

 useEffect(()=>{
   try{
     const saved=localStorage.getItem(STORAGE_KEY);
     if(saved) setCustom(JSON.parse(saved));
   }catch{}
 },[]);
 useEffect(()=>{
   try{ localStorage.setItem(STORAGE_KEY, JSON.stringify(custom)); }catch{ setNotice("Storage full — delete some custom assets."); }
 },[custom]);

 function handleUpload(e:React.ChangeEvent<HTMLInputElement>){
   const file=e.target.files?.[0]; e.target.value="";
   if(!file) return;
   if(!["image/png","image/jpeg","image/webp"].includes(file.type)){ setNotice("Use PNG, JPEG or WebP."); return; }
   if(file.size>1.5*1024*1024){ setNotice("Max 1.5 MB per asset so it fits browser storage. Compress first."); return; }
   if(custom.length>=10){ setNotice("You have 10 custom assets — delete one to add more."); return; }
   const reader=new FileReader();
   reader.onload=()=>{
     const dataUrl=String(reader.result);
     const asset:CustomAsset={id:crypto.randomUUID(), title:file.name.replace(/\.[^.]+$/,'').slice(0,40)||"My cover", category:"Your assets", dataUrl, createdAt:new Date().toISOString()};
     setCustom(v=>[asset, ...v]); setTab("yours"); setNotice(`“${asset.title}” added to Your Assets ✨`);
   };
   reader.readAsDataURL(file);
 }
 function deleteCustom(id:string){
   if(!confirm("Delete this custom asset from this browser? This cannot be undone.")) return;
   setCustom(v=>v.filter(a=>a.id!==id));
 }

 const filtered=assets.filter(a=>(category==="All"||a.category===category)&&`${a.title} ${a.category}`.toLowerCase().includes(search.toLowerCase()));
 const filteredCustom=custom.filter(a=>`${a.title} ${a.category}`.toLowerCase().includes(search.toLowerCase()) && (category==="All"||category==="Your assets"||a.category===category));

 return <section className="post-asset-library mt-5" aria-label="Post cover library">
  <div className="flex flex-wrap items-end justify-between gap-4">
    <div><p className="post-eyebrow">THE COMMUNITY COLLECTION</p><h2 className="post-serif mt-2 text-2xl">A good story deserves a good cover.</h2><p className="mt-2 text-xs leading-5 text-stone-400">12 original PNG covers + <span className="text-[#b5c4a5]">your own uploads</span>. Ready to attach, download or make part of your next post.</p></div>
    <label className="relative"><Search size={14} className="absolute left-3 top-3.5 text-stone-400"/><input aria-label="Search cover library" className="ios-input !pl-9 text-xs" placeholder="Find a cover…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
  </div>

  {/* Tabs + Upload */}
  <div className="mt-5 flex flex-wrap items-center gap-2">
    <div className="flex rounded-full border border-white/10 bg-white/[0.03] p-1">
      <button onClick={()=>setTab("collection")} aria-pressed={tab==="collection"} className={`rounded-full px-4 py-2 text-xs font-semibold transition ${tab==="collection"?"bg-[#b5c4a5] text-[#151b18]":"text-stone-400"}`}>Collection · 12</button>
      <button onClick={()=>setTab("yours")} aria-pressed={tab==="yours"} className={`rounded-full px-4 py-2 text-xs font-semibold transition ${tab==="yours"?"bg-[#b5c4a5] text-[#151b18]":"text-stone-400"}`}>Your Assets · {custom.length}</button>
    </div>
    <button onClick={()=>fileRef.current?.click()} className="ios-btn ios-btn-primary text-xs !py-2"><Upload size={14}/> Upload Your Own</button>
    <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={handleUpload} />
    <span className="text-[10px] text-stone-500">PNG/JPEG/WebP · 1.5 MB · up to 10 · stored in this browser</span>
  </div>
  {notice&&<p role="status" className="mt-3 rounded-xl bg-[#b5c4a5]/10 px-3 py-2 text-xs text-[#c5d6b3]">{notice}</p>}

  <div className="my-5 flex flex-wrap gap-2">{["All","Community","Announcements","Events","Editorial","Your assets"].map(c=><button key={c} aria-pressed={category===c} onClick={()=>setCategory(c)} className={`rounded-full border px-3 py-1.5 text-[11px] transition ${c===category?"border-[#b5c4a5]/40 bg-[#b5c4a5]/15 text-[#d7e2ca]":"border-white/10 text-stone-400 hover:text-white"}`}>{c}</button>)}</div>

  {tab==="yours" && (
    custom.length===0 ? (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-10 text-center">
        <Sparkles size={28} className="mx-auto text-[#b5c4a5]/50"/>
        <h3 className="mt-3 text-sm font-semibold">No custom assets yet</h3>
        <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-stone-400">Upload your own PNG/JPEG covers — logos, photos, brand backgrounds. They stay in this browser (localStorage), up to 10 covers of 1.5 MB, and you can use them instantly as post covers.</p>
        <button onClick={()=>fileRef.current?.click()} className="ios-btn ios-btn-glass mt-4 text-xs"><ImagePlus size={14}/> Choose an image</button>
      </div>
    ) : (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filteredCustom.map(a=>{
          const active=selected===a.dataUrl;
          return <article key={a.id} className={`overflow-hidden rounded-2xl border bg-[#1c201e] ${active?"border-[#b5c4a5]/60":"border-white/10"}`}>
            <button disabled={disabled} onClick={()=>onSelect(a.dataUrl)} className="group block w-full overflow-hidden disabled:opacity-40" aria-label={`Use ${a.title} cover`}>
              <img src={a.dataUrl} alt={`${a.title} custom cover`} width={1200} height={675} loading="lazy" className="aspect-video w-full object-cover transition duration-300 group-hover:scale-[1.03]"/>
            </button>
            <div className="flex items-center justify-between gap-3 p-4">
              <div><p className="text-[9px] uppercase tracking-[.15em] text-[#b5c4a5]">Your assets · {new Date(a.createdAt).toLocaleDateString()}</p><h3 className="mt-1 text-xs font-medium text-stone-200">{a.title}</h3></div>
              <div className="flex gap-1">
                <a href={a.dataUrl} download={`${a.title}.png`} aria-label={`Download ${a.title}`} className="rounded-lg p-2 text-stone-400 hover:bg-white/5 hover:text-white"><ArrowDownToLine size={15}/></a>
                <button disabled={disabled} onClick={()=>onSelect(a.dataUrl)} aria-label={`Attach ${a.title}`} className="rounded-lg bg-[#b5c4a5]/10 p-2 text-[#c5d6b3] disabled:opacity-40">{active?<Check size={15}/>:<ImagePlus size={15}/>}</button>
                <button onClick={()=>deleteCustom(a.id)} aria-label={`Delete ${a.title}`} className="rounded-lg p-2 text-rose-300 hover:bg-rose-500/10"><Trash2 size={14}/></button>
              </div>
            </div>
          </article>
        })}
      </div>
    )
  )}

  {tab==="collection" && (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{filtered.map(a=>{const path=`/post-assets/${a.id}.png`;const active=selected.endsWith(path);return <article key={a.id} className={`overflow-hidden rounded-2xl border bg-[#1c201e] ${active?"border-[#b5c4a5]/60":"border-white/10"}`}><button disabled={disabled} onClick={()=>onSelect(path)} className="group block w-full overflow-hidden disabled:opacity-40" aria-label={`Use ${a.title} cover`}><img src={path} alt={`${a.title} editorial cover`} width={1200} height={675} loading="lazy" className="aspect-video w-full object-cover transition duration-300 group-hover:scale-[1.03]"/></button><div className="flex items-center justify-between gap-3 p-4"><div><p className="text-[9px] uppercase tracking-[.15em] text-stone-500">{a.category}</p><h3 className="mt-1 text-xs font-medium text-stone-200">{a.title}</h3></div><div className="flex gap-1"><a href={path} download={`${a.id}-cover.png`} aria-label={`Download ${a.title}`} className="rounded-lg p-2 text-stone-400 hover:bg-white/5 hover:text-white"><ArrowDownToLine size={15}/></a><button disabled={disabled} onClick={()=>onSelect(path)} aria-label={`Attach ${a.title}`} className="rounded-lg bg-[#b5c4a5]/10 p-2 text-[#c5d6b3] disabled:opacity-40">{active?<Check size={15}/>:<ImagePlus size={15}/>}</button></div></div></article>})}</div>
  )}
  {!filtered.length && tab==="collection" && <p role="status" className="rounded-xl border border-white/10 p-6 text-sm text-stone-400">No covers match your search. Try another category.</p>}
  <p className="mt-4 flex items-center gap-2 text-[10px] leading-5 text-stone-500"><Heart size={12} className="text-[#b5c4a5]/60"/> 1200 × 675 px · Original Videl artwork + your uploads · Your assets are stored locally in this browser, up to 10 covers. Use them as post covers or download anytime.</p>
 </section>
}
