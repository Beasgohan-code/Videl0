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
  const buttons: BtnRow[] = [];
  if (Array.isArray(d.buttons))
    for (const row of d.buttons.slice(0, 8)) {
      if (!Array.isArray(row)) continue;
      const clean = row
        .filter(
          (b) =>
            b &&
            typeof b.text === "string" &&
            b.text.length <= 64 &&
            typeof b.url === "string" &&
            /^https?:\/\//i.test(b.url) &&
            b.url.length <= 2048,
        )
        .slice(0, 8)
        .map((b) => ({ text: b.text, url: b.url }));
      if (clean.length) buttons.push(clean);
    }
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
