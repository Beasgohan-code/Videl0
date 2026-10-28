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
  group: "Reactions" | "Interface" | "Celebration" | "Play" | "Telegram Android";
};

export const PREMIUM_GROUPS: PremiumEmoji["group"][] = [
  "Reactions",
  "Interface",
  "Celebration",
  "Play",
  "Telegram Android",
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

  // User-supplied Telegram Android icon set (100 verified IDs).
  { id: "5875465628285931233", char: "✈️", label: "Android 01 · Plane", group: "Telegram Android" },
  { id: "5958376256788502078", char: "⭐️", label: "Android 02 · Star 01", group: "Telegram Android" },
  { id: "5960672896060756972", char: "⭐️", label: "Android 03 · Star 02", group: "Telegram Android" },
  { id: "5958413064658228696", char: "⭐️", label: "Android 04 · Star 03", group: "Telegram Android" },
  { id: "5931621672846103580", char: "💫", label: "Android 05 · Dizzy star", group: "Telegram Android" },
  { id: "5956561749070057536", char: "⭐️", label: "Android 06 · Star 04", group: "Telegram Android" },
  { id: "5956148757899776734", char: "⭐️", label: "Android 07 · Star 05", group: "Telegram Android" },
  { id: "5874948844935974490", char: "⭐️", label: "Android 08 · Star 06", group: "Telegram Android" },
  { id: "6032937473162614352", char: "🎁", label: "Android 09 · Gift 01", group: "Telegram Android" },
  { id: "5875180111744995604", char: "🎁", label: "Android 10 · Gift 02", group: "Telegram Android" },
  { id: "5877260593903177342", char: "⚙", label: "Android 11 · Settings", group: "Telegram Android" },
  { id: "5875271289605722323", char: "🍔", label: "Android 12 · Burger", group: "Telegram Android" },
  { id: "5875431869842985304", char: "🎛", label: "Android 13 · Controls 01", group: "Telegram Android" },
  { id: "5875462364110787088", char: "🗂", label: "Android 14 · Folder tabs", group: "Telegram Android" },
  { id: "5875033614705495771", char: "🎛", label: "Android 15 · Controls 02", group: "Telegram Android" },
  { id: "5886506997066502636", char: "📰", label: "Android 16 · News 01", group: "Telegram Android" },
  { id: "5886752540346814809", char: "📰", label: "Android 17 · News 02", group: "Telegram Android" },
  { id: "5886440807325504167", char: "📰", label: "Android 18 · News 03", group: "Telegram Android" },
  { id: "5886330010054168711", char: "📝", label: "Android 19 · Memo", group: "Telegram Android" },
  { id: "5888799736508454231", char: "🖼", label: "Android 20 · Image 01", group: "Telegram Android" },
  { id: "5886285363869126932", char: "🖼", label: "Android 21 · Image 02", group: "Telegram Android" },
  { id: "5888642858533001671", char: "↔️", label: "Android 22 · Left-right 01", group: "Telegram Android" },
  { id: "5886451926995833684", char: "⬇️", label: "Android 23 · Down 01", group: "Telegram Android" },
  { id: "5899757765743615694", char: "⬇️", label: "Android 24 · Down 02", group: "Telegram Android" },
  { id: "5879883461711367869", char: "⬇️", label: "Android 25 · Down 03", group: "Telegram Android" },
  { id: "5967432796627538166", char: "⬇️", label: "Android 26 · Down 04", group: "Telegram Android" },
  { id: "5875082500023258804", char: "⬅️", label: "Android 27 · Left arrow 01", group: "Telegram Android" },
  { id: "5846097080002550195", char: "↖️", label: "Android 28 · Up-left arrow", group: "Telegram Android" },
  { id: "5877629862306385808", char: "◀️", label: "Android 29 · Left triangle", group: "Telegram Android" },
  { id: "5875078273775439450", char: "🔼", label: "Android 30 · Up triangle", group: "Telegram Android" },
  { id: "5875008416132370818", char: "🔽", label: "Android 31 · Down triangle", group: "Telegram Android" },
  { id: "5874986954180791957", char: "📶", label: "Android 32 · Signal", group: "Telegram Android" },
  { id: "6005843436479975944", char: "🔁", label: "Android 33 · Repeat", group: "Telegram Android" },
  { id: "5886707481844912001", char: "↔️", label: "Android 34 · Left-right 02", group: "Telegram Android" },
  { id: "5886762118123886049", char: "↔️", label: "Android 35 · Left-right 03", group: "Telegram Android" },
  { id: "5877468380125990242", char: "➡️", label: "Android 36 · Right 01", group: "Telegram Android" },
  { id: "5832251986635920010", char: "➡️", label: "Android 37 · Right 02", group: "Telegram Android" },
  { id: "5886334622849044906", char: "➡️", label: "Android 38 · Right 03", group: "Telegram Android" },
  { id: "5830060857530257978", char: "➡️", label: "Android 39 · Right 04", group: "Telegram Android" },
  { id: "5888484185261216745", char: "⬅️", label: "Android 40 · Left 02", group: "Telegram Android" },
  { id: "5875506366050734240", char: "➡️", label: "Android 41 · Right 05", group: "Telegram Android" },
  { id: "5877536313623711363", char: "⬅️", label: "Android 42 · Left 03", group: "Telegram Android" },
  { id: "5967432491684860012", char: "🛜", label: "Android 43 · Wireless 01", group: "Telegram Android" },
  { id: "5884343982816759327", char: "↗️", label: "Android 44 · Up-right arrow", group: "Telegram Android" },
  { id: "5874960879434338403", char: "🔎", label: "Android 45 · Search", group: "Telegram Android" },
  { id: "5843862283964390528", char: "🔖", label: "Android 46 · Bookmark", group: "Telegram Android" },
  { id: "5825794181183836432", char: "✔️", label: "Android 47 · Check 01", group: "Telegram Android" },
  { id: "5823396554345549784", char: "✔️", label: "Android 48 · Check 02", group: "Telegram Android" },
  { id: "5877219383691972108", char: "➕", label: "Android 49 · Plus 01", group: "Telegram Android" },
  { id: "5875019892284985369", char: "➕", label: "Android 50 · Plus 02", group: "Telegram Android" },
  { id: "5877396173135811032", char: "⌨", label: "Android 51 · Keyboard", group: "Telegram Android" },
  { id: "5875450995332353523", char: "🔨", label: "Android 52 · Hammer", group: "Telegram Android" },
  { id: "5771887475421090729", char: "👤", label: "Android 53 · Person 01", group: "Telegram Android" },
  { id: "5814247475141153332", char: "👤", label: "Android 54 · Person 02", group: "Telegram Android" },
  { id: "5814550759961793482", char: "👤", label: "Android 55 · Person 03", group: "Telegram Android" },
  { id: "5877316724830768997", char: "🗃", label: "Android 56 · Archive 01", group: "Telegram Android" },
  { id: "5778546461436284629", char: "🔋", label: "Android 57 · Battery", group: "Telegram Android" },
  { id: "5877485980901971030", char: "📊", label: "Android 58 · Chart 01", group: "Telegram Android" },
  { id: "5924720918826848520", char: "📦", label: "Android 59 · Package", group: "Telegram Android" },
  { id: "5875291072225087249", char: "📊", label: "Android 60 · Chart 02", group: "Telegram Android" },
  { id: "5875206779196935950", char: "📁", label: "Android 61 · Folder 01", group: "Telegram Android" },
  { id: "5877443460725739250", char: "📁", label: "Android 62 · Folder 02", group: "Telegram Android" },
  { id: "5839323457015256759", char: "📄", label: "Android 63 · Document 01", group: "Telegram Android" },
  { id: "5877495434124988415", char: "📎", label: "Android 64 · Paperclip", group: "Telegram Android" },
  { id: "5877465816030515018", char: "🔗", label: "Android 65 · Link 01", group: "Telegram Android" },
  { id: "5778168620278354602", char: "🔗", label: "Android 66 · Link 02", group: "Telegram Android" },
  { id: "5765071340847501478", char: "🔗", label: "Android 67 · Link 03", group: "Telegram Android" },
  { id: "5877738786971979125", char: "🔗", label: "Android 68 · Link 04", group: "Telegram Android" },
  { id: "5888751259212583270", char: "🔗", label: "Android 69 · Link 05", group: "Telegram Android" },
  { id: "5839354140261619193", char: "🛜", label: "Android 70 · Wireless 02", group: "Telegram Android" },
  { id: "5877318502947229960", char: "💻", label: "Android 71 · Laptop 01", group: "Telegram Android" },
  { id: "5967816500415827773", char: "💻", label: "Android 72 · Laptop 02", group: "Telegram Android" },
  { id: "5877482652302315100", char: "📁", label: "Android 73 · Folder 03", group: "Telegram Android" },
  { id: "5877680341057015789", char: "📁", label: "Android 74 · Folder 04", group: "Telegram Android" },
  { id: "5877540355187937244", char: "📤", label: "Android 75 · Upload", group: "Telegram Android" },
  { id: "5877307202888273539", char: "📥", label: "Android 76 · Download", group: "Telegram Android" },
  { id: "5967456680940671207", char: "🗃", label: "Android 77 · Archive 02", group: "Telegram Android" },
  { id: "5877332341331857066", char: "📁", label: "Android 78 · Folder 05", group: "Telegram Android" },
  { id: "6017174676898321263", char: "📂", label: "Android 79 · Open folder", group: "Telegram Android" },
  { id: "5854776233950188167", char: "🏷", label: "Android 80 · Tag 01", group: "Telegram Android" },
  { id: "5843478103434728287", char: "🏷", label: "Android 81 · Tag 02", group: "Telegram Android" },
  { id: "5845955401916355857", char: "🏷", label: "Android 82 · Tag 03", group: "Telegram Android" },
  { id: "5870525453822859417", char: "🏷", label: "Android 83 · Tag 04", group: "Telegram Android" },
  { id: "5886763041541853781", char: "🏷", label: "Android 84 · Tag 05", group: "Telegram Android" },
  { id: "5881986900469748194", char: "🏷", label: "Android 85 · Tag 06", group: "Telegram Android" },
  { id: "5985433648810171091", char: "🏷", label: "Android 86 · Tag 07", group: "Telegram Android" },
  { id: "5987802868734760945", char: "🏷", label: "Android 87 · Tag 08", group: "Telegram Android" },
  { id: "5987718983728503684", char: "🏷", label: "Android 88 · Tag 09", group: "Telegram Android" },
  { id: "5843843420468024653", char: "⭐️", label: "Android 89 · Star 07", group: "Telegram Android" },
  { id: "5841238690306724929", char: "⭐️", label: "Android 90 · Star 08", group: "Telegram Android" },
  { id: "5879896690210639947", char: "🗑", label: "Android 91 · Trash 01", group: "Telegram Android" },
  { id: "5841541824803509441", char: "🗑", label: "Android 92 · Trash 02", group: "Telegram Android" },
  { id: "5879915802815107172", char: "🗑", label: "Android 93 · Trash 03", group: "Telegram Android" },
  { id: "5879937509579820068", char: "🗑", label: "Android 94 · Trash 04", group: "Telegram Android" },
  { id: "5877301185639091664", char: "📄", label: "Android 95 · Document 02", group: "Telegram Android" },
  { id: "5879841310902324730", char: "✏️", label: "Android 96 · Pencil", group: "Telegram Android" },
  { id: "5839380580080293813", char: "🖋", label: "Android 97 · Fountain pen", group: "Telegram Android" },
  { id: "5877341274863832725", char: "🚪", label: "Android 98 · Door", group: "Telegram Android" },
  { id: "5879770735999717115", char: "👤", label: "Android 99 · Person 04", group: "Telegram Android" },
  { id: "5877530150345641603", char: "👤", label: "Android 100 · Person 05", group: "Telegram Android" },
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
