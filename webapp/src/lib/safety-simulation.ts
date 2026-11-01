import { flag, type FilterRow, type GroupSettings } from "@/lib/group-admin";

export type SampleKind =
  | "text" | "link" | "forward" | "photo" | "video" | "audio" | "voice"
  | "document" | "sticker" | "animation" | "poll" | "mention" | "contact"
  | "location" | "game" | "inline" | "bot";
export type SampleSender = "member" | "admin" | "approved";

export type SafetyPreview = {
  exemptFromLocks: boolean;
  blockedBy: string | null;
  autoReply: string | null;
};

const LOCK_LABELS: Record<string, string> = {
  links: "Links",
  mentions: "Mentions",
  forward: "Forwards",
  stickers: "Stickers",
  polls: "Polls",
  photos: "Photos",
  videos: "Videos",
  audio: "Audio",
  voice: "Voice notes",
  documents: "Documents",
  animations: "GIFs and animations",
  contacts: "Contact cards",
  locations: "Locations",
  games: "Games",
  inline: "Inline bots",
  media: "All media",
  bots: "Bot messages",
};

const LINK_RE = /(?:https?:\/\/|www\.|\bt\.me\/|\btelegram\.me\/)\S+/i;
const USERNAME_RE = /(?:^|\s)@[A-Za-z0-9_]{5,32}\b/;
const MEDIA_KINDS = new Set<SampleKind>(["photo", "video", "audio", "voice", "document", "animation"]);

/**
 * A read-only approximation of the bot's actual content-lock priority.
 * It deliberately does not simulate actions requiring live Telegram state,
 * such as anti-flood history, quiet-hours timezones, or Telegram permissions.
 */
export function simulateSafety(
  settings: GroupSettings,
  filters: FilterRow[],
  message: string,
  kind: SampleKind,
  sender: SampleSender,
): SafetyPreview {
  const exemptFromLocks = sender === "admin" || sender === "approved";
  let blockedBy: string | null = null;

  if (!exemptFromLocks) {
    const hasLink = kind === "link" || LINK_RE.test(message);
    const hasMention = kind === "mention" || USERNAME_RE.test(message);
    const isForward = kind === "forward";
    const enabled = (name: string) => flag(settings, `lock_${name}`);

    // Keep the same first-match precedence as videl.utils.moderation.locked_message_reason.
    if (enabled("links") && hasLink) blockedBy = "links";
    else if (enabled("mentions") && hasMention) blockedBy = "mentions";
    else if (enabled("forward") && isForward) blockedBy = "forward";
    else {
      const orderedKinds: [SampleKind, string][] = [
        ["sticker", "stickers"], ["poll", "polls"], ["photo", "photos"],
        ["video", "videos"], ["audio", "audio"], ["voice", "voice"],
        ["document", "documents"], ["animation", "animations"],
        ["contact", "contacts"], ["location", "locations"],
        ["game", "games"], ["inline", "inline"],
      ];
      const specific = orderedKinds.find(([sampleKind, lock]) => kind === sampleKind && enabled(lock));
      if (specific) blockedBy = specific[1];
      else if (enabled("media") && MEDIA_KINDS.has(kind)) blockedBy = "media";
      else if (enabled("bots") && kind === "bot") blockedBy = "bots";
    }
  }

  const cleanText = message.trim();
  const isCommand = /^\/[A-Za-z0-9_]+/.test(cleanText);
  const matchingFilter = kind === "text" && cleanText && !isCommand
    ? filters
        .filter((filter) => filter.keyword.trim() && cleanText.toLocaleLowerCase().includes(filter.keyword.trim().toLocaleLowerCase()))
        .sort((a, b) => b.keyword.trim().length - a.keyword.trim().length)[0]
    : undefined;

  return {
    exemptFromLocks,
    blockedBy,
    autoReply: matchingFilter?.reply ?? null,
  };
}

export function safetyRuleLabel(key: string): string {
  return LOCK_LABELS[key] ?? key;
}
