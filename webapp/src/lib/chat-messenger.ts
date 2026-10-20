import type {GroupMessage} from './group-view';

/** Other Telegram bots are not this bot's outgoing messages. */
export function sentByThisBot(message:GroupMessage,username:string):boolean {
  if(message.ephemeral)return true; // Created only after Telegram confirmed a local send.
  const normalized=username.replace(/^@/,'').toLowerCase();
  return !!normalized&&message.is_bot&&(message.sender_username||'').toLowerCase()===normalized;
}
