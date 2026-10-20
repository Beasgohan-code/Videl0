import { safeLink } from "@/lib/telegram-format";

/**
 * Convert Markdown-ish text into the HTML subset Telegram accepts.
 *
 * This is intentionally small and predictable: headings become bold lines,
 * blockquotes become <blockquote>, lists keep their text, and the usual inline
 * marks move to Telegram tags. Anything Telegram cannot render (tables,
 * images) is left as readable text instead of being silently dropped.
 */

const PLACEHOLDER = "\u0000";

function escapeText(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function protectCode(input: string, store: string[]) {
  let output = input.replace(/```[a-zA-Z0-9_+-]*\n?([\s\S]*?)```/g, (_match, code: string) => {
    store.push(`<pre>${escapeText(code.replace(/\n$/, ""))}</pre>`);
    return `${PLACEHOLDER}C${store.length - 1}${PLACEHOLDER}`;
  });
  output = output.replace(/`([^`\n]+)`/g, (_match, code: string) => {
    store.push(`<code>${escapeText(code)}</code>`);
    return `${PLACEHOLDER}C${store.length - 1}${PLACEHOLDER}`;
  });
  return output;
}

function restore(html: string, store: string[]) {
  return html.replace(
    new RegExp(`${PLACEHOLDER}C(\\d+)${PLACEHOLDER}`, "g"),
    (_match, index: string) => store[Number(index)] ?? "",
  );
}

function inline(text: string) {
  let out = text;

  // Links: [label](url) — only http(s) and tg:// survive validation.
  out = out.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (match, label: string, url: string) => {
    const decoded = url.replace(/&amp;/g, "&");
    const safe = safeLink(decoded);
    if (!safe) return `${label} (${url})`;
    return `<a href="${escapeText(safe)}">${label}</a>`;
  });

  out = out
    .replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
    .replace(/__([^_\n]+)__/g, "<b>$1</b>")
    .replace(/~~([^~\n]+)~~/g, "<s>$1</s>")
    .replace(/\|\|([^|\n]+)\|\|/g, "<tg-spoiler>$1</tg-spoiler>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<i>$2</i>")
    .replace(/(^|[\s(])_([^_\n]+)_(?![\w])/g, "$1<i>$2</i>");

  return out;
}

function lines(text: string) {
  return text
    .split("\n")
    .map((line) => {
      const heading = line.match(/^\s{0,3}#{1,6}\s+(.*)$/);
      if (heading) return `<b>${heading[1].trim()}</b>`;
      const quote = line.match(/^\s{0,3}&gt;\s?(.*)$/);
      if (quote) return { quote: quote[1] };
      const bullet = line.match(/^\s{0,3}[-*+]\s+(.*)$/);
      if (bullet) return `• ${bullet[1]}`;
      return line;
    });
}

export function markdownToTelegram(markdown: string): string {
  const store: string[] = [];
  const protectedInput = protectCode(markdown.replace(/\r\n?/g, "\n"), store);
  const escaped = escapeText(protectedInput);

  const rendered: string[] = [];
  let quote: string[] = [];
  const flushQuote = () => {
    if (!quote.length) return;
    rendered.push(`<blockquote>${quote.join("\n")}</blockquote>`);
    quote = [];
  };

  for (const line of lines(escaped)) {
    if (typeof line === "object") {
      quote.push(inline(line.quote));
      continue;
    }
    flushQuote();
    rendered.push(inline(line));
  }
  flushQuote();

  return restore(rendered.join("\n"), store).replace(/\n{3,}/g, "\n\n").trim();
}

/** True when the Markdown produced at least one Telegram formatting tag. */
export function hasFormatting(html: string) {
  return /<(b|i|s|u|code|pre|blockquote|a|tg-spoiler)\b/i.test(html);
}
