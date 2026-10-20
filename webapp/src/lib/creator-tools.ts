export function textInsights(text: string) {
  return {
    characters: Array.from(text).length,
    telegramLength: text.length,
    words: text.trim() ? text.trim().split(/\s+/u).length : 0,
    hashtags: [
      ...new Set(
        (text.match(/#[\p{L}\p{M}\p{N}_]+/gu) || []).map((tag) =>
          tag.toLowerCase(),
        ),
      ),
    ],
  };
}
export function campaignLink(
  raw: string,
  source: string,
  medium: string,
  campaign: string,
): string {
  const url = new URL(raw);
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password
  )
    throw new Error("Enter a public http(s) URL without credentials.");
  for (const [name, value] of Object.entries({
    utm_source: source,
    utm_medium: medium,
    utm_campaign: campaign,
  })) {
    if (value.trim()) url.searchParams.set(name, value.trim());
    else url.searchParams.delete(name);
  }
  return url.toString();
}
