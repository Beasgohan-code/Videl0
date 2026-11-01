export type BroadcastButton = { text: string; url: string };

export function normalizeBroadcastButtons(value: unknown): BroadcastButton[] | null {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value) || value.length > 8) return null;
  const result: BroadcastButton[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") return null;
    const candidate = item as Record<string, unknown>;
    if (typeof candidate.text !== "string" || !candidate.text.trim() || candidate.text.trim().length > 64) return null;
    if (typeof candidate.url !== "string" || candidate.url.length > 2048) return null;
    try {
      const url = new URL(candidate.url);
      if (url.protocol !== "https:" || url.username || url.password) return null;
      result.push({ text: candidate.text.trim(), url: url.href });
    } catch {
      return null;
    }
  }
  return result;
}
