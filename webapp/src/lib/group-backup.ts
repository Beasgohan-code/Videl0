/**
 * Portable group backups.
 *
 * A backup is plain JSON so the owner can keep it outside the panel. The file
 * carries configuration only — locks, automation, blacklist words and switched
 * off commands — never warnings, notes or member identities. The parser here
 * mirrors the backend rules so an obviously wrong file is rejected before a
 * round-trip, and the preview is built from the backend's diff, not a guess.
 */

export const BACKUP_FORMAT = "videl-group-backup";
export const BACKUP_VERSION = 1;
export const BACKUP_MAX_BYTES = 262_144;

export type BackupChanges = {
  settings: { before: Record<string, boolean | number | string | null>; after: Record<string, boolean | number | string | null> };
  automation: string[];
  blacklist: { add: string[]; remove: string[] };
  commands: { disable: string[]; enable: string[] };
};

const EMPTY_CHANGES: BackupChanges = {
  settings: { before: {}, after: {} },
  automation: [],
  blacklist: { add: [], remove: [] },
  commands: { disable: [], enable: [] },
};

function strings(value: unknown, limit = 300): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").slice(0, limit)
    : [];
}

function record(value: unknown): Record<string, boolean | number | string | null> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const output: Record<string, boolean | number | string | null> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (typeof item === "boolean" || typeof item === "number" || typeof item === "string" || item === null) {
      output[key] = item;
    }
  }
  return output;
}

/** Accepts the exact shape the backend writes, plus nothing else. */
export function parseBackupFile(text: string):
  | { ok: true; document: Record<string, unknown> }
  | { ok: false; error: string } {
  if (text.length > BACKUP_MAX_BYTES) {
    return { ok: false, error: "That file is larger than 256 KB, which is not a group backup." };
  }
  let document: unknown;
  try {
    document = JSON.parse(text);
  } catch {
    return { ok: false, error: "That file is not valid JSON." };
  }
  if (!document || typeof document !== "object" || Array.isArray(document)) {
    return { ok: false, error: "A group backup must be a JSON object." };
  }
  const candidate = document as Record<string, unknown>;
  const inner =
    candidate.backup && typeof candidate.backup === "object" && !Array.isArray(candidate.backup)
      ? (candidate.backup as Record<string, unknown>)
      : candidate;
  if (inner.format !== BACKUP_FORMAT) {
    return { ok: false, error: "That JSON file is not a Videl group backup." };
  }
  if (Number(inner.version) !== BACKUP_VERSION) {
    return { ok: false, error: `Backup version ${String(inner.version ?? "unknown")} cannot be imported by this panel.` };
  }
  if (!inner.settings || typeof inner.settings !== "object" || Array.isArray(inner.settings)) {
    return { ok: false, error: "That backup has no settings block." };
  }
  return { ok: true, document: inner };
}

/** Normalise whatever the backend returned into a renderable diff. */
export function backupChanges(value: unknown): BackupChanges {
  if (!value || typeof value !== "object" || Array.isArray(value)) return EMPTY_CHANGES;
  const source = value as Record<string, unknown>;
  const settings = (source.settings && typeof source.settings === "object" ? source.settings : {}) as Record<string, unknown>;
  const blacklist = (source.blacklist && typeof source.blacklist === "object" ? source.blacklist : {}) as Record<string, unknown>;
  const commands = (source.commands && typeof source.commands === "object" ? source.commands : {}) as Record<string, unknown>;
  return {
    settings: { before: record(settings.before), after: record(settings.after) },
    automation: strings(source.automation, 3),
    blacklist: { add: strings(blacklist.add), remove: strings(blacklist.remove) },
    commands: { disable: strings(commands.disable, 200), enable: strings(commands.enable, 200) },
  };
}

export function backupIsEmpty(changes: BackupChanges): boolean {
  return (
    Object.keys(changes.settings.after).length === 0 &&
    changes.automation.length === 0 &&
    changes.blacklist.add.length === 0 &&
    changes.blacklist.remove.length === 0 &&
    changes.commands.disable.length === 0 &&
    changes.commands.enable.length === 0
  );
}

function label(key: string): string {
  return key.replace(/^lock_/, "").replace(/_/g, " ").replace(/\benabled\b/, "").trim();
}

function describeSetting(key: string, value: boolean | number | string | null): string {
  if (typeof value === "boolean") return `${label(key)} ${value ? "on" : "off"}`;
  if (value === null || value === "") return `${label(key)} cleared`;
  return `${label(key)} ${String(value)}`;
}

/** One row per block that actually changes, for the confirmation preview. */
export function backupSummary(changes: BackupChanges): { label: string; detail: string }[] {
  const rows: { label: string; detail: string }[] = [];
  const after = changes.settings.after;
  const keys = Object.keys(after);
  if (keys.length) {
    const shown = keys.slice(0, 6).map((key) => describeSetting(key, after[key]));
    const rest = keys.length - shown.length;
    rows.push({
      label: `${keys.length} setting${keys.length === 1 ? "" : "s"} change`,
      detail: shown.join(" · ") + (rest > 0 ? ` · and ${rest} more` : ""),
    });
  }
  if (changes.automation.length) {
    rows.push({ label: "Automation", detail: changes.automation.join(", ") + " replaced" });
  }
  if (changes.blacklist.add.length || changes.blacklist.remove.length) {
    rows.push({
      label: "Blacklist",
      detail: [
        changes.blacklist.add.length ? `+${changes.blacklist.add.length} word${changes.blacklist.add.length === 1 ? "" : "s"}` : "",
        changes.blacklist.remove.length ? `−${changes.blacklist.remove.length} word${changes.blacklist.remove.length === 1 ? "" : "s"}` : "",
      ]
        .filter(Boolean)
        .join(" · "),
    });
  }
  if (changes.commands.disable.length || changes.commands.enable.length) {
    rows.push({
      label: "Commands",
      detail: [
        changes.commands.disable.length ? `${changes.commands.disable.length} switched off` : "",
        changes.commands.enable.length ? `${changes.commands.enable.length} switched back on` : "",
      ]
        .filter(Boolean)
        .join(" · "),
    });
  }
  return rows;
}

/** Safe download name: the group id and the day it was exported. */
export function backupFileName(chatId: number, now = new Date()): string {
  return `videl-group-${chatId}-${now.toISOString().slice(0, 10)}.json`;
}
