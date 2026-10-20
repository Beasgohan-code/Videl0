"use client";
import {useEffect,useState} from "react";
import {BRAND_KEY,parseBrandKits,type BrandKit} from "@/lib/studio-workflows";
import type {ImageDesign} from "@/lib/image-design";
export function BrandKits({design,onApply,disabled=false}:{design:ImageDesign;onApply:(value:Partial<ImageDesign>)=>void;disabled?:boolean}){
 const [kits,setKits]=useState<BrandKit[]>([]),[name,setName]=useState(""),[notice,setNotice]=useState("");
 useEffect(()=>{try{setKits(parseBrandKits(JSON.parse(localStorage.getItem(BRAND_KEY)||"[]")))}catch{setNotice("Brand storage is unavailable.")}},[]);
 function persist(next:BrandKit[]){try{localStorage.setItem(BRAND_KEY,JSON.stringify(next));setKits(next);return true}catch{setNotice("Brand kit not saved: browser storage unavailable.");return false}}
 return <section className="space-y-2 rounded-xl border border-white/10 p-3"><h3 className="text-sm font-semibold">Brand kits</h3><p className="ios-caption">Reusable colors and font · this browser only. Apply after choosing a layout.</p>
 <input aria-label="Brand kit name" className="ios-input" placeholder="Brand kit name" value={name} maxLength={40} disabled={disabled} onChange={e=>setName(e.target.value)}/>
 <button className="ios-btn ios-btn-glass text-xs" disabled={disabled||!name.trim()||kits.length>=20} onClick={()=>{const {background,accent,color,font}=design;if(persist([{id:crypto.randomUUID(),name:name.trim(),background,accent,color,font},...kits])){setName("");setNotice("Brand kit saved.")}}}>Save current brand</button>
 {kits.map(kit=><div key={kit.id} className="flex items-center gap-2"><button disabled={disabled} className="ios-btn ios-btn-glass min-w-0 flex-1 truncate text-xs" aria-label={`Apply brand ${kit.name}`} onClick={()=>{onApply({background:kit.background,accent:kit.accent,color:kit.color,font:kit.font});setNotice(`Applied ${kit.name}.`)}}><span aria-hidden style={{background:kit.accent}} className="h-3 w-3 rounded-full"/>{kit.name}</button><button disabled={disabled} className="ios-pill" aria-label={`Delete brand ${kit.name}`} onClick={()=>persist(kits.filter(k=>k.id!==kit.id))}>×</button></div>)}
 {notice&&<p role="status" className="ios-caption">{notice}</p>}</section>
}
