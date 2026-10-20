import type {GroupMessage} from './group-view';
export type ConversationMeta={chat_id:number;pinned:boolean;tags:string[];last_reviewed_message_id:number};
export type WorkspaceChat=ConversationMeta&{draft:string;notes:string;revisions:{draft:number;notes:number;organize:number}};
export type QuickReply={id:string;title:string;text:string;revision:number};
export function tagsFromInput(value:string):string[]{
 return [...new Set(value.split(',').map(tag=>tag.trim()).filter(Boolean))];
}
export function loadedNewMessages(items:GroupMessage[],reviewed:number):number{
 return items.filter(item=>!item.is_bot&&!item.deleted&&item.message_id>reviewed).length;
}
export function orderConversations<T extends {id:number;title:string}>(items:T[],metadata:ConversationMeta[]):T[]{
 const pinned=new Set(metadata.filter(item=>item.pinned).map(item=>item.chat_id));
 return [...items].sort((a,b)=>Number(pinned.has(b.id))-Number(pinned.has(a.id))||a.title.localeCompare(b.title));
}
