/**
 * Curated premium (custom) emoji library.
 *
 * Telegram renders `<tg-emoji emoji-id="…">fallback</tg-emoji>` with the custom
 * artwork when the bot is allowed to send it, and with the plain fallback
 * character everywhere else. IDs below come from public Telegram emoji packs
 * (Colourful, UI Pro White, Gamefun) and are verified document IDs — they are
 * not placeholders.
 */
export type PremiumEmoji = {
  id: string;
  char: string;
  label: string;
  group: "Reactions" | "Interface" | "Celebration" | "Play";
};

export const PREMIUM_GROUPS: PremiumEmoji["group"][] = [
  "Reactions",
  "Interface",
  "Celebration",
  "Play",
];

export const PREMIUM_EMOJI: PremiumEmoji[] = [
  { id: "5039753786638205957", char: "❤️", label: "Love", group: "Reactions" },
  { id: "5042297717242463211", char: "💯", label: "Hundred", group: "Reactions" },
  { id: "5039539210072097557", char: "🔥", label: "Fire crown", group: "Reactions" },
  { id: "5042334757040423886", char: "⚡", label: "Lightning", group: "Reactions" },
  { id: "5039623284056917259", char: "👀", label: "Eyes", group: "Reactions" },
  { id: "5041866884778034602", char: "💀", label: "Skull", group: "Reactions" },
  { id: "5041992177563993101", char: "💥", label: "Burst", group: "Reactions" },
  { id: "5042209657527993345", char: "😈", label: "Mischief", group: "Reactions" },

  { id: "5258185631355378853", char: "⭐", label: "Star", group: "Interface" },
  { id: "5258073068852485953", char: "✈️", label: "Paper plane", group: "Interface" },
  { id: "5258050709252743821", char: "✉️", label: "Envelope", group: "Interface" },
  { id: "5258105663359294787", char: "🔗", label: "Link", group: "Interface" },
  { id: "5260730055880876557", char: "🔍", label: "Search", group: "Interface" },
  { id: "5257974976094412956", char: "🖼️", label: "Image", group: "Interface" },
  { id: "5258513401784573443", char: "👥", label: "People", group: "Interface" },
  { id: "5260726538302660868", char: "✅", label: "Check", group: "Interface" },
  { id: "5260268501515377807", char: "💬", label: "Chat", group: "Interface" },
  { id: "5260280853841321805", char: "🕐", label: "Clock", group: "Interface" },
  { id: "5258260149037965799", char: "🔒", label: "Lock", group: "Interface" },
  { id: "5039727604517570274", char: "🌐", label: "Globe", group: "Interface" },
  { id: "5039895103947146186", char: "📍", label: "Pin", group: "Interface" },

  { id: "5042225965518816316", char: "👑", label: "Red crown", group: "Celebration" },
  { id: "5039727497143387500", char: "👑", label: "Gold crown", group: "Celebration" },
  { id: "5039686583284925280", char: "🎁", label: "Gift", group: "Celebration" },
  { id: "5042274086332400375", char: "🍾", label: "Champagne", group: "Celebration" },
  { id: "5039685805895844805", char: "🎂", label: "Birthday", group: "Celebration" },
  { id: "5042050649248760772", char: "💎", label: "Diamond", group: "Celebration" },
  { id: "5041975203853239332", char: "🪙", label: "Coin", group: "Celebration" },
  { id: "5042328396193864923", char: "🎈", label: "Balloon", group: "Celebration" },

  { id: "5368324170671202286", char: "👍", label: "Thumbs up", group: "Play" },
  { id: "5465465194056525619", char: "🎮", label: "Good game", group: "Play" },
  { id: "5463412289883353404", char: "🚀", label: "Hype", group: "Play" },
  { id: "5463277406435422003", char: "👌", label: "Okay", group: "Play" },
  { id: "5462882007451185227", char: "🙅", label: "Nope", group: "Play" },
  { id: "5463423955014529788", char: "🙆", label: "Yes", group: "Play" },
  { id: "5463092727136661235", char: "🏆", label: "MVP", group: "Play" },
  { id: "5465443379917629504", char: "🧑‍💻", label: "Hack", group: "Play" },
];

export function isEmojiId(value: string) {
  return /^[0-9]{1,20}$/.test(value.trim());
}

/** Serialize one premium emoji into Telegram's HTML style. */
export function premiumEmojiTag(id: string, char: string) {
  const emojiId = id.trim();
  const fallback = [...char.trim()].slice(0, 8).join("") || "✨";
  if (!isEmojiId(emojiId)) return fallback;
  return `<tg-emoji emoji-id="${emojiId}">${fallback
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")}</tg-emoji>`;
}

function escapeText(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Browser-safe artwork for a premium emoji.
 *
 * The fallback character stays in the DOM (copy, screen readers, and the case
 * where the bot cannot resolve the artwork), and the resolved image is layered
 * on top by CSS. Only an already validated numeric id reaches the proxy URL.
 */
export function premiumEmojiArt(id: string, char: string) {
  const fallback = escapeText([...String(char || "✨").trim()].slice(0, 8).join("") || "✨");
  const emojiId = String(id || "").trim();
  if (!isEmojiId(emojiId)) return fallback;
  return `<span class="tg-premium-emoji" data-emoji-id="${emojiId}">${fallback}<span class="tg-emoji-art" aria-hidden="true" style="background-image:url('/api/premium-emoji?id=${emojiId}')"></span></span>`;
}
