"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import type {ConversationMeta,QuickReply,WorkspaceChat} from '@/lib/inbox-workspace';

export function useInboxWorkspace(chatId:number|null,active:boolean){
 const [conversations,setConversations]=useState<ConversationMeta[]>([]),[replies,setReplies]=useState<QuickReply[]>([]);
 const [detail,setDetail]=useState<WorkspaceChat|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const current=useRef(chatId),writing=useRef(false);current.current=chatId;
 const chat=detail?.chat_id===chatId?detail:null;
 const loadGlobal=useCallback(async(signal?:AbortSignal)=>{
  const response=await fetch('/api/inbox-workspace',{cache:'no-store',signal:signal||AbortSignal.timeout(15000)}),body=await response.json();
  if(!response.ok||!body.ok)throw new Error(body.error||'Workspace unavailable.');
  if(!signal?.aborted){setConversations(body.conversations||[]);setReplies(body.quick_replies||[]);}
 },[]);
 const [reload,setReload]=useState(0);
 useEffect(()=>{
  if(!active)return;const controller=new AbortController();
  setError('');setNotice('');
  void (async()=>{
   try{
    await loadGlobal(controller.signal);
    if(chatId){const response=await fetch(`/api/inbox-workspace?chat_id=${chatId}`,{cache:'no-store',signal:controller.signal}),body=await response.json();
     if(!response.ok||!body.ok)throw new Error(body.error||'Chat workspace unavailable.');
     if(!controller.signal.aborted)setDetail(body.chat||null);
    }
   }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Workspace unavailable.');}
  })();
  return()=>controller.abort();
 },[chatId,active,reload,loadGlobal]);
 async function save(action:Record<string,unknown>):Promise<boolean>{
  if(writing.current)return false;
  const cid=chatId,global=action.action==='save_reply'||action.action==='delete_reply';
  if(!global&&!chat)return false;
  writing.current=true;setBusy(true);setError('');setNotice('');
  try{
   const response=await fetch('/api/inbox-workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...action,...(!global?{chat_id:cid}:{})}),signal:AbortSignal.timeout(20000)}),body=await response.json();
   if(!response.ok||!body.ok)throw new Error(body.error||'Workspace save unconfirmed.');
   if(global){
    try{await loadGlobal();setNotice('Saved replies updated. Nothing was sent to Telegram.');}
    catch{setNotice('Save confirmed, but the saved-reply list could not refresh. Refresh workspace data before making further edits.');}
   }
   else if(current.current===cid){
    setDetail(body.chat);setConversations(items=>[...items.filter(item=>item.chat_id!==cid),{chat_id:cid!,pinned:body.chat.pinned,tags:body.chat.tags,last_reviewed_message_id:body.chat.last_reviewed_message_id}]);
    setNotice(action.action==='review'?'Marked reviewed in this workspace only.':'Saved to MongoDB. Nothing was sent to Telegram.');
   }
   return true;
  }catch(e){if(global||current.current===cid)setError(e instanceof Error?e.message:'Workspace save unconfirmed.');return false;}
  finally{writing.current=false;setBusy(false);}
 }
 return {chat,conversations,replies,busy,error,notice,save,refresh:()=>setReload(value=>value+1)};
}
export type InboxWorkspaceState=ReturnType<typeof useInboxWorkspace>;
