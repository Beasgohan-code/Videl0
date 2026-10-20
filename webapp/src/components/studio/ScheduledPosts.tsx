"use client";
import {useEffect,useRef,useState} from "react";
import type {ButtonRow} from "@/lib/post-buttons";
type Job={id:string;status:string;chat_id:string;scheduled_at:string;text:string;message_id?:number};
export function ScheduledPosts({chatId,text,mediaUrl,buttons,hasLocalImage,reviewed,disabled}:{chatId:string;text:string;mediaUrl:string;buttons:ButtonRow[];hasLocalImage:boolean;reviewed:boolean;disabled:boolean}){
 const [zone,setZone]=useState("device local time");
 useEffect(()=>setZone(Intl.DateTimeFormat().resolvedOptions().timeZone),[]);
 const request=useRef<{fingerprint:string;id:string}|null>(null);
 const [date,setDate]=useState(""),[jobs,setJobs]=useState<Job[]>([]),[notice,setNotice]=useState(""),[busy,setBusy]=useState(false);
 async function refresh(){const r=await fetch("/api/schedules",{cache:"no-store"});const data=await r.json();if(!r.ok||!data.ok)throw new Error(data.error||"Queue unavailable");setJobs(data.jobs)}
 async function run(action:()=>Promise<void>){if(busy)return;setBusy(true);setNotice("");try{await action()}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
 return <section className="ios-card space-y-3 p-4"><h2 className="font-semibold">Scheduled publishing</h2><p className="ios-caption">Times use your device timezone ({zone}) and are saved in UTC. Mongo-backed; due posts dispatch approximately once a minute while the bot is running. Jobs over 24 hours late are marked missed.</p>
 <label className="block text-xs">Scheduled time<input aria-label="Scheduled time" type="datetime-local" className="ios-input mt-2" value={date} disabled={busy||disabled} onChange={e=>setDate(e.target.value)}/></label>
 {hasLocalImage&&<p className="ios-caption">Use a persistent HTTPS image URL for scheduling; local image uploads cannot be scheduled.</p>}
 <div className="flex flex-wrap gap-2"><button disabled={disabled||busy||!date||!reviewed||!chatId.trim()||hasLocalImage||(!text.trim()&&!mediaUrl)} className="ios-btn ios-btn-primary text-xs" onClick={()=>void run(async()=>{
   const instant=new Date(date);if(!Number.isFinite(instant.getTime()))throw new Error("Choose a valid time.");
   if(!window.confirm(`Schedule the current post to ${chatId} at ${instant.toLocaleString()}?`))return;
   const snapshot={chat_id:chatId.trim(),text,media_url:mediaUrl.trim(),buttons,schedule_at:instant.toISOString()};
   const fingerprint=JSON.stringify(snapshot);
   if(request.current?.fingerprint!==fingerprint)request.current={fingerprint,id:crypto.randomUUID()};
   const response=await fetch("/api/schedules",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...snapshot,request_id:request.current.id})});
   const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Schedule unconfirmed. Refresh before retrying.");
   setNotice(`Schedule ${data.status}: ${data.job_id}`);await refresh();
 })}>Schedule reviewed post</button><button disabled={busy||disabled} className="ios-btn ios-btn-glass text-xs" onClick={()=>void run(refresh)}>Refresh scheduled posts</button></div>
 <p className="ios-caption">Sending/unconfirmed posts cannot be cancelled or automatically retried. Check Telegram before scheduling another copy. Editing the studio does not change an already scheduled snapshot.</p>
 {notice&&<p role="status" className="text-xs">{notice}</p>}
 {jobs.map(job=><div key={job.id} className="space-y-2 rounded-xl bg-white/[0.035] p-3"><p className="text-sm">{job.status} · {job.chat_id}</p><p className="ios-caption">{new Date(job.scheduled_at).toLocaleString()} · {job.id}</p><p className="truncate text-xs">{job.text.replace(/<[^>]+>/g,"")}</p>{job.status==="pending"&&<button className="ios-pill" disabled={busy||disabled} onClick={()=>void run(async()=>{if(!window.confirm("Cancel this scheduled post?"))return;const response=await fetch("/api/schedules",{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:job.id})});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Cancellation unconfirmed; refresh.");await refresh()})}>Cancel scheduled post</button>}</div>)}</section>
}
