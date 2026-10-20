"use client";
import {useCallback, useEffect, useLayoutEffect, useRef, useState} from "react";
import {ArrowLeft, ArrowDown, Check, MessageCircle, Search, Send, ShieldCheck, RefreshCw, Reply, X, MoreHorizontal, ExternalLink, Copy, Eye, Pause, Users, Settings2, AlertTriangle, LoaderCircle} from "lucide-react";
import {sentByThisBot} from "@/lib/chat-messenger";
import InboxWorkspace from "./InboxWorkspace";
import {useInboxWorkspace} from "./useInboxWorkspace";
import {orderConversations,loadedNewMessages} from "@/lib/inbox-workspace";
import InboxComposer from "./InboxComposer";
import {useStudio} from "./StudioProvider";
import {GroupMessage, GroupSnapshot, protections, telegramMessageLink, textUnits, conversationId} from "@/lib/group-view";
import {chatPreviewHtml, plainPostText} from "@/lib/telegram-format";

const DRAFT_KEY="videl_chat_drafts_v1";
type Group = {type?:string;id:number; title:string; members:number|null; available:boolean};
type Action = {action:string;text?:string;file?:File;kind?:'photo'|'video'|'voice'; message_id?:number; enabled?:boolean; retention_days?:number; settings?:Record<string,boolean>};
export default function GroupViewer() {
  const {tab,selectedGroup,selectGroup,open} = useStudio();
  const [mobileChat,setMobileChat]=useState(false),[detailsOpen,setDetailsOpen]=useState(false),[searchOpen,setSearchOpen]=useState(false);
  const [isMobile,setIsMobile]=useState(false),[showJump,setShowJump]=useState(false),[groupsLoading,setGroupsLoading]=useState(true);
  const messageList=useRef<HTMLDivElement>(null),stickToBottom=useRef(true),scrollChat=useRef<number|null>(null);
  const restoreScroll=useRef<{height:number;top:number}|null>(null);
  const [recent,setRecent]=useState<Record<number,{text:string;date:string}>>({});
  const [drafts,setDrafts]=useState<Record<string,string>>({});
  const draftChat=useRef<number|null>(null);
  useEffect(()=>{try{const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||"{}");if(saved&&typeof saved==="object"&&!Array.isArray(saved))setDrafts(saved);}catch{}},[]);
  useEffect(()=>{const query=window.matchMedia('(max-width: 767px)');const update=()=>setIsMobile(query.matches);update();query.addEventListener('change',update);return()=>query.removeEventListener('change',update);},[]);
  useEffect(()=>{if(selectedGroup)setMobileChat(true);setDetailsOpen(false);setSearchOpen(false);stickToBottom.current=true;scrollChat.current=null;restoreScroll.current=null;setShowJump(false);},[selectedGroup]);
  const [receipts,setReceipts]=useState<GroupMessage[]>([]);
  const localUrls=useRef(new Set<string>());
  const [groups,setGroups] = useState<Group[]>([]), [groupSearch,setGroupSearch] = useState("");
  const [manualId,setManualId] = useState(""), [groupsError,setGroupsError] = useState("");
  const [search,setSearch] = useState(""), [sender,setSender] = useState<number|null>(null);
  const [snapshot,setSnapshot] = useState<GroupSnapshot|null>(null);
  const [loading,setLoading] = useState(false), [error,setError] = useState("");
  const [notice,setNotice] = useState(""), [busy,setBusy] = useState(false);
  const [selected,setSelected] = useState<GroupMessage|null>(null), [reply,setReply] = useState<GroupMessage|null>(null);
  const [text,setText] = useState(""), [older,setOlder] = useState(false), [updated,setUpdated] = useState("");
  const [refresh,setRefresh] = useState(0), [confirm,setConfirm] = useState<Action|null>(null), [days,setDays] = useState(7);
  const viewKey=useRef('');viewKey.current=`${selectedGroup}:${search}:${sender}`;
  const activeId = useRef(selectedGroup), mutation = useRef(false);
  activeId.current=selectedGroup;
  const data = snapshot?.chat_id === selectedGroup ? snapshot : null;
  const workspace=useInboxWorkspace(data?.chat_id||null,tab==='chat');
  const [folder,setFolder]=useState<'all'|'private'|'groups'|'pinned'>('all');
  const group = groups.find(item=>item.id===selectedGroup);
  const chosen = selected?.chat_id === selectedGroup ? selected : null;
  const replying = reply?.chat_id === selectedGroup ? reply : null;

  const loadGroups = useCallback(async()=>{
    setGroupsError("");
    try {
      const response=await fetch('/api/conversations',{cache:'no-store',signal:AbortSignal.timeout(15000)}), body=await response.json();
      if(!response.ok || !body.ok) throw new Error(body.error || 'Groups could not be loaded.');
      const rows=body.chats || [];
      setGroups(rows);
      if(body.truncated) setGroupsError('First 25 served groups shown. You can also open a known group by its numeric ID.');
    } catch(e) {setGroupsError(e instanceof Error?e.message:'Groups unavailable.');} finally {setGroupsLoading(false);}
  },[]);
  useEffect(()=>{if(tab!=='chat')return;void loadGroups();const timer=setInterval(()=>{if(document.visibilityState==='visible')void loadGroups();},15000);return()=>clearInterval(timer);},[loadGroups,tab]);
  useEffect(()=>()=>{localUrls.current.forEach(url=>URL.revokeObjectURL(url));localUrls.current.clear();},[]);
  useEffect(()=>{
    setReceipts([]);localUrls.current.forEach(url=>URL.revokeObjectURL(url));localUrls.current.clear();
    setSelected(null);setReply(null);setSearch('');setSender(null);setOlder(false);setNotice('');setError('');setConfirm(null);
    draftChat.current=selectedGroup??null;
    let saved='';
    try{const all=JSON.parse(localStorage.getItem(DRAFT_KEY)||'{}');saved=typeof all[String(selectedGroup)]==='string'?all[String(selectedGroup)]:'';}catch{}
    setText(saved);
  },[selectedGroup]);
  useEffect(()=>{
    if(!selectedGroup||draftChat.current!==selectedGroup)return;
    const cid=String(selectedGroup);
    const timer=setTimeout(()=>{
      setDrafts(current=>{
        const next={...current};
        if(text.trim())next[cid]=text;else delete next[cid];
        const entries=Object.entries(next).slice(-40);
        const bounded=Object.fromEntries(entries);
        try{localStorage.setItem(DRAFT_KEY,JSON.stringify(bounded));}catch{}
        return bounded;
      });
    },350);
    return ()=>clearTimeout(timer);
  },[text,selectedGroup]);
  useEffect(()=>{
    if(!selectedGroup || tab!=='chat')return;
    const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    const cid=selectedGroup;
    async function poll(){
      if(document.visibilityState==='hidden') {timer=setTimeout(poll,6000);return;}
      setLoading(true);
      try {
        const params=new URLSearchParams({chat_id:String(cid),q:search});
        if(sender)params.set('sender',String(sender));
        const response=await fetch(`/api/group-view?${params}`,{cache:'no-store',signal:controller.signal});
        const body=await response.json();
        if(!response.ok || !body.ok) {if([401,403].includes(response.status)&&!controller.signal.aborted){setSnapshot(null);setSelected(null);setReply(null);}throw new Error(body.error || 'Group messages unavailable.');}
        if(!controller.signal.aborted){
          setSnapshot(body);setError('');
          setUpdated(new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}));
        }
      } catch(e) {if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Messages unavailable.');}
      finally {if(!controller.signal.aborted){setLoading(false);if(!older)timer=setTimeout(poll,6000);}}
    }
    if(!older)timer=setTimeout(poll,300);
    return()=>{controller.abort();clearTimeout(timer);};
  },[selectedGroup,search,sender,refresh,tab,older]);

  async function loadOlder(){
    if(!selectedGroup || !data?.next_before || loading)return;
    const key=viewKey.current;
    const cid=selectedGroup, params=new URLSearchParams({chat_id:String(cid),before:String(data.next_before),q:search});
    if(sender)params.set('sender',String(sender));
    setOlder(true);setLoading(true);
    try {
      const response=await fetch(`/api/group-view?${params}`,{cache:'no-store',signal:AbortSignal.timeout(20000)}), body=await response.json();
      if(!response.ok || !body.ok)throw new Error(body.error || 'Older messages unavailable.');
      if(activeId.current===cid&&viewKey.current===key){if(messageList.current)restoreScroll.current={height:messageList.current.scrollHeight,top:messageList.current.scrollTop};setSnapshot(current=>current?.chat_id===cid?{...body,items:[...body.items,...current.items].slice(-250)}:current);}
    } catch(e){if(activeId.current===cid)setError(e instanceof Error?e.message:'Older messages unavailable.');}
    finally{setLoading(false);}
  }
  async function act(action:Action):Promise<boolean>{
    if(mutation.current || !selectedGroup)return false;
    const cid=selectedGroup;
    mutation.current=true;setBusy(true);setError('');setNotice('');setConfirm(null);
    try {
      let response:Response;
      if(action.file){
        const form=new FormData();form.set('chat_id',String(cid));form.set('kind',action.kind!);form.set('file',action.file);
        form.set('text',text);form.set('request_id',crypto.randomUUID());if(action.message_id)form.set('message_id',String(action.message_id));
        response=await fetch('/api/inbox-media',{method:'POST',body:form,signal:AbortSignal.timeout(65000)});
      }else{
        response=await fetch('/api/group-view',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({chat_id:cid,...action,...(['send','reply'].includes(action.action)?{text}:{}),request_id:crypto.randomUUID()}),signal:AbortSignal.timeout(60000)});
      }
      const body=await response.json();
      if(!response.ok || !body.ok)throw new Error(body.error || 'Action not confirmed. Check Telegram before retrying.');
      if(activeId.current===cid){
        setNotice(body.warning || (['send','reply','attachment'].includes(action.action)?'':action.action==='purge_history'?'Saved history cleared and recording paused. Telegram messages were not deleted.':'Group action confirmed.'));
        if(['send','reply','attachment'].includes(action.action)){
          stickToBottom.current=true;setShowJump(false);
          if(body.message_id){
            const url=action.file?URL.createObjectURL(action.file):undefined;if(url)localUrls.current.add(url);
            setReceipts(current=>[...current,{chat_id:cid,message_id:body.message_id,text,sender_id:null,
              sender_is_user:true,sender_name:'Your bot',sender_username:'',is_bot:true,date:new Date().toISOString(),
              edited:false,deleted:false,reply_to_id:action.message_id||null,thread_id:replying?.thread_id||null,
              media:action.file?{kind:action.kind!,name:action.file.name}:null,local_preview:url,ephemeral:true}].slice(-50));
          }
          setText('');setReply(null);
        }
        if(action.action==='delete')setSelected(null);
        setOlder(false);setRefresh(value=>value+1);
      }
      return true;
    } catch(e){if(activeId.current===cid)setError(e instanceof Error?e.message:'Action unconfirmed. Check Telegram before retrying.');return false;}
    finally{mutation.current=false;setBusy(false);}
  }
  useEffect(()=>{if(data)setDays(data.retention_days);},[selectedGroup,data?.retention_days]);
  const changeSearch=(value:string)=>{setSearch(value);setOlder(false);};
  const displayMessages=data?[...data.items,...receipts.filter(item=>item.chat_id===selectedGroup&&!data.items.some(saved=>saved.message_id===item.message_id)&&(!search||item.text.toLowerCase().includes(search.toLowerCase()))&&!sender)].sort((a,b)=>a.message_id-b.message_id):[];
  useLayoutEffect(()=>{
    const node=messageList.current;if(!node||!data||!mobileChat&&isMobile)return;
    if(restoreScroll.current){const previous=restoreScroll.current;node.scrollTop=previous.top+node.scrollHeight-previous.height;restoreScroll.current=null;}
    else if(scrollChat.current!==data.chat_id||stickToBottom.current){node.scrollTop=node.scrollHeight;stickToBottom.current=true;setShowJump(false);}
    scrollChat.current=data.chat_id;
  },[data,receipts,mobileChat,isMobile]);
  useEffect(()=>{
    if(!data||older||search||sender)return;
    const last=[...data.items,...receipts.filter(row=>row.chat_id===data.chat_id)].sort((a,b)=>a.message_id-b.message_id).at(-1);
    if(!last)return;
    const preview={text:last.deleted?'Message deleted':plainPostText(last.text||'')||last.media?.kind||'Message',date:last.date};
    setRecent(previous=>previous[data.chat_id]?.text===preview.text&&previous[data.chat_id]?.date===preview.date?previous:{...previous,[data.chat_id]:preview});
  },[data,receipts,older,search,sender]);
  const contextLink=chosen?telegramMessageLink(chosen.chat_id,chosen.message_id):null;
  const outgoing=(message:GroupMessage)=>sentByThisBot(message,process.env.NEXT_PUBLIC_BOT_USERNAME||'Videl0Bot');
  const avatarPalette=['linear-gradient(135deg,#6366f1,#22d3ee)','linear-gradient(135deg,#f472b6,#8b5cf6)','linear-gradient(135deg,#f59e0b,#ef4444)','linear-gradient(135deg,#10b981,#3b82f6)','linear-gradient(135deg,#06b6d4,#6366f1)','linear-gradient(135deg,#a855f7,#ec4899)','linear-gradient(135deg,#14b8a6,#84cc16)','linear-gradient(135deg,#fb7185,#fbbf24)'];
  const clock=(value:string)=>new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
  const day=(value:string)=>new Date(value).toLocaleDateString([], {month:'long',day:'numeric',year:'numeric'});
  const visibleGroups=orderConversations(groups.filter(item=>{
    const meta=workspace.conversations.find(row=>row.chat_id===item.id);
    return (folder==='all'||(folder==='private'&&item.id>0)||(folder==='groups'&&item.id<0)||(folder==='pinned'&&meta?.pinned))&&`${item.title} ${item.id} ${(meta?.tags||[]).join(' ')}`.toLowerCase().includes(groupSearch.toLowerCase());
  }),workspace.conversations).sort((a,b)=>Number(!!workspace.conversations.find(row=>row.chat_id===b.id)?.pinned)-Number(!!workspace.conversations.find(row=>row.chat_id===a.id)?.pinned)||(Date.parse(recent[b.id]?.date||'')||0)-(Date.parse(recent[a.id]?.date||'')||0));
  const reviewed=workspace.chat?.last_reviewed_message_id||0;
  const newCount=loadedNewMessages(data?.items||[],reviewed);
  const latestIncoming=Math.max(0,...(data?.items||[]).filter(item=>!item.is_bot&&!item.deleted).map(item=>item.message_id));
  return <main className={`tg-inbox ${mobileChat?'tg-conversation-open':''}`}>
    <h1 className="sr-only">Bot inbox</h1>
    <div className="tg-layout">
      <aside className="tg-chat-list" aria-label="Chats">
        <div className="border-b border-indigo-300/10 p-4"><div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold">Chats</h2><p className="text-[11px] text-slate-400">Your bot account</p></div><button aria-label="Refresh group list" onClick={()=>void loadGroups()}><RefreshCw size={14}/></button></div>
          <label className="mt-3 flex items-center gap-2 rounded-xl bg-white/5 px-3"><Search size={14}/><input aria-label="Search group list" value={groupSearch} onChange={e=>setGroupSearch(e.target.value)} className="min-w-0 bg-transparent py-3 text-xs outline-none" placeholder="Names, IDs or tags…"/></label>
          <div className="mt-3 flex flex-wrap gap-1" aria-label="Conversation folders">{(['all','private','groups','pinned'] as const).map(value=><button key={value} aria-pressed={folder===value} onClick={()=>setFolder(value)} className={`rounded-lg px-2 py-1.5 text-[10px] capitalize ${folder===value?'bg-indigo-400/20 text-indigo-100':'text-indigo-100/45 hover:bg-white/5'}`}>{value==='private'?'DMs':value}</button>)}</div></div>
        <div className="tg-chat-rows">{visibleGroups.map(item=><button key={item.id} disabled={busy} onClick={()=>{selectGroup(item.id);setMobileChat(true);}} className={`tg-chat-row flex w-full items-center gap-3 p-3 text-left transition disabled:opacity-40 ${selectedGroup===item.id?'bg-indigo-500/20 ring-1 ring-indigo-300/20':'hover:bg-white/5'}`}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-xs font-bold text-white/90 ring-1 ring-white/10" style={{backgroundImage:avatarPalette[Math.abs(item.id)%avatarPalette.length]}}>{item.title.slice(0,2).toUpperCase()}</span>
          <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{workspace.conversations.find(row=>row.chat_id===item.id)?.pinned?'★ ':''}{item.title}</span><span className={`mt-1 block truncate text-xs ${drafts[item.id]?'text-emerald-300/80':'text-slate-400'}`}>{drafts[item.id]?`Draft: ${plainPostText(drafts[item.id]).slice(0,80)}`:recent[item.id]?.text||(item.type==='private'?'Bot direct message':'Group conversation')}</span></span>{recent[item.id]&&<time className="self-start pt-1 text-[10px] text-slate-400">{clock(recent[item.id].date)}</time>}</button>)}
          {groupsLoading&&<div role="status" className="space-y-4 p-4" aria-label="Loading conversations">{[1,2,3,4].map(n=><div key={n} className="flex gap-3 animate-pulse"><span className="h-11 w-11 rounded-full bg-white/10"/><span className="flex-1 space-y-2 py-1"><span className="block h-3 w-2/3 rounded bg-white/10"/><span className="block h-3 w-4/5 rounded bg-white/5"/></span></div>)}</div>}
          {!groupsLoading&&!visibleGroups.length&&<p className="p-4 text-xs text-indigo-100/40">No conversations yet. Ask someone to message your bot, or add it to a group. Only bot-visible chats appear here.</p>}</div>
        {groupsError&&<p className="px-4 pb-3 text-[11px] text-amber-200/70">{groupsError}</p>}
        <details className="tg-open-id"><summary>Open chat by ID</summary><form onSubmit={e=>{e.preventDefault();const id=conversationId(manualId);if(id){selectGroup(id);setMobileChat(true);}else setGroupsError('Enter a numeric conversation ID already known to the bot.');}} className="border-t border-white/5 p-4"><label className="text-[11px] text-indigo-100/45" htmlFor="known-group">Open a known chat by ID</label><div className="mt-2 flex gap-2"><input id="known-group" value={manualId} onChange={e=>setManualId(e.target.value)} placeholder="-100…" className="ios-input min-w-0 text-xs"/><button disabled={busy} className="ios-btn ios-btn-glass !px-3 text-xs">Open</button></div></form></details>
      </aside>
      <section className="tg-conversation" aria-label="Conversation">
        <div className="tg-conversation-header"><div className="flex items-center justify-between gap-3"><button className="tg-mobile-back" aria-label="Back to chats" onClick={()=>{setMobileChat(false);setDetailsOpen(false);}}><ArrowLeft size={22}/></button><div className="min-w-0 flex-1"><h2 className="truncate font-semibold">{selectedGroup?(group?.title || `Group ${selectedGroup}`):'Choose a conversation'}</h2><p className="mt-1 text-[11px] text-indigo-100/40">{selectedGroup?'Sending as your bot':'Select a chat to start messaging'}{updated&&data?` · Synced ${updated}`:''}</p></div><button aria-label="Search conversation" aria-expanded={searchOpen} onClick={()=>setSearchOpen(value=>!value)} className="tg-header-button"><Search size={19}/></button><button aria-label="Chat info and settings" aria-expanded={detailsOpen} onClick={()=>setDetailsOpen(value=>!value)} className="tg-header-button"><MoreHorizontal size={21}/></button><button aria-label="Refresh messages" disabled={!selectedGroup || loading} onClick={()=>{setOlder(false);setRefresh(value=>value+1);}} className="ios-btn ios-btn-glass !p-2"><RefreshCw size={15} className={loading?'animate-spin':''}/></button></div>
          <div hidden={!searchOpen} className="mt-3 flex gap-2"><label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl bg-white/5 px-3"><Search size={14}/><input aria-label="Search recorded messages" disabled={!selectedGroup} className="min-w-0 w-full bg-transparent py-2.5 text-xs outline-none" value={search} onChange={e=>changeSearch(e.target.value)} maxLength={80} placeholder="Search recorded messages…"/></label>{sender&&<button onClick={()=>{setSender(null);setOlder(false);}} className="ios-pill text-[10px]">User {sender}<X size={12}/></button>}</div>
        </div>
        {error&&<div role="alert" className="m-3 flex gap-2 rounded-xl bg-rose-400/10 p-3 text-xs leading-5 text-rose-200"><AlertTriangle size={16} className="shrink-0"/>{error}</div>}
        {notice&&<p role="status" className="m-3 rounded-xl bg-emerald-400/10 p-3 text-xs leading-5 text-emerald-200">{notice}</p>}

        <div ref={messageList} onScroll={()=>{const node=messageList.current;if(node){stickToBottom.current=node.scrollHeight-node.scrollTop-node.clientHeight<100;setShowJump(!stickToBottom.current);}}} onLoadCapture={()=>{const node=messageList.current;if(node&&stickToBottom.current)node.scrollTop=node.scrollHeight;}} className="tg-messages chat-canvas space-y-2" role="log" aria-live="off" aria-label="Recorded group messages">
          {!selectedGroup?<div className="py-20 text-center"><MessageCircle size={40} className="mx-auto text-indigo-300/35"/><h3 className="mt-4 font-medium">Your messages, as your bot</h3><p className="mx-auto mt-2 max-w-xs text-xs leading-6 text-indigo-100/45">Choose a chat on the left. Read captured messages and reply with text, photos, video or voice, directly as your bot.</p></div>:!data?<div className="py-20 text-center text-xs text-indigo-100/40">{loading?<span className="inline-flex items-center gap-2"><LoaderCircle size={18} className="animate-spin"/>Loading messages…</span>:'Messages could not be loaded. Use refresh to try again.'}</div>:<>
            <p className="text-center text-[10px] text-indigo-100/35">{data.recording?'Recording enabled':'Recording paused'} · {data.retention_days}-day retention · {older?'Browsing history · refresh to return to latest':'Refreshes every 6 seconds while visible'}</p>
            {data.has_more&&data.items.length<250&&<button disabled={loading} onClick={()=>void loadOlder()} className="mx-auto block text-[11px] text-indigo-200 underline">{loading?'Loading…':'Load older messages'}</button>}
            {!data.recording&&<div className="mx-auto max-w-md rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-center"><p className="text-xs font-semibold text-amber-200">Recording is paused — new messages are not being saved</p><p className="mt-2 text-[11px] leading-5 text-amber-100/70">Enable to start capturing bot-visible messages here. A notice is posted in the chat first; old history cannot be imported.</p><button disabled={busy} onClick={()=>void act({action:'recording',enabled:true,retention_days:days})} className="ios-btn ios-btn-primary mt-3 w-full justify-center text-xs">Enable recording for this chat</button></div>}
            {displayMessages.length===0&&<div className="mx-auto max-w-sm py-16 text-center"><Eye size={30} className="mx-auto text-indigo-300/40"/><h3 className="mt-4 text-sm font-medium">{search||sender?'No matching messages':data.recording?'Waiting for new bot-visible messages':'No messages yet'}</h3><p className="mt-3 text-xs leading-6 text-indigo-100/45">{data.recording?'Send a new message in Telegram after enabling recording. Bot privacy mode may limit what appears.':'Ask someone to send a message after enabling above. You can also disable anytime via Chat info → Chat settings.'}</p>{!data.recording&&!search&&!sender&&<button disabled={busy} onClick={()=>setDetailsOpen(true)} className="mt-4 text-xs text-indigo-200 underline">Open chat settings</button>}</div>}
            {displayMessages.map((message,index)=><div key={message.message_id}>{(index===0||day(displayMessages[index-1].date)!==day(message.date))&&<div className="tg-date"><span>{day(message.date)}</span></div>}<article key={message.message_id} className={`flex ${outgoing(message)?'justify-end':'justify-start'}`}><div className={`tg-bubble max-w-[88%] min-w-[100px] rounded-2xl px-3 py-2 sm:max-w-[75%] ${outgoing(message)?'tg-outgoing rounded-br-sm':'tg-incoming rounded-bl-sm'} ${chosen?.message_id===message.message_id?'ring-1 ring-indigo-300/50':''}`}>
              <div className="flex items-center justify-between gap-3"><button className="truncate text-left text-[11px] font-semibold text-indigo-200" onClick={()=>{setSelected(message);setDetailsOpen(true);}}>{message.sender_name}{message.is_bot?' · bot':''}</button><button aria-label={`Message ${message.message_id} actions`} onClick={()=>{setSelected(message);setDetailsOpen(true);}}><MoreHorizontal size={15} className="text-indigo-100/45"/></button></div>
              {message.reply_to_id&&<div className="mt-2 border-l-2 border-indigo-300/50 pl-2 text-[10px] text-indigo-100/45">Reply to #{message.reply_to_id}{data.items.find(item=>item.message_id===message.reply_to_id)?.text?` · ${plainPostText(data.items.find(item=>item.message_id===message.reply_to_id)!.text).slice(0,80)}`:''}</div>}
              {message.media&&<div className="mt-2 rounded-lg bg-white/5 p-2 text-[11px] text-indigo-100/60"><p>{message.media.kind.replace('_',' ')}{message.media.name?` · ${message.media.name}`:''}</p>{message.media.kind==='photo'?<img loading="lazy" src={message.local_preview||`/api/inbox-media?chat_id=${message.chat_id}&message_id=${message.message_id}`} alt="Bot-visible photo" className="mt-2 max-h-64 rounded-lg object-contain"/>:['voice','audio'].includes(message.media.kind)?<audio controls preload="none" src={message.local_preview||`/api/inbox-media?chat_id=${message.chat_id}&message_id=${message.message_id}`} className="mt-2 max-w-full"/>:['video','animation'].includes(message.media.kind)?<video controls preload="none" src={message.local_preview||`/api/inbox-media?chat_id=${message.chat_id}&message_id=${message.message_id}`} className="mt-2 max-h-64 rounded-lg"/>:null}<p className="mt-1 text-[9px] text-indigo-100/35">Preview up to 8 MB. If unavailable, open the original in Telegram.</p></div>}
              {message.deleted ? (
                <p className="mt-2 text-[13px] italic text-indigo-100/30">Deleted through Videl</p>
              ) : !message.text ? null : message.is_bot ? (
                <div className="telegram-rich mt-2 break-words text-[13px] leading-6 text-indigo-50/90" dangerouslySetInnerHTML={{__html: chatPreviewHtml(message.text)}} />
              ) : (
                <p className="mt-2 whitespace-pre-wrap break-words text-[13px] leading-6 text-indigo-50/85">{message.text}</p>
              )}
              <div className="mt-2 flex items-center justify-end gap-2 text-[9px] text-indigo-100/35"><span>{message.thread_id?`Topic ${message.thread_id}`:''}</span><span>{message.edited?'edited · ':''}{clock(message.date)}</span>{message.is_bot&&message.text?.includes('<tg-emoji')&&<span title="Premium emoji" className="rounded-full bg-gradient-to-r from-violet-500/20 to-indigo-500/20 px-1.5 py-0.5 text-[8px] font-bold tracking-widest text-violet-200">PREMIUM</span>}{message.ephemeral&&<span title="Telegram confirmed delivery; not a read receipt" aria-label="Delivery confirmed"><Check size={13}/></span>}{!message.deleted&&<button aria-label={`Reply to message ${message.message_id}`} disabled={message.ephemeral} title={message.ephemeral?"Saved message actions become available after recording captures it":"Reply"} onClick={()=>{setReply(message);setSelected(message);}}><Reply size={13}/></button>}</div>
            </div></article></div>)}
          </>}
        </div>
        {showJump&&<button className="tg-jump" aria-label="Jump to latest messages" onClick={()=>{if(messageList.current)messageList.current.scrollTop=messageList.current.scrollHeight;stickToBottom.current=true;setShowJump(false);}}><ArrowDown size={20}/></button>}
        <InboxComposer active={tab==='chat'&&(!isMobile||mobileChat)} chatId={data?selectedGroup:null} reply={replying} text={text} setText={setText} busy={busy} onCancelReply={()=>setReply(null)} onSend={(file,kind)=>act({action:file?'attachment':replying?'reply':'send',...(replying?{message_id:replying.message_id}:{}),...(file&&kind?{file,kind}:{})})}/>

      </section>
      <aside hidden={!detailsOpen} className="tg-details space-y-4" aria-label="Chat info"><div className="flex items-center justify-between"><h2 className="font-semibold">Chat info</h2><button aria-label="Close chat info" onClick={()=>setDetailsOpen(false)}><X size={20}/></button></div>
        {detailsOpen&&data&&workspace.chat&&<div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 px-4 py-2"><span className="text-[10px] text-indigo-100/45">{newCount} new incoming in loaded messages · workspace marker only</span><button disabled={workspace.busy||!latestIncoming||newCount===0} onClick={()=>void workspace.save({action:'review',message_id:latestIncoming})} className="text-[10px] text-teal-200 underline disabled:opacity-40">Mark loaded messages reviewed</button></div>}
        <InboxWorkspace workspace={workspace} text={text} setText={setText}/>
        <section className="ios-card p-4"><h2 className="flex items-center gap-2 text-sm font-semibold"><Settings2 size={16}/>Chat settings</h2>
          <p className="mt-3 text-[11px] leading-5 text-indigo-100/45">Owner-only bot inbox. Group controls additionally require current group admin permissions.</p>
          {data&&<><div className="mt-4 flex items-center justify-between text-xs"><span className="flex items-center gap-2">{data.recording?<Eye size={14}/>:<Pause size={14}/>}Recording {data.recording?'on':'off'}</span><button disabled={busy} onClick={()=>setConfirm({action:'recording',enabled:!data.recording,retention_days:days})} className="ios-btn ios-btn-glass !px-3 !py-2 text-[11px]">{data.recording?'Pause':'Enable'}</button></div>
            <label className="mt-4 block text-[11px] text-indigo-100/50">Message retention<select aria-label="Message retention" value={days} onChange={e=>setDays(Number(e.target.value))} className="ios-input mt-2 text-xs"><option value={1}>1 day</option><option value={7}>7 days</option><option value={30}>30 days</option></select></label>
            {days!==data.retention_days&&<button disabled={busy} onClick={()=>setConfirm({action:'recording',enabled:data.recording,retention_days:days})} className="mt-2 text-[11px] text-indigo-200 underline">Save retention policy</button>}
            {!data.is_private&&<div className="mt-4 space-y-3 border-t border-white/5 pt-4">{protections.map(([key,label])=><label key={key} className="flex items-center justify-between gap-2 text-[11px]"><span>{label}</span><input type="checkbox" aria-label={label} disabled={busy} checked={!!data.settings[key]} onChange={e=>setConfirm({action:'protect',settings:{[key]:e.target.checked}})} className="h-4 w-4 accent-indigo-400"/></label>)}</div>}
            <button disabled={busy} onClick={()=>setConfirm({action:'purge_history'})} className="mt-5 text-[11px] text-rose-200 underline">Clear saved history & pause</button></>}
          <button onClick={()=>open('groups')} className="mt-4 block text-[11px] text-indigo-200 underline">Open full Group Manager</button>
        </section>
        {chosen&&<section className="ios-card p-4"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Message details</h2><button aria-label="Close message details" onClick={()=>setSelected(null)}><X size={14}/></button></div><p className="mt-4 break-all text-xs font-medium">{chosen.sender_name}</p><p className="mt-1 break-all text-[10px] leading-5 text-indigo-100/45">User/chat ID: {chosen.sender_id || 'Unknown'}<br/>Message ID: {chosen.message_id}<br/>{chosen.sender_username?`@${chosen.sender_username}`:''}</p>
          <div className="mt-4 grid grid-cols-2 gap-2"><button onClick={()=>void navigator.clipboard.writeText(String(chosen.message_id)).then(()=>setNotice('Message ID copied.')).catch(()=>setError('Clipboard permission was denied.'))} className="ios-btn ios-btn-glass !p-2 text-[10px]"><Copy size={12}/>Copy ID</button>{contextLink&&<a href={contextLink} target="_blank" rel="noreferrer" className="ios-btn ios-btn-glass !p-2 text-[10px]"><ExternalLink size={12}/>Telegram</a>}
            {chosen.sender_is_user&&chosen.sender_id&&chosen.sender_id>0&&<button onClick={()=>{setSender(chosen.sender_id);setOlder(false);}} className="ios-btn ios-btn-glass col-span-2 !p-2 text-[10px]">More from this sender</button>}
            {!chosen.deleted&&!chosen.ephemeral&&<><button onClick={()=>setReply(chosen)} className="ios-btn ios-btn-glass !p-2 text-[10px]">Reply</button><button disabled={busy} onClick={()=>setConfirm({action:'delete',message_id:chosen.message_id})} className="ios-btn ios-btn-glass !p-2 text-[10px] text-rose-200">Delete</button>{!data?.is_private&&['pin','unpin'].map(action=><button key={action} disabled={busy} onClick={()=>setConfirm({action,message_id:chosen.message_id})} className="ios-btn ios-btn-glass !p-2 text-[10px] capitalize">{action}</button>)}{!data?.is_private&&chosen.sender_is_user&&!chosen.is_bot&&['mute','unmute','ban'].map(action=><button key={action} disabled={busy} onClick={()=>setConfirm({action,message_id:chosen.message_id})} className="ios-btn ios-btn-glass !p-2 text-[10px] capitalize">{action==='mute'?'Mute 10 min':action}</button>)}</>}
          </div></section>}
        <p className="px-1 text-[10px] leading-5 text-indigo-100/35">{data?.visibility_note || 'Recording is opt-in for each group. Telegram history cannot be fetched by a bot.'} Group admins can use /groupview off; a DM participant can use /inbox off.{!!data?.capture_dropped&&` Capture dropped ${data.capture_dropped} messages during overload; this is not a complete archive.`}</p>
      </aside>
    </div>
    {confirm&&<div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-5 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="group-confirm-title"><div className="ios-card w-full max-w-md p-6"><h2 id="group-confirm-title" className="text-lg font-semibold">Confirm group action</h2><p className="mt-3 text-sm leading-7 text-indigo-100/65">{confirm.action==='recording'?confirm.enabled?`Enable recording with ${confirm.retention_days}-day retention? On first enable, a notice is posted in the conversation. Only future bot-visible messages are saved.`:'Pause recording? Existing snapshots expire under the selected retention policy.':confirm.action==='purge_history'?'Permanently delete this group’s saved dashboard history and pause recording? This does not delete messages in Telegram.':confirm.action==='protect'?`Update ${Object.keys(confirm.settings || {}).join(', ')} for this group? Existing approved-user/admin exemptions still apply.`:`${confirm.action==='mute'?'Mute the sender for 10 minutes':confirm.action.charAt(0).toUpperCase()+confirm.action.slice(1)} using message #${confirm.message_id} in ${group?.title || selectedGroup}? Telegram permissions will be checked before acting.`}</p><div className="mt-5 flex justify-end gap-3"><button autoFocus onClick={()=>setConfirm(null)} className="ios-btn ios-btn-glass text-xs">Cancel</button><button disabled={busy} onClick={()=>void act(confirm)} className="ios-btn ios-btn-primary text-xs">Confirm</button></div></div></div>}
  </main>;
}
