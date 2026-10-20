"use client";
import {useEffect,useRef,useState} from 'react';
import {Bookmark,Pin,RefreshCw,Tag,NotebookPen,MessageSquareText,X} from 'lucide-react';
import {tagsFromInput} from '@/lib/inbox-workspace';
import type {QuickReply} from '@/lib/inbox-workspace';
import type {InboxWorkspaceState} from './useInboxWorkspace';

export default function InboxWorkspace({workspace,text,setText}:{workspace:InboxWorkspaceState;text:string;setText:(value:string)=>void}){
 const {chat,busy,save}=workspace;
 const [notes,setNotes]=useState(''),[tags,setTags]=useState(''),[title,setTitle]=useState(''),[body,setBody]=useState('');
 const [editing,setEditing]=useState<QuickReply|null>(null),[find,setFind]=useState('');
 const notesDirty=useRef(false),tagsDirty=useRef(false),cid=chat?.chat_id;
 useEffect(()=>{notesDirty.current=false;tagsDirty.current=false;setNotes(chat?.notes||'');setTags(chat?.tags.join(', ')||'');},[cid]);
 useEffect(()=>{if(!notesDirty.current)setNotes(chat?.notes||'');if(!tagsDirty.current)setTags(chat?.tags.join(', ')||'');},[chat]);
 const useReply=(value:string)=>{if(!text||text===value||window.confirm('Replace the current composer text? Nothing will be sent automatically.'))setText(value);};
 async function saveReply(){
  const ok=await save({action:'save_reply',id:editing?.id||crypto.randomUUID(),revision:editing?.revision||0,title,text:body});
  if(ok){setEditing(null);setTitle('');setBody('');}
 }
 return <section className="ios-card p-4" aria-label="Advanced inbox workspace">
  <div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><Bookmark size={16}/>Workspace tools</h2><button aria-label="Refresh workspace" disabled={busy} onClick={workspace.refresh}><RefreshCw size={14}/></button></div>
  <p className="mt-2 text-[10px] leading-5 text-indigo-100/40">Private owner tools · saved in MongoDB · never sent automatically.</p>
  {workspace.error&&<p role="alert" className="mt-3 text-[11px] leading-5 text-rose-200">{workspace.error}</p>}
  {workspace.notice&&<p role="status" className="mt-3 text-[11px] leading-5 text-teal-200">{workspace.notice}</p>}
  {chat&&<>
   <button aria-label={chat.pinned?'Unpin conversation in workspace':'Pin conversation in workspace'} disabled={busy} onClick={()=>void save({action:'organize',pinned:!chat.pinned,tags:chat.tags,revision:chat.revisions.organize})} className="ios-btn ios-btn-glass mt-4 w-full text-[11px]"><Pin size={13}/>{chat.pinned?'Pinned conversation':'Pin conversation'}</button>
   <div className="mt-4 border-t border-white/5 pt-4"><h3 className="flex items-center gap-2 text-xs font-medium"><MessageSquareText size={13}/>Chat draft</h3><p className="mt-2 text-[10px] leading-5 text-indigo-100/45">Save composer text explicitly, then restore it on another device. Attachments and microphone recordings are not saved.</p>
    <div className="mt-3 flex flex-wrap gap-2"><button disabled={busy||text.length>4096} onClick={()=>void save({action:'draft',value:text,revision:chat.revisions.draft})} className="ios-btn ios-btn-glass !p-2 text-[10px]">Save draft</button><button disabled={busy||!chat.draft} onClick={()=>useReply(chat.draft)} className="ios-btn ios-btn-glass !p-2 text-[10px]">Restore draft</button><button disabled={busy||!chat.draft} onClick={()=>void save({action:'draft',value:'',revision:chat.revisions.draft})} className="ios-btn ios-btn-glass !p-2 text-[10px]">Clear saved draft</button></div><p className="mt-2 text-[9px] text-indigo-100/35">{chat.draft.length} saved text units · explicit save, not auto-save</p>
   </div>
   <label className="mt-4 block text-[11px] text-indigo-100/60"><span className="flex items-center gap-2"><Tag size={12}/>Conversation tags</span><input aria-label="Conversation tags" value={tags} onChange={e=>{tagsDirty.current=true;setTags(e.target.value);}} className="ios-input mt-2 text-xs" placeholder="support, priority" maxLength={110}/></label>
   <button disabled={busy||tagsFromInput(tags).length>5||tagsFromInput(tags).some(tag=>tag.length>20)} onClick={async()=>{if(await save({action:'organize',pinned:chat.pinned,tags:tagsFromInput(tags),revision:chat.revisions.organize}))tagsDirty.current=false;}} className="mt-2 text-[10px] text-indigo-200 underline">Save tags · up to 5</button>
   <label className="mt-4 block text-[11px] text-indigo-100/60"><span className="flex items-center gap-2"><NotebookPen size={12}/>Private owner notes</span><textarea aria-label="Private conversation notes" value={notes} onChange={e=>{notesDirty.current=true;setNotes(e.target.value);}} rows={3} maxLength={2000} className="ios-input mt-2 resize-y text-xs" placeholder="Context for your next visit…"/></label>
   <button disabled={busy} onClick={async()=>{if(await save({action:'notes',value:notes,revision:chat.revisions.notes}))notesDirty.current=false;}} className="mt-2 text-[10px] text-indigo-200 underline">Save notes · {notes.length}/2000</button>
  </>}
  <div className="mt-5 border-t border-white/5 pt-4"><div className="flex items-center justify-between"><h3 className="text-xs font-semibold">Saved replies</h3><span className="text-[9px] text-indigo-100/35">{workspace.replies.length}/50</span></div>
   <input aria-label="Find saved replies" value={find} onChange={e=>setFind(e.target.value)} className="ios-input mt-3 text-xs" placeholder="Find a saved reply…"/>
   <div className="mt-2 max-h-44 space-y-2 overflow-auto">{workspace.replies.filter(item=>`${item.title} ${item.text}`.toLowerCase().includes(find.toLowerCase())).map(item=><div key={item.id} className="rounded-xl bg-white/5 p-3"><p className="truncate text-[11px] font-medium">{item.title}</p><p className="mt-1 line-clamp-2 whitespace-pre-wrap break-words text-[10px] text-indigo-100/40">{item.text}</p><div className="mt-2 flex gap-3 text-[10px] text-indigo-200"><button disabled={!chat||busy} onClick={()=>useReply(item.text)}>Use</button><button disabled={busy} onClick={()=>{setEditing(item);setTitle(item.title);setBody(item.text);}}>Edit</button><button disabled={busy} onClick={()=>{if(window.confirm(`Delete saved reply “${item.title}”?`))void save({action:'delete_reply',id:item.id,revision:item.revision});}}>Delete</button></div></div>)}</div>
   {!workspace.replies.length&&<p className="mt-2 text-[10px] leading-5 text-indigo-100/40">Add your own replies below. No AI or demo replies.</p>}
   <div className="mt-3 flex items-center justify-between"><span className="text-[10px] text-indigo-100/50">{editing?'Edit saved reply':'New saved reply'}</span>{editing&&<button aria-label="Cancel saved reply edit" onClick={()=>{setEditing(null);setTitle('');setBody('');}}><X size={12}/></button>}</div>
   <input aria-label="Saved reply title" value={title} maxLength={60} onChange={e=>setTitle(e.target.value)} className="ios-input mt-2 text-xs" placeholder="Reply title"/>
   <textarea aria-label="Saved reply text" value={body} maxLength={4096} onChange={e=>setBody(e.target.value)} className="ios-input mt-2 resize-y text-xs" rows={3} placeholder="Write reusable plain text…"/>
   <button disabled={busy||!title.trim()||!body.trim()} onClick={()=>void saveReply()} className="ios-btn ios-btn-glass mt-2 w-full text-[10px]">{editing?'Update saved reply':'Create saved reply'}</button>
  </div>
 </section>;
}
