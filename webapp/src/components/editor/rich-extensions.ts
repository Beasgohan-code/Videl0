import { Mark, Node, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import type { Editor } from "@tiptap/core";
import { safeLink } from "@/lib/telegram-format";

/** Telegram spoiler, edited as a styled span and serialized as <tg-spoiler>. */
export const Spoiler = Mark.create({
  name: "spoiler",
  parseHTML: () => [{ tag: 'span[data-spoiler="true"]' }, { tag: "tg-spoiler" }],
  renderHTML: ({ HTMLAttributes }) => [
    "span",
    mergeAttributes(HTMLAttributes, { "data-spoiler": "true", class: "tg-editor-spoiler" }),
    0,
  ],
});

/**
 * Premium (custom) emoji as an inline atom. The real artwork is resolved by
 * the owner-only /api/premium-emoji proxy; the fallback character stays
 * copyable and visible if Telegram cannot render the custom emoji.
 */
export const PremiumEmoji = Node.create({
  name: "premiumEmoji",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,
  addAttributes: () => ({
    emojiId: {
      default: null,
      parseHTML: (element) => element.getAttribute("emoji-id") || element.getAttribute("data-emoji-id"),
      renderHTML: (attributes) =>
        attributes.emojiId ? { "emoji-id": String(attributes.emojiId), "data-emoji-id": String(attributes.emojiId) } : {},
    },
    char: {
      default: "✨",
      parseHTML: (element) => (element.textContent || "✨").trim().slice(0, 8) || "✨",
      renderHTML: () => ({}),
    },
  }),
  parseHTML: () => [
    { tag: "tg-emoji" },
    { tag: "span[data-emoji-id]" },
  ],
  renderHTML: ({ node, HTMLAttributes }) => {
    const id = String(node.attrs.emojiId || "");
    const char = String(node.attrs.char || "✨");
    const art = /^[0-9]{1,20}$/.test(id)
      ? ["span", { class: "tg-emoji-art", "aria-hidden": "true", style: `background-image:url('/api/premium-emoji?id=${id}')` }]
      : ["span", { class: "tg-emoji-art", hidden: "true" }];
    return [
      "span",
      mergeAttributes(HTMLAttributes, { class: "tg-premium-emoji", title: `Premium emoji ${id}` }),
      char,
      art,
    ];
  },
});

export function richExtensions(placeholder: string) {
  return [
    StarterKit.configure({
      heading: { levels: [2, 3] },
      horizontalRule: false,
      link: false,
      underline: false,
    }),
    Underline,
    Link.configure({
      openOnClick: false,
      autolink: true,
      linkOnPaste: true,
      protocols: ["https", "http", "tg"],
      validate: (url) => Boolean(safeLink(url)),
    }),
    Spoiler,
    PremiumEmoji,
    Placeholder.configure({ placeholder }),
  ];
}

/** Insert a premium emoji at the caret (or replace the current selection). */
export function insertPremiumEmoji(editor: Editor, id: string, char: string) {
  editor.chain().focus().insertContent({ type: "premiumEmoji", attrs: { emojiId: id, char: char || "✨" } }).run();
}
