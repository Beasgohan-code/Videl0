"use client";
import {useEffect,useRef,useState} from "react";
import type {ButtonRow} from "@/lib/post-buttons";
type Job={id:string;status:string;chat_id:string;scheduled_at:string;text:string;message_id?:number;attempts?:number;repeat?:string|null;sent_count?:number;skipped?:number;error?:string|null;finished_at?:string|null};
const STATUS_COPY:Record<string,string>={
 pending:"Queued",sending:"Sending now",sent:"Delivered",failed:"Rejected by Telegram",
 unconfirmed:"Outcome unknown",missed:"Missed (over a day late)",cancelled:"Cancelled",
};
const REPEAT_COPY:Record<string,string>={daily:"Every day",weekly:"Every week"};
const STATUS_HELP:Record<string,string>={
 pending:"Waiting for its scheduled time.",
 sending:"The bot has claimed this job and is calling the Bot API.",
 sent:"Telegram accepted the message.",
 failed:"Telegram refused it. Nothing was delivered, so a retry is safe.",
 unconfirmed:"The bot could not confirm delivery. Check Telegram before resending anything.",
 missed:"The bot was offline for more than a day past the due time; it is never sent late.",
 cancelled:"Cancelled before it was due.",
};
export function ScheduledPosts({chatId,text,mediaUrl,buttons,hasLocalImage,reviewed,disabled}:{chatId:string;text:string;mediaUrl:string;buttons:ButtonRow[];hasLocalImage:boolean;reviewed:boolean;disabled:boolean}){
 const [zone,setZone]=useState("device local time");
 useEffect(()=>setZone(Intl.DateTimeFormat().resolvedOptions().timeZone),[]);
 const request=useRef<{fingerprint:string;id:string}|null>(null);
 const [repeat,setRepeat]=useState("once");
 const [date,setDate]=useState(""),[jobs,setJobs]=useState<Job[]>([]),[notice,setNotice]=useState(""),[busy,setBusy]=useState(false);
 // A copy is a brand-new post: it needs its own time, never the original's.
 const [copyFor,setCopyFor]=useState(""),[copyWhen,setCopyWhen]=useState("");
 function localSlot(when:Date){const shifted=new Date(when.getTime()-when.getTimezoneOffset()*60000);return shifted.toISOString().slice(0,16)}
 async function refresh(){const r=await fetch("/api/schedules",{cache:"no-store"});const data=await r.json();if(!r.ok||!data.ok)throw new Error(data.error||"Queue unavailable");setJobs(data.jobs)}
 async function run(action:()=>Promise<void>){if(busy)return;setBusy(true);setNotice("");try{await action()}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
 const counts=jobs.reduce<Record<string,number>>((total,job)=>{total[job.status]=(total[job.status]??0)+1;return total},{});
 const ordered=[...jobs].sort((a,b)=>{
  const rank=(job:Job)=>job.status==="pending"?0:job.status==="sending"?1:2;
  const difference=rank(a)-rank(b);
  if(difference)return difference;
  if(rank(a)===0)return Date.parse(a.scheduled_at)-Date.parse(b.scheduled_at);
  return Date.parse(b.scheduled_at)-Date.parse(a.scheduled_at);
 });
 function late(job:Job){return job.status==="pending"&&Date.parse(job.scheduled_at)<Date.now()}
 return <section className="ios-card space-y-3 p-4"><h2 className="font-semibold">Scheduled publishing</h2><p className="ios-caption">Times use your device timezone ({zone}) and are saved in UTC. Mongo-backed; due posts dispatch approximately once a minute while the bot is running. Jobs over 24 hours late are marked missed.</p>
 <div className="flex flex-wrap gap-2"><label className="block text-xs">Scheduled time<input aria-label="Scheduled time" type="datetime-local" className="ios-input mt-2" value={date} disabled={busy||disabled} onChange={e=>setDate(e.target.value)}/></label>
 <label className="block text-xs">Repeat<select aria-label="Repeat" className="ios-input mt-2" value={repeat} disabled={busy||disabled} onChange={e=>setRepeat(e.target.value)}><option value="once">Once</option><option value="daily">Every day</option><option value="weekly">Every week</option></select></label></div>
 {hasLocalImage&&<p className="ios-caption">Use a persistent HTTPS image URL for scheduling; local image uploads cannot be scheduled.</p>}
 <div className="flex flex-wrap gap-2"><button disabled={disabled||busy||!date||!reviewed||!chatId.trim()||hasLocalImage||(!text.trim()&&!mediaUrl)} className="ios-btn ios-btn-primary text-xs" onClick={()=>void run(async()=>{
   const instant=new Date(date);if(!Number.isFinite(instant.getTime()))throw new Error("Choose a valid time.");
   if(!window.confirm(`Schedule the current post to ${chatId} at ${instant.toLocaleString()}${repeat==="once"?"":" and repeat it "+REPEAT_COPY[repeat].toLowerCase()}?`))return;
   const snapshot={chat_id:chatId.trim(),text,media_url:mediaUrl.trim(),buttons,schedule_at:instant.toISOString()};
   const fingerprint=JSON.stringify({...snapshot,repeat});
   if(request.current?.fingerprint!==fingerprint)request.current={fingerprint,id:crypto.randomUUID()};
   const response=await fetch("/api/schedules",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...snapshot,request_id:request.current.id,repeat:repeat==="once"?undefined:repeat})});
   const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Schedule unconfirmed. Refresh before retrying.");
   setNotice(`Schedule ${data.status}: ${data.job_id}`);await refresh();
 })}>Schedule reviewed post</button><button disabled={busy||disabled} className="ios-btn ios-btn-glass text-xs" onClick={()=>void run(refresh)}>Refresh scheduled posts</button></div>
 <p className="ios-caption">A Telegram rate limit is retried automatically and shows as Queued with the interval it is waiting for. Any other failure is final and waits for you — a duplicate post is worse than a missing one. Editing the studio does not change an already scheduled snapshot. A finished post can be copied as a new post at a time you choose; the original is never resent. A repeating post keeps its own place in the queue: after each delivery it moves itself forward, and cancelling it stops the series. One failure stops a series and waits for you, and a series that falls more than a day behind skips the missed copies instead of sending them late.</p>
 {jobs.length>0&&<div className="flex flex-wrap gap-1.5">{Object.entries(counts).map(([status,value])=><span key={status} data-tone={status==="sent"?"good":status==="failed"?"bad":status==="unconfirmed"||status==="missed"?"warn":"neutral"} className="ios-pill text-[10px]">{STATUS_COPY[status]??status} · {value}</span>)}</div>}
 {notice&&<p role="status" className="text-xs">{notice}</p>}
 {ordered.map(job=><div key={job.id} className="space-y-2 rounded-xl bg-white/[0.035] p-3">
   <div className="flex flex-wrap items-baseline justify-between gap-2"><p className="text-sm">{STATUS_COPY[job.status]??job.status} · {job.chat_id}</p><span className="flex items-center gap-1.5">{job.repeat?<span className="ios-pill text-[10px]" data-tone="good">{REPEAT_COPY[job.repeat]??job.repeat}</span>:null}{job.attempts?<span className="ios-pill text-[10px]" data-tone="warn">auto-retry {job.attempts}</span>:null}{late(job)&&<span className="ios-pill text-[10px]" data-tone="warn">due now</span>}</span></div>
   <p className="ios-caption">{new Date(job.scheduled_at).toLocaleString()} · {job.id}{job.attempts?` · ${job.attempts} automatic ${job.attempts===1?"retry":"retries"}`:""}{job.finished_at?` · finished ${new Date(job.finished_at).toLocaleString()}`:""}{job.sent_count?` · delivered ${job.sent_count} ${job.sent_count===1?"time":"times"}`:""}{job.skipped?` · ${job.skipped} skipped while offline`:""}</p>
   {job.error&&<p role="status" className="text-xs text-amber-200">{job.error}</p>}
   {STATUS_HELP[job.status]&&<p className="ios-caption">{STATUS_HELP[job.status]}</p>}
   <p className="truncate text-xs">{job.text.replace(/<[^>]+>/g,"")}</p>
   <div className="flex flex-wrap gap-2">
   {job.status==="pending"&&<button className="ios-pill" disabled={busy||disabled} onClick={()=>void run(async()=>{if(!window.confirm("Cancel this scheduled post?"))return;const response=await fetch("/api/schedules",{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:job.id})});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Cancellation unconfirmed; refresh.");await refresh()})}>Cancel scheduled post</button>}
   {job.status!=="pending"&&job.status!=="sending"&&<button className="ios-pill" disabled={busy||disabled} onClick={()=>{setCopyFor(job.id);setCopyWhen(localSlot(new Date(Date.now()+3600000)))}}>Send a new copy</button>}
   {job.status==="failed"&&<button className="ios-pill" disabled={busy||disabled} onClick={()=>void run(async()=>{if(!window.confirm("Requeue this rejected post? Telegram refused it, so nothing was delivered."))return;const response=await fetch("/api/schedules/retry",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:job.id})});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Requeue unconfirmed; refresh.");setNotice(`Requeued for ${new Date(data.scheduled_at).toLocaleString()}.`);await refresh()})}>Retry rejected post</button>}
   </div>
   {copyFor===job.id&&<div className="flex flex-wrap items-end gap-2 rounded-xl border border-white/10 p-2">
     <label className="text-[11px]">Copy time<input aria-label="Copy time" type="datetime-local" className="ios-input mt-1" value={copyWhen} disabled={busy||disabled} onChange={e=>setCopyWhen(e.target.value)}/></label>
     <button className="ios-pill" disabled={busy||disabled||!copyWhen} onClick={()=>void run(async()=>{
       const instant=new Date(copyWhen);if(!Number.isFinite(instant.getTime()))throw new Error("Choose a valid time.");
       if(!window.confirm(`Queue a new copy of this post to ${job.chat_id} at ${instant.toLocaleString()}? The original is not affected.`))return;
       const response=await fetch("/api/schedules/duplicate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:job.id,schedule_at:instant.toISOString()})});
       const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"Copy unconfirmed; refresh.");
       setNotice(`Copy queued for ${new Date(data.scheduled_at).toLocaleString()}.`);setCopyFor("");await refresh()
     })}>Queue copy</button>
     <button className="ios-pill" disabled={busy} onClick={()=>setCopyFor("")}>Dismiss</button>
   </div>}
 </div>)}</section>
}
