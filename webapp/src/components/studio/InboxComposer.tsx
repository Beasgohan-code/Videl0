"use client";
import {useEffect,useRef,useState} from 'react';
import {ImagePlus,Video,Mic,Square,Send,X,Paperclip,LoaderCircle} from 'lucide-react';
import type {GroupMessage} from '@/lib/group-view';

type Kind='photo'|'video'|'voice';
export default function InboxComposer({chatId,reply,text,setText,busy,active,onCancelReply,onSend}:{
 chatId:number|null;active:boolean;reply:GroupMessage|null;text:string;setText:(text:string)=>void;busy:boolean;
 onCancelReply:()=>void;onSend:(file:File|null,kind:Kind|null)=>Promise<boolean>;
}){
 const [attachment,setAttachment]=useState<{file:File;kind:Kind}|null>(null),[preview,setPreview]=useState('');
 const [error,setError]=useState(''),[recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0);
 const requesting=useRef(false);
 const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),generation=useRef(0);
 const timer=useRef<ReturnType<typeof setInterval>|null>(null),input=useRef<HTMLInputElement>(null),pickKind=useRef<Kind>('photo');
 useEffect(()=>{
  generation.current++;setAttachment(null);setRecording(false);setSeconds(0);setError('');
  return()=>{generation.current++;if(timer.current)clearInterval(timer.current);if(recorder.current?.state==='recording')recorder.current.stop();stream.current?.getTracks().forEach(track=>track.stop());};
 },[chatId]);
 useEffect(()=>{
  function stopHidden(){if(document.visibilityState==='hidden'&&recorder.current?.state==='recording')recorder.current.stop();}
  document.addEventListener('visibilitychange',stopHidden);
  return()=>document.removeEventListener('visibilitychange',stopHidden);
 },[]);
 useEffect(()=>{
  if(!active){generation.current++;if(recorder.current?.state==='recording')recorder.current.stop();stream.current?.getTracks().forEach(track=>track.stop());if(timer.current)clearInterval(timer.current);setRecording(false);}
 },[active]);
 useEffect(()=>{
  if(!attachment){setPreview('');return;}
  const url=URL.createObjectURL(attachment.file);setPreview(url);return()=>URL.revokeObjectURL(url);
 },[attachment]);
 async function record(){
  if(!chatId||busy||recording||requesting.current||!active)return;
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){setError('Microphone recording needs HTTPS and a browser with MediaRecorder. You can upload a voice file instead.');return;}
  requesting.current=true;const epoch=generation.current;setError('');
  try{
   const media=await navigator.mediaDevices.getUserMedia({audio:true});
   if(epoch!==generation.current){media.getTracks().forEach(track=>track.stop());return;}
   stream.current=media;const type=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(value=>MediaRecorder.isTypeSupported(value));
   const device=new MediaRecorder(media,type?{mimeType:type}:undefined);recorder.current=device;
   const parts:BlobPart[]=[];let size=0,elapsed=0,tooLarge=false;
   device.ondataavailable=event=>{if(event.data.size){size+=event.data.size;if(size>4*1024*1024){tooLarge=true;if(device.state==='recording')device.stop();}else parts.push(event.data);}};
   device.onstop=()=>{
    media.getTracks().forEach(track=>track.stop());if(timer.current)clearInterval(timer.current);
    if(epoch!==generation.current)return;
    setRecording(false);if(tooLarge){setError('Recording exceeded 4 MB. Try a shorter voice message.');return;}
    const blob=new Blob(parts,{type:device.mimeType||'audio/webm'});
    if(blob.size)setAttachment({file:new File([blob],'voice-recording',{type:blob.type}),kind:'voice'});
   };
   device.onerror=()=>{media.getTracks().forEach(track=>track.stop());if(timer.current)clearInterval(timer.current);if(epoch===generation.current){setRecording(false);setError('The microphone recording failed. Try uploading a voice file.');}};
   device.start(500);setRecording(true);setSeconds(0);
   timer.current=setInterval(()=>{elapsed++;setSeconds(elapsed);if(elapsed>=120&&device.state==='recording')device.stop();},1000);
  }catch{stream.current?.getTracks().forEach(track=>track.stop());if(epoch===generation.current)setError('Microphone access was denied or is unavailable. Check browser permissions.');}finally{requesting.current=false;}
 }
 function choose(kind:Kind){pickKind.current=kind;if(input.current){input.current.accept=kind==='photo'?'image/jpeg,image/png,image/webp':kind==='video'?'video/mp4':'audio/ogg,audio/webm,audio/mpeg,audio/mp4';input.current.click();}}
 const limit=attachment?1024:4096;
 async function send(){if(!chatId||busy||recording||!active)return;setError('');const epoch=generation.current;const ok=await onSend(attachment?.file||null,attachment?.kind||null);if(ok&&epoch===generation.current)setAttachment(null);}
 return <div className="border-t border-indigo-300/10 p-4">
  {reply&&<div className="mb-3 flex justify-between gap-3 border-l-2 border-teal-300/60 pl-3"><div className="min-w-0"><p className="text-[11px] text-teal-200">Replying as bot to {reply.sender_name}</p><p className="mt-1 truncate text-[11px] text-indigo-100/45">#{reply.message_id} · {reply.text||reply.media?.kind}</p></div><button aria-label="Cancel reply" onClick={onCancelReply}><X size={14}/></button></div>}
  {attachment&&<div className="mb-3 rounded-xl bg-white/5 p-3"><div className="flex items-center justify-between"><span className="truncate text-[11px] text-indigo-100/60">{attachment.kind} · {attachment.file.name} · {(attachment.file.size/1024).toFixed(0)} KB</span><button aria-label="Remove attachment" disabled={busy} onClick={()=>setAttachment(null)}><X size={14}/></button></div>{preview&&attachment.kind==='photo'&&<img src={preview} alt="Attachment preview" className="mt-2 max-h-44 rounded-lg object-contain"/>}{preview&&attachment.kind==='video'&&<video controls src={preview} className="mt-2 max-h-44 rounded-lg"/>}{preview&&attachment.kind==='voice'&&<audio controls src={preview} className="mt-2 max-w-full"/>}</div>}
  {error&&<p role="alert" className="mb-3 text-xs text-rose-200">{error}</p>}
  <textarea onKeyDown={event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)&&!event.nativeEvent.isComposing&&!busy&&!recording&&chatId&&(text.trim()||attachment)&&text.length<=limit){event.preventDefault();void send();}}} aria-label="Message as bot" value={text} onChange={event=>setText(event.target.value)} disabled={!chatId||busy||recording} rows={2} className="ios-input resize-none text-sm" placeholder={attachment?'Add an optional caption…':'Write a message as your bot…'}/>
  <input ref={input} type="file" hidden onChange={event=>{const file=event.target.files?.[0];if(file){if(file.size>4*1024*1024)setError('Uploads are limited to 4 MB. Use a smaller photo or short MP4 clip.');else{setAttachment({file,kind:pickKind.current});setError('');}}event.target.value='';}}/>
  <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-1">
   <button aria-label="Attach photo" title="Photo" disabled={!chatId||busy||recording} onClick={()=>choose('photo')} className="ios-btn ios-btn-glass !p-2"><ImagePlus size={16}/></button>
   <button aria-label="Attach video" title="MP4 video" disabled={!chatId||busy||recording} onClick={()=>choose('video')} className="ios-btn ios-btn-glass !p-2"><Video size={16}/></button>
   <button aria-label="Upload voice message" title="Upload voice" disabled={!chatId||busy||recording} onClick={()=>choose('voice')} className="ios-btn ios-btn-glass !p-2"><Paperclip size={16}/></button>
   <button aria-label={recording?'Stop recording':'Record voice message'} onClick={()=>recording?recorder.current?.stop():void record()} disabled={!chatId||busy} className={`ios-btn ios-btn-glass !p-2 ${recording?'text-rose-300':''}`}>{recording?<Square size={16}/>:<Mic size={16}/>}</button>
   {recording&&<span role="status" className="ml-2 text-[11px] text-rose-200">Recording {seconds}s / 120s</span>}
  </div><button disabled={busy||!chatId||recording||(!text.trim()&&!attachment)||text.length>limit} onClick={()=>void send()} className="ios-btn ios-btn-primary text-xs">{busy?<LoaderCircle size={14} className="animate-spin"/>:<Send size={14}/>}Send as bot</button></div>
  <p className={`mt-2 text-[10px] ${text.length>limit?'text-rose-300':'text-indigo-100/35'}`}>{text.length}/{limit} · Uploads up to 4 MB · Voice up to 2 min · Ctrl/⌘ + Enter to send</p>
 </div>;
}
