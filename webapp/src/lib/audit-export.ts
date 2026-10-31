export type AuditExportEvent = {
  at?: unknown;
  kind?: unknown;
  action?: unknown;
  detail?: unknown;
  source?: unknown;
  actor?: unknown;
};

const field = (value: unknown, max: number): string =>
  String(value ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);

function csvCell(value: string): string {
  const safe = /^[=+@\-\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}

/** Export only the current bounded audit page; actor identifiers are excluded. */
export function auditCsv(events: AuditExportEvent[]): string {
  const rows = events.slice(0, 40).map((event) => [
    field(event.at, 40),
    field(event.kind, 24),
    field(event.action, 48),
    // Avoid exporting Telegram-sized numeric identifiers embedded in details.
    field(event.detail, 240).replace(/(?<!\d)-?\d{6,}(?!\d)/g, "[id]"),
    field(event.source, 12),
  ]);
  return [
    ["timestamp", "category", "action", "summary", "source"],
    ...rows,
  ].map((row) => row.map(csvCell).join(",")).join("\r\n");
}
