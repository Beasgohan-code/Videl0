export type MessageTemplatePreview = { text: string; unknown: string[] };

const SAMPLE_VALUES: Record<string, (groupTitle: string) => string> = {
  name: () => "Mira",
  id: () => "123456789",
  title: (groupTitle) => groupTitle || "Your group",
  mention: () => "@Mira",
};

/** Safe plain-text preview of the welcome/goodbye placeholders Videl supports. */
export function previewGroupMessage(template: string, groupTitle: string): MessageTemplatePreview {
  const unknown = new Set<string>();
  const text = template.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (token, key: string) => {
    const value = SAMPLE_VALUES[key];
    if (!value) {
      unknown.add(token);
      return token;
    }
    return value(groupTitle);
  });
  return { text, unknown: [...unknown] };
}
