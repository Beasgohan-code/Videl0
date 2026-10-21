"use client";
import {useEffect,useRef,useState} from 'react';
import {ImagePlus,Video,Mic,Square,Send,X,Paperclip,LoaderCircle,Smile} from 'lucide-react';
import type {GroupMessage} from '@/lib/group-view';
import {visibleLength} from '@/lib/telegram-format';
import {RichComposer} from '@/components/editor/RichComposer';

type Kind='photo'|'video'|'voice';

/**
 * Bot messenger composer: a real Telegram-style rich editor (formatting by
 * selection, premium emoji, spoilers) plus photo, video and voice attachments.
 */
export default function InboxComposer({chatId,reply,text,setText,busy,active,richText,onCancelReply,onSend}:{
 chatId:number|null;active:boolean;reply:GroupMessage|null;text:string;setText:(text:string)=>void;busy:boolean;
 richText?:boolean;onCancelReply:()=>void;onSend:(file:File|null,kind:Kind|null)=>Promise<boolean>;
}){
 const [attachment,setAttachment]=useState<{file:File;kind:Kind}|null>(null),[preview,setPreview]=useState('');
 const [error,setError]=useState(''),[recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0);
 const requesting=useRef(false),attachmentsMenu=useRef<HTMLDetailsElement>(null);
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
 function choose(kind:Kind){pickKind.current=kind;if(attachmentsMenu.current)attachmentsMenu.current.open=false;if(input.current){input.current.accept=kind==='photo'?'image/jpeg,image/png,image/webp':kind==='video'?'video/mp4':'audio/ogg,audio/webm,audio/mpeg,audio/mp4';input.current.click();}}
 const plainLen=visibleLength(text);
 const limit=attachment?1024:4096;
 const isOverLimit=plainLen>limit;
 const empty=!text.trim()&&!attachment;
 async function send(){if(!chatId||busy||recording||!active||empty||isOverLimit)return;setError('');const epoch=generation.current;const ok=await onSend(attachment?.file||null,attachment?.kind||null);if(ok&&epoch===generation.current){setAttachment(null);}}

 return <div className="tg-composer tg-composer-premium border-t border-white/[0.06] bg-[#0a0e1e]/80 p-3 backdrop-blur-2xl sm:p-4">
  {reply&&<div className="mb-3 flex justify-between gap-3 rounded-xl border-l-[3px] border-teal-400/50 bg-teal-500/[0.06] p-3"><div className="min-w-0"><p className="text-[11px] font-semibold text-teal-300">Replying as bot to {reply.sender_name}</p><p className="mt-1 truncate text-[11px] text-indigo-100/50">#{reply.message_id} · {reply.text||reply.media?.kind}</p></div><button aria-label="Cancel reply" onClick={onCancelReply} className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-white/50 hover:bg-white/5 hover:text-white"><X size={15}/></button></div>}
  {attachment&&<div className="mb-3 rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10"><div className="flex items-center justify-between"><span className="truncate text-[11px] font-medium text-white/70">{attachment.kind} · {attachment.file.name} · {(attachment.file.size/1024).toFixed(0)} KB</span><button aria-label="Remove attachment" disabled={busy} onClick={()=>setAttachment(null)} className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-white/50 hover:bg-white/5 hover:text-white disabled:opacity-40"><X size={15}/></button></div>{preview&&attachment.kind==='photo'&&<img src={preview} alt="Attachment preview" className="mt-2 max-h-40 rounded-xl object-contain"/>}{preview&&attachment.kind==='video'&&<video src={preview} controls className="mt-2 max-h-40 rounded-xl"/>}{preview&&attachment.kind==='voice'&&<audio src={preview} controls className="mt-2 w-full"/>}</div>}

  <RichComposer value={text} onChange={setText} disabled={!chatId||busy||recording||!active} onSubmit={()=>void send()} limit={limit}
    placeholder={attachment?'Add an optional caption… select text to style':'Message… select text to style, Ctrl+Enter to send'} />

  {!richText&&<p role="status" className="mt-2 rounded-xl bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200/90">Rich formatting is waiting for the backend update. Messages will be sent as plain text until the bot reports support — formatting is kept in your draft.</p>}
  {error&&<p role="alert" className="mt-2 rounded-xl bg-rose-500/10 px-3 py-2 text-[11px] text-rose-200">{error}</p>}
  {recording&&<p role="status" className="mt-2 flex items-center gap-2 rounded-full bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-200 ring-1 ring-rose-500/20"><span className="h-2 w-2 animate-pulse rounded-full bg-rose-400"/> Recording {seconds}s / 120s · Tap stop to preview before sending</p>}

  <div className="tg-compose-row mt-2 flex items-end gap-2 rounded-[22px] bg-white/[0.06] p-2 ring-1 ring-white/10 backdrop-blur">
   <details ref={attachmentsMenu} className="tg-attachment-menu shrink-0"><summary aria-label="Attach media" title="Attach photo, video or voice" className="grid h-11 w-11 place-items-center rounded-full bg-white/5 text-white/70 transition hover:bg-white/10"><Paperclip size={18}/></summary><div className="tg-attachment-options" role="group" aria-label="Attachment types">
     <button aria-label="Attach photo" title="Photo" disabled={!chatId||busy||recording} onClick={()=>choose('photo')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><ImagePlus size={16} aria-hidden/></button>
     <button aria-label="Attach video" title="MP4 video" disabled={!chatId||busy||recording} onClick={()=>choose('video')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><Video size={16} aria-hidden/></button>
     <button aria-label="Upload voice message" title="Upload voice" disabled={!chatId||busy||recording} onClick={()=>choose('voice')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><Paperclip size={16} aria-hidden/></button>
   </div></details>
   <div className={`tg-compose-hint-box min-w-0 flex-1 text-[10px] ${isOverLimit?'text-rose-300':'text-white/30'}`}>
     {plainLen>0?`${plainLen}/${limit}${isOverLimit?' · too long':''} · `:''}Select text for formatting · <span className="hidden sm:inline">Ctrl+B / Ctrl+I / Ctrl+U · </span><Smile size={10} className="inline"/> premium emoji in the toolbar
   </div>
   <button aria-label={recording?'Stop recording':'Record voice message'} onClick={()=>recording?recorder.current?.stop():void record()} disabled={!chatId||busy} className={`grid h-11 w-11 shrink-0 place-items-center rounded-full transition ${recording?'animate-pulse bg-rose-500 text-white':'bg-white/5 text-white/70 hover:bg-white/10'}`}>{recording?<Square size={16}/>:<Mic size={16}/>}</button>
   <button disabled={busy||!chatId||recording||empty||isOverLimit} onClick={()=>void send()} aria-label="Send as bot" title="Send as bot" aria-busy={busy} className="tg-send ios-btn ios-btn-primary grid h-11 w-11 shrink-0 place-items-center rounded-full p-0 shadow-lg disabled:opacity-40">{busy?<LoaderCircle size={16} className="animate-spin"/>:<Send size={16}/>}</button>
  </div>
  <input ref={input} type="file" hidden onChange={event=>{const file=event.target.files?.[0];if(file){if(file.size>4*1024*1024)setError('Uploads are limited to 4 MB. Use a smaller photo or short MP4 clip.');else{setAttachment({file,kind:pickKind.current});setError('');}}event.target.value='';}}/>
 </div>;
}
