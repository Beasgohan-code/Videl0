export type GroupMessage = {
  chat_id: number; message_id: number; text: string; local_preview?: string; ephemeral?: boolean;
  sender_id: number | null; sender_is_user: boolean; sender_name: string;
  sender_username: string; is_bot: boolean; date: string; edited: boolean; deleted: boolean;
  reply_to_id: number | null; thread_id: number | null;
  media: {kind: string; name: string} | null;
  rich?: boolean;
  bot_reaction?: string | null;
  poll?: {question: string; options: string[]; anonymous: boolean; multiple: boolean} | null;
};
export type GroupSnapshot = {
  chat_id: number; items: GroupMessage[]; has_more: boolean; next_before: number | null;
  is_private?: boolean; recording: boolean; retention_days: number; capture_dropped: number;
  rich_text?: boolean;
  visibility_note: string; settings: Record<string, boolean>;
};
export const protections = [
  ["lock_links", "Block links"], ["lock_media", "Block media"],
  ["lock_stickers", "Block stickers"], ["lock_forwards", "Block forwards"],
  ["lock_polls", "Block polls"], ["lock_mentions", "Block mentions"],
  ["antispam", "Anti-flood"], ["welcome_enabled", "Welcome messages"],
] as const;
export function telegramMessageLink(chatId: number, messageId: number) {
  const value = String(chatId);
  return /^-100\d+$/.test(value) && Number.isSafeInteger(messageId) && messageId > 0
    ? `https://t.me/c/${value.slice(4)}/${messageId}` : null;
}
export function textUnits(text: string) { return text.length; }
export function groupId(value: string): number | null {
  if (!/^-\d+$/.test(value)) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number < 0 ? number : null;
}

export function conversationId(value:string):number|null{
 if(!/^-?[0-9]+$/.test(value))return null;
 const id=Number(value);return Number.isSafeInteger(id)&&id!==0?id:null;
}

/** True when a stored message contains Telegram-supported formatting markup. */
export function hasRichMarkup(text: string | null | undefined) {
  return /<\/?(?:b|i|u|s|code|pre|blockquote|a|tg-spoiler|tg-emoji)\b/.test(text || "");
}
