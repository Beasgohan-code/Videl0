import { parseButtons } from "./post-buttons";
import type { BtnRow } from "@/components/editor/ButtonBuilder";

export type PostDraft = {
  id: string;
  chatId: string;
  text: string;
  parseMode: "HTML" | "Markdown";
  mediaUrl: string;
  buttons: BtnRow[];
  savedAt: string;
};
export const DRAFT_KEY = "videl_channel_drafts_v1";
export const RECOVERY_KEY = "videl_post_recovery_v1";
/** Browser storage can be stale, malformed, or edited externally. */
export function parseDraft(value: unknown): PostDraft | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  if (
    typeof d.id !== "string" ||
    typeof d.text !== "string" ||
    typeof d.chatId !== "string" ||
    typeof d.savedAt !== "string" ||
    !Number.isFinite(Date.parse(d.savedAt))
  )
    return null;
  if (d.text.length > 65536 || d.chatId.length > 128) return null;
  const mediaUrl =
    typeof d.mediaUrl === "string" &&
    /^https:\/\//i.test(d.mediaUrl) &&
    d.mediaUrl.length <= 2048
      ? d.mediaUrl
      : "";
  const buttons = parseButtons(d.buttons);
  return {
    id: d.id.slice(0, 128),
    chatId: d.chatId,
    text: d.text,
    parseMode: d.parseMode === "Markdown" ? "Markdown" : "HTML",
    mediaUrl,
    buttons,
    savedAt: d.savedAt,
  };
}
export function parseDrafts(json: string): PostDraft[] {
  try {
    const data = JSON.parse(json);
    return Array.isArray(data)
      ? data
          .map(parseDraft)
          .filter((d): d is PostDraft => d !== null)
          .slice(0, 20)
      : [];
  } catch {
    return [];
  }
}

/** Portable text/button draft; local image blobs are deliberately never serialized. */
export function draftDocument(draft: PostDraft): string {
  const clean = parseDraft(draft);
  if (!clean) throw new Error("Invalid post draft");
  return JSON.stringify({format:"videl-post",version:1,draft:clean},null,2);
}
export function importDraftDocument(value: unknown): PostDraft {
  if(!value || typeof value!=="object") throw new Error("Not a Videl post document");
  const doc=value as Record<string,unknown>;
  if(doc.format!=="videl-post"||doc.version!==1)throw new Error("Unsupported post document. Use an exported Videl post JSON file.");
  const draft=parseDraft(doc.draft);
  if(!draft)throw new Error("This draft is invalid or too large.");
  return draft;
}
