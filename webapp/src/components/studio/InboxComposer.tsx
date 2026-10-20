"use client";
import {useEffect,useRef,useState} from 'react';
import {ImagePlus,Video,Mic,Square,Send,X,Paperclip,LoaderCircle,Bold,Italic,Underline as UnderlineIcon,Strikethrough,Code2,EyeOff,Quote,Link2,Sparkles,Eye,Smile,ChevronDown,Wand2} from 'lucide-react';
import type {GroupMessage} from '@/lib/group-view';
import {previewHtml, safeLink, visibleLength, wrapWithTag} from '@/lib/telegram-format';

type Kind='photo'|'video'|'voice';

// Real custom-emoji document IDs (UI Pro White pack + Telegram's documented 👍).
// The fallback character is shown where custom emoji cannot be rendered.
const PREMIUM_PRESETS: {id:string, char:string, label:string}[] = [
  {id:"5368324170671202286", char:"👍", label:"Thumbs up"},
  {id:"5258185631355378853", char:"⭐", label:"Star"},
  {id:"5258073068852485953", char:"✈️", label:"Paper plane"},
  {id:"5258050709252743821", char:"✉️", label:"Envelope"},
  {id:"5258105663359294787", char:"🔗", label:"Link"},
  {id:"5260730055880876557", char:"🔍", label:"Search"},
  {id:"5257974976094412956", char:"🖼️", label:"Image"},
  {id:"5258513401784573443", char:"👥", label:"Users"},
  {id:"5260726538302660868", char:"✅", label:"Check"},
  {id:"5260268501515377807", char:"💬", label:"Chat"},
  {id:"5260280853841321805", char:"🕐", label:"Clock"},
  {id:"5258260149037965799", char:"🔒", label:"Lock"},
];

export default function InboxComposer({chatId,reply,text,setText,busy,active,richText,onCancelReply,onSend}:{
 chatId:number|null;active:boolean;reply:GroupMessage|null;text:string;setText:(text:string)=>void;busy:boolean;
 richText?:boolean;onCancelReply:()=>void;onSend:(file:File|null,kind:Kind|null)=>Promise<boolean>;
}){
 const [attachment,setAttachment]=useState<{file:File;kind:Kind}|null>(null),[preview,setPreview]=useState('');
 const [error,setError]=useState(''),[recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0);
 const [showFormat,setShowFormat]=useState(false),[showEmoji,setShowEmoji]=useState(false),[showPreview,setShowPreview]=useState(false);
 const [emojiId,setEmojiId]=useState(''),[emojiChar,setEmojiChar]=useState('✨');
 const [linkOpen,setLinkOpen]=useState(false),[linkUrl,setLinkUrl]=useState('');
 const requesting=useRef(false),attachmentsMenu=useRef<HTMLDetailsElement>(null),textarea=useRef<HTMLTextAreaElement>(null);
 useEffect(()=>{const node=textarea.current;if(node){node.style.height='auto';node.style.height=`${Math.max(44,Math.min(node.scrollHeight,160))}px`;}},[text]);
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

 function applyFormat(open:string, close:string){
  const el=textarea.current; if(!el) return;
  const start=el.selectionStart ?? text.length, end=el.selectionEnd ?? text.length;
  const res=wrapWithTag(text,start,end,open,close);
  setText(res.text);
  requestAnimationFrame(()=>{ el.focus(); el.setSelectionRange(res.selection[0], res.selection[1]); });
 }
 function formatBold(){ applyFormat('<b>','</b>'); }
 function formatItalic(){ applyFormat('<i>','</i>'); }
 function formatUnderline(){ applyFormat('<u>','</u>'); }
 function formatStrike(){ applyFormat('<s>','</s>'); }
 function formatMono(){ applyFormat('<code>','</code>'); }
 function formatSpoiler(){ applyFormat('<tg-spoiler>','</tg-spoiler>'); }
 function formatQuote(){ applyFormat('<blockquote>','</blockquote>'); }
 function formatLink(){
  if(linkOpen){ setLinkOpen(false); return; }
  const el=textarea.current; const start=el?.selectionStart ?? 0, end=el?.selectionEnd ?? 0;
  const selected=text.slice(start,end);
  if(selected && safeLink(selected)){ setLinkUrl(selected); } else { setLinkUrl(''); }
  setLinkOpen(true);
 }
 function confirmLink(){
  const href=safeLink(linkUrl.trim());
  if(!href){ setError('Enter a valid https://, http:// or tg:// link.'); return; }
  const el=textarea.current; if(!el){ setError('Select text first'); return; }
  const start=el.selectionStart ?? 0, end=el.selectionEnd ?? 0;
  let res;
  if(start!==end){
   res=wrapWithTag(text,start,end,`<a href="${href}">`,'</a>');
  } else {
   const placeholder='link';
   const insert=`<a href="${href}">${placeholder}</a>`;
   res={text:text.slice(0,start)+insert+text.slice(end), selection:[start+insert.length,start+insert.length] as const};
  }
  setText(res.text); setLinkOpen(false); setError('');
  requestAnimationFrame(()=>{ el.focus(); el.setSelectionRange(res.selection[0], res.selection[1]); });
 }
 function insertEmoji(id:string, char:string){
  if(!/^[0-9]{1,20}$/.test(id)){ setError('Premium emoji ID must be 1–20 digits. Copy it from @emoji.'); return; }
  if(!char) char='✨';
  const el=textarea.current; const pos=el?.selectionStart ?? text.length;
  const tag=`<tg-emoji emoji-id="${id}">${char}</tg-emoji>`;
  const next=text.slice(0,pos)+tag+text.slice(pos);
  setText(next); setError('');
  requestAnimationFrame(()=>{ if(el){ el.focus(); const p=pos+tag.length; el.setSelectionRange(p,p); }});
 }

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
 async function send(){if(!chatId||busy||recording||!active)return;setError('');const epoch=generation.current;const ok=await onSend(attachment?.file||null,attachment?.kind||null);if(ok&&epoch===generation.current){setAttachment(null); setShowPreview(false);}}
 return <div className="tg-composer tg-composer-premium border-t border-white/[0.06] bg-[#0a0e1e]/80 backdrop-blur-2xl p-3 sm:p-4">
  {reply&&<div className="mb-3 flex justify-between gap-3 rounded-xl border-l-[3px] border-teal-400/50 bg-teal-500/[0.06] p-3"><div className="min-w-0"><p className="text-[11px] font-semibold text-teal-300">Replying as bot to {reply.sender_name}</p><p className="mt-1 truncate text-[11px] text-indigo-100/50">#{reply.message_id} · {reply.text||reply.media?.kind}</p></div><button aria-label="Cancel reply" onClick={onCancelReply} className="text-white/50 hover:text-white"><X size={14}/></button></div>}
  {attachment&&<div className="mb-3 rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10"><div className="flex items-center justify-between"><span className="truncate text-[11px] font-medium text-white/70">{attachment.kind} · {attachment.file.name} · {(attachment.file.size/1024).toFixed(0)} KB</span><button aria-label="Remove attachment" disabled={busy} onClick={()=>setAttachment(null)} className="rounded-full p-1 hover:bg-white/10"><X size={14}/></button></div>{preview&&attachment.kind==='photo'&&<img src={preview} alt="Attachment preview" className="mt-3 max-h-44 rounded-xl object-contain ring-1 ring-white/10"/>}{preview&&attachment.kind==='video'&&<video controls src={preview} className="mt-3 max-h-44 rounded-xl ring-1 ring-white/10"/>}{preview&&attachment.kind==='voice'&&<audio controls src={preview} className="mt-3 max-w-full"/>}</div>}
  {error&&<p role="alert" className="mb-3 rounded-xl bg-rose-500/10 px-3 py-2 text-xs text-rose-200 ring-1 ring-rose-500/20">{error}</p>}

  {richText===false&&<p className="mb-2 rounded-lg bg-amber-400/10 px-3 py-2 text-[10px] leading-4 text-amber-200/80 ring-1 ring-amber-400/20">Rich formatting is waiting for the updated backend to finish deploying. Until then, formatting is sent as clean plain text and switches on automatically.</p>}
  {/* Beautiful formatting toolbar */}
  <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-2xl bg-white/[0.04] p-2 ring-1 ring-white/[0.06]">
    <div className="flex items-center gap-1">
      <button type="button" title="Bold" onClick={formatBold} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><Bold size={14}/></button>
      <button type="button" title="Italic" onClick={formatItalic} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><Italic size={14}/></button>
      <button type="button" title="Underline" onClick={formatUnderline} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><UnderlineIcon size={14}/></button>
      <button type="button" title="Strikethrough" onClick={formatStrike} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><Strikethrough size={14}/></button>
    </div>
    <span className="h-6 w-px bg-white/10 mx-1" />
    <div className="flex items-center gap-1">
      <button type="button" title="Monospace" onClick={formatMono} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><Code2 size={14}/></button>
      <button type="button" title="Spoiler" onClick={formatSpoiler} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><EyeOff size={14}/></button>
      <button type="button" title="Quote" onClick={formatQuote} className="rounded-xl bg-white/5 p-2.5 text-white/70 hover:bg-white/10 hover:text-white transition"><Quote size={14}/></button>
      <button type="button" title="Link" onClick={formatLink} className={`rounded-xl p-2.5 transition ${linkOpen?'bg-indigo-500 text-white':'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white'}`}><Link2 size={14}/></button>
    </div>
    <span className="h-6 w-px bg-white/10 mx-1" />
    <button type="button" onClick={()=>setShowEmoji(v=>!v)} className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition ${showEmoji?'bg-gradient-to-r from-violet-500 to-indigo-500 text-white shadow-lg':'bg-white/5 text-white/70 hover:bg-white/10'}`}><Sparkles size={14}/> Premium <ChevronDown size={12} className={showEmoji?'rotate-180':''}/></button>
    <button type="button" onClick={()=>setShowPreview(v=>!v)} className={`ml-auto flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition ${showPreview?'bg-emerald-500 text-white':'bg-white/5 text-white/70 hover:bg-white/10'}`}><Eye size={14}/> Preview</button>
  </div>

  {linkOpen&&<div className="mb-3 rounded-2xl bg-indigo-500/10 p-3 ring-1 ring-indigo-500/20"><p className="text-[11px] font-semibold text-indigo-200">Add a link to selected text</p><div className="mt-2 flex gap-2"><input autoFocus value={linkUrl} onChange={e=>setLinkUrl(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();confirmLink();} if(e.key==='Escape') setLinkOpen(false);}} placeholder="https://example.com" className="ios-input flex-1 text-xs"/><button onClick={confirmLink} className="ios-btn ios-btn-primary text-xs !py-2">Apply</button><button onClick={()=>setLinkOpen(false)} className="ios-btn ios-btn-glass text-xs !py-2">Cancel</button></div><p className="mt-2 text-[10px] text-indigo-200/60">Select text first, then paste URL. Supports https, http, tg://</p></div>}

  {showEmoji&&<div className="mb-3 rounded-2xl bg-gradient-to-br from-violet-500/10 via-indigo-500/10 to-fuchsia-500/10 p-4 ring-1 ring-violet-500/20 backdrop-blur">
    <div className="flex items-center justify-between"><h4 className="flex items-center gap-2 text-xs font-bold tracking-widest text-violet-200"><Smile size={14}/> PREMIUM EMOJI STUDIO</h4><button onClick={()=>setShowEmoji(false)} className="rounded-full p-1 hover:bg-white/10"><X size={14}/></button></div>
    <p className="mt-2 text-[11px] leading-5 text-white/60">Tap a real custom emoji or paste any <b>emoji ID</b> copied from Telegram. Sent as <code className="rounded bg-white/10 px-1">&lt;tg-emoji&gt;</code> with your character as the fallback. Your bot must be eligible to send custom emoji (Fragment username, or the bot owner has Telegram Premium on Bot API 9.4+), otherwise Telegram rejects the message.</p>
    <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-6">{PREMIUM_PRESETS.map(p=><button key={p.id} onClick={()=>insertEmoji(p.id,p.char)} title={`${p.label} ${p.id}`} className="rounded-2xl bg-white/5 p-3 text-center hover:bg-white/10 transition ring-1 ring-white/5"><span className="block text-lg">{p.char}</span><span className="mt-1 block truncate text-[9px] text-white/50">{p.label}</span></button>)}</div>
    <div className="mt-4 rounded-xl bg-black/20 p-3 ring-1 ring-white/5"><p className="text-[10px] font-semibold tracking-widest text-white/50">CUSTOM EMOJI ID</p><div className="mt-2 flex gap-2"><input value={emojiId} onChange={e=>setEmojiId(e.target.value.replace(/[^0-9]/g,''))} placeholder="e.g. 5368324170671202286" className="ios-input flex-1 text-xs font-mono" maxLength={20}/><input value={emojiChar} onChange={e=>setEmojiChar(e.target.value.slice(0,2))} placeholder="✨" className="ios-input w-20 text-center text-xs" maxLength={4}/><button onClick={()=>{if(emojiId) insertEmoji(emojiId, emojiChar||'✨');}} disabled={!emojiId} className="ios-btn ios-btn-primary text-xs disabled:opacity-40 !px-4"><Wand2 size={14}/> Insert</button></div><p className="mt-2 text-[10px] text-white/40">Get an ID by forwarding the emoji to a helper bot, or from Telegram Web’s customEmojiId. IDs are 1–20 digits. <a href="https://core.telegram.org/bots/api#html-style" target="_blank" rel="noreferrer" className="underline">Bot API reference</a></p></div>
  </div>}

  {showPreview&&text&&<div className="mb-3 rounded-2xl bg-[#0e1621] p-4 ring-1 ring-white/10"><p className="mb-2 text-[10px] font-bold tracking-widest text-white/40">TELEGRAM PREVIEW</p><div className="telegram-rich text-sm leading-6 text-white/90 prose prose-invert max-w-none" dangerouslySetInnerHTML={{__html: previewHtml(text)}} /></div>}

  <div className="tg-compose-row flex items-end gap-2 rounded-[22px] bg-white/[0.06] p-2 ring-1 ring-white/10 backdrop-blur">
   <details ref={attachmentsMenu} className="tg-attachment-menu shrink-0"><summary aria-label="Attach media" title="Attach photo, video or voice" className="grid h-11 w-11 place-items-center rounded-full bg-white/5 text-white/70 hover:bg-white/10 transition"><Paperclip size={18}/></summary><div className="tg-attachment-options" role="group" aria-label="Attachment types">   <button aria-label="Attach photo" title="Photo" disabled={!chatId||busy||recording} onClick={()=>choose('photo')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><ImagePlus size={16}/></button>
   <button aria-label="Attach video" title="MP4 video" disabled={!chatId||busy||recording} onClick={()=>choose('video')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><Video size={16}/></button>
   <button aria-label="Upload voice message" title="Upload voice" disabled={!chatId||busy||recording} onClick={()=>choose('voice')} className="ios-btn ios-btn-glass !p-2.5 rounded-full"><Paperclip size={16}/></button>
</div></details>
   <textarea ref={textarea} onKeyDown={event=>{
     const mod=event.ctrlKey||event.metaKey;
     if(mod&&!event.altKey&&!event.nativeEvent.isComposing){
       const key=event.key.toLowerCase();
       if(key==='b'){event.preventDefault();formatBold();return;}
       if(key==='i'){event.preventDefault();formatItalic();return;}
       if(key==='u'){event.preventDefault();formatUnderline();return;}
       if(key==='d'){event.preventDefault();formatStrike();return;}
       if(event.key==='Enter'&&!busy&&!recording&&chatId&&(text.trim()||attachment)&&plainLen<=limit){event.preventDefault();void send();return;}
     }
   }} aria-label="Message as bot" value={text} onChange={event=>setText(event.target.value)} disabled={!chatId||busy||recording} rows={1} className="ios-input flex-1 resize-none border-0 bg-transparent text-sm placeholder:text-white/30 focus:ring-0" placeholder={attachment?'Add an optional caption… (supports formatting)':'Message…  select text to format ✨'}/>
   <button aria-label={recording?'Stop recording':'Record voice message'} onClick={()=>recording?recorder.current?.stop():void record()} disabled={!chatId||busy} className={`grid h-11 w-11 place-items-center rounded-full transition shrink-0 ${recording?'bg-rose-500 text-white animate-pulse':'bg-white/5 text-white/70 hover:bg-white/10'}`}><span className="sr-only">Mic</span>{recording?<Square size={16}/>:<Mic size={16}/>}</button>
<button disabled={busy||!chatId||recording||(!text.trim()&&!attachment)||isOverLimit} onClick={()=>void send()} aria-label="Send as bot" title="Send as bot" className="tg-send ios-btn ios-btn-primary grid h-11 w-11 place-items-center rounded-full p-0 shadow-lg disabled:opacity-40 shrink-0">{busy?<LoaderCircle size={16} className="animate-spin"/>:<Send size={16}/>}<span className="sr-only">Send as bot</span></button></div>
  <input ref={input} type="file" hidden onChange={event=>{const file=event.target.files?.[0];if(file){if(file.size>4*1024*1024)setError('Uploads are limited to 4 MB. Use a smaller photo or short MP4 clip.');else{setAttachment({file,kind:pickKind.current});setError('');}}event.target.value='';}}/>
  {recording&&<p role="status" className="mt-3 flex items-center gap-2 rounded-full bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-200 ring-1 ring-rose-500/20"><span className="h-2 w-2 animate-pulse rounded-full bg-rose-400"/> Recording {seconds}s / 120s · Tap stop to preview before sending</p>}
  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px]">
    <span className={`font-mono ${isOverLimit?'text-rose-300 font-bold':'text-white/30'}`}>{plainLen}/{limit} {isOverLimit?'· too long':''} · Rich formatting & premium emoji supported</span>
    <span className="text-white/20 hidden sm:inline">Ctrl+Enter to send · Select text + toolbar to style</span>
  </div>
 </div>;
}
