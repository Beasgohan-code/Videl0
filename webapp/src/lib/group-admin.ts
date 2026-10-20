/**
 * Group manager vocabulary shared by the screen and its API routes.
 *
 * Everything here mirrors what the bot actually reads from
 * `mgmt_chat_settings`. A control is only listed if the enforcement code
 * executes it — the UI never offers a switch that saves into a void.
 */

export type SettingValue = boolean | number | string;
export type GroupSettings = Record<string, SettingValue>;

export type GroupCounts = {
  warns: number;
  notes: number;
  blacklist: number;
  approved: number;
};

export type HealthIssue = { code: string; message: string; advisory?: boolean };
export type GroupHealth = { score: number; issues: HealthIssue[]; attention: boolean };

export type QuietHours = { enabled: boolean; start: string; end: string; tz_offset: number };
export type Escalation = { enabled: boolean; action: EscalationAction; mute_hours: number };
export type EscalationAction = "ban" | "mute" | "kick" | "none";
export type Automation = { quiet_hours: QuietHours; escalation: Escalation };

export type ReportRow = {
  id: string;
  reporter: number | null;
  target: number | null;
  message_id: number | null;
  text: string;
  at: string | null;
};
export type JoinRequest = {
  user_id: number;
  name: string;
  username: string | null;
  at: string | null;
};
export type GroupInbox = { reports: ReportRow[]; join_requests: JoinRequest[] };

export type AuditEvent = {
  kind: string;
  action: string;
  detail: string;
  actor: number | null;
  source: string;
  at: string | null;
};

export type Group = {
  id: number;
  title: string;
  username?: string | null;
  type: string;
  members: number | null;
  available: boolean;
  settings: GroupSettings;
  /** Only the switches actually stored for this group; absent keys are unset. */
  explicit?: GroupSettings;
  counts?: GroupCounts;
  warn_limit?: number;
  bot_admin?: boolean | null;
  automation?: Automation;
  health?: GroupHealth;
};

export type GroupsSummary = {
  total: number;
  attention: number;
  unreachable: number;
  protected: number;
  average: number;
};

export type WarnRow = { user_id: number; count: number; reasons: string[] };
export type NoteRow = { name: string; type: string };
export type FilterRow = { keyword: string; reply: string };
export type BlacklistRow = { trigger: string; mode: string };

export type GroupCommunity = {
  warns: WarnRow[];
  warn_limit: number;
  notes: NoteRow[];
  filters: FilterRow[];
  blacklist: BlacklistRow[];
  approved: number[];
  disabled_commands: string[];
};

export type GroupDetail = {
  automation?: Automation;
  inbox?: GroupInbox;
  chat: {
    id: number;
    title: string;
    type: string;
    username?: string | null;
    member_count?: number | null;
    description?: string | null;
    invite_link?: string | null;
    available?: boolean;
    is_forum?: boolean;
    slow_mode_delay?: number;
    permissions?: Record<string, boolean>;
    bot?: { is_admin?: boolean; status?: string | null; username?: string | null; can_manage?: boolean };
    owner?: { status?: string | null };
  };
  settings: GroupSettings;
  presets: Record<string, Preset>;
  community: GroupCommunity;
  problems: string[];
};

export type Preset = { label: string; description: string; settings: GroupSettings };

/** Locks enforced by `videl/plugins/locks.py`, in the order the bot reads them. */
export const LOCK_KEYS = [
  "lock_links",
  "lock_forwards",
  "lock_media",
  "lock_stickers",
  "lock_animations",
  "lock_photos",
  "lock_videos",
  "lock_audio",
  "lock_voice",
  "lock_documents",
  "lock_polls",
  "lock_mentions",
  "lock_bots",
  "lock_inline",
  "lock_contacts",
  "lock_locations",
  "lock_games",
] as const;

export type SettingsGroup = {
  id: string;
  title: string;
  description: string;
  controls: { key: string; label: string; description: string }[];
};

export const PROTECTION_GROUPS: SettingsGroup[] = [
  {
    id: "links",
    title: "Links & forwards",
    description: "Stops traffic that usually precedes spam.",
    controls: [
      { key: "lock_links", label: "Links", description: "Delete messages containing URLs, @links or t.me invites" },
      { key: "lock_forwards", label: "Forwards", description: "Delete forwarded messages from members" },
      { key: "lock_mentions", label: "Mentions", description: "Delete @mentions and text mentions" },
      { key: "lock_inline", label: "Inline bots", description: "Delete messages sent through inline bots" },
    ],
  },
  {
    id: "media",
    title: "Media",
    description: "Per-type media locks, enforced before the general media lock.",
    controls: [
      { key: "lock_media", label: "All media", description: "Delete every photo, video, audio, voice note and document" },
      { key: "lock_photos", label: "Photos", description: "Delete photo messages" },
      { key: "lock_videos", label: "Videos", description: "Delete videos and video notes" },
      { key: "lock_audio", label: "Audio", description: "Delete audio files" },
      { key: "lock_voice", label: "Voice notes", description: "Delete voice messages" },
      { key: "lock_documents", label: "Documents", description: "Delete documents and archives" },
      { key: "lock_animations", label: "GIFs", description: "Delete animated media" },
      { key: "lock_stickers", label: "Stickers", description: "Delete sticker messages" },
    ],
  },
  {
    id: "interactive",
    title: "Interactive",
    description: "Polls, bots and location sharing.",
    controls: [
      { key: "lock_polls", label: "Polls", description: "Delete polls and quizzes" },
      { key: "lock_bots", label: "Bot messages", description: "Delete messages posted by other bots" },
      { key: "lock_contacts", label: "Contacts", description: "Delete shared contact cards" },
      { key: "lock_locations", label: "Locations", description: "Delete live and static locations" },
      { key: "lock_games", label: "Games", description: "Delete Telegram games" },
    ],
  },
  {
    id: "flood",
    title: "Flood & joins",
    description: "Applies to everyone except admins and approved members.",
    controls: [
      { key: "antispam", label: "Anti-Spam", description: "Delete bursts above 6 messages per user in 8 seconds" },
      { key: "captcha_enabled", label: "Join captcha", description: "New members solve a short challenge before posting" },
      { key: "welcome_enabled", label: "Welcome message", description: "Greet new members with your saved text" },
      { key: "goodbye_enabled", label: "Goodbye message", description: "Post your saved farewell when a member leaves" },
    ],
  },
];

/** Keys the UI may write, derived from the groups above. */
export const SETTING_KEYS = PROTECTION_GROUPS.flatMap((group) => group.controls.map((control) => control.key));

/** The bot greets new members unless the value is explicitly false. */
export const SETTING_DEFAULTS: Record<string, boolean> = { welcome_enabled: true };

export const BLACKLIST_MODES = [
  { id: "off", label: "Off", description: "Do not act on blacklisted words" },
  { id: "del", label: "Delete", description: "Remove the message" },
  { id: "warn", label: "Warn", description: "Remove the message and add a warning" },
  { id: "mute", label: "Mute", description: "Remove the message and mute the sender" },
  { id: "kick", label: "Kick", description: "Remove the message and kick the sender" },
  { id: "ban", label: "Ban", description: "Remove the message and ban the sender" },
] as const;

export const PRESET_ORDER = ["relaxed", "balanced", "strict", "lockdown"] as const;
export type PresetId = (typeof PRESET_ORDER)[number];

/** Local copy for the description text only — the backend remains the writer. */
export const PRESET_COPY: Record<PresetId, { label: string; description: string }> = {
  relaxed: { label: "Relaxed", description: "Greetings on, every lock released." },
  balanced: { label: "Balanced", description: "Flood control, links and forwards." },
  strict: { label: "Strict", description: "Media, stickers, mentions, bots and polls blocked." },
  lockdown: { label: "Lockdown", description: "Every lock on, greetings paused." },
};

export type GroupFilter = "all" | "protected" | "open" | "warns" | "unavailable" | "attention";
export type GroupSort = "name" | "members" | "warns" | "type" | "health";

export const FILTERS: { id: GroupFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "protected", label: "Protected" },
  { id: "open", label: "No locks" },
  { id: "warns", label: "Has warnings" },
  { id: "unavailable", label: "Unreachable" },
  { id: "attention", label: "Needs attention" },
];

export const SORTS: { id: GroupSort; label: string }[] = [
  { id: "name", label: "Name" },
  { id: "members", label: "Members" },
  { id: "warns", label: "Warnings" },
  { id: "type", label: "Type" },
  { id: "health", label: "Health" },
];

/** Treat stored values as on/off without trusting their JSON type. */
export function flag(settings: GroupSettings | undefined, key: string): boolean {
  const value = settings?.[key];
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return value === "true" || value === "on" || value === "1";
  return SETTING_DEFAULTS[key] ?? false;
}

export function numberValue(settings: GroupSettings | undefined, key: string, fallback = 0): number {
  const value = settings?.[key];
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function textValue(settings: GroupSettings | undefined, key: string): string {
  const value = settings?.[key];
  return typeof value === "string" ? value : "";
}

/** A switch the owner actually saved. Missing keys are not "configured". */
export function isExplicitlyOn(settings: GroupSettings | undefined, key: string): boolean {
  const value = settings?.[key];
  return value === true || value === 1 || value === "true" || value === "on";
}

/**
 * Guards configured for this group. Defaults are not counted: a freshly added
 * group must not look protected just because welcomes default to on.
 */
export function protectionSummary(
  settings: GroupSettings | undefined,
  explicit?: GroupSettings,
): { active: number; total: number } {
  // Stored values win. The API fills defaults for every key, so counting the
  // filled view would call a brand-new group "protected" because welcomes
  // default to on.
  const source = explicit ?? settings;
  const active = SETTING_KEYS.filter((key) => isExplicitlyOn(source, key)).length;
  return { active, total: SETTING_KEYS.length };
}

/** Effective stored values, falling back to the filled settings for older payloads. */
export function explicitSettings(group: Pick<Group, "settings" | "explicit">): GroupSettings {
  return group.explicit ?? group.settings;
}

/** Effective switch positions, including the bot's defaults (used by the panel). */
export function effectiveGuards(settings: GroupSettings | undefined): number {
  return SETTING_KEYS.filter((key) => flag(settings, key)).length;
}

export function matchesQuery(group: Group, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return `${group.title} ${group.id} ${group.username ?? ""}`.toLowerCase().includes(needle);
}

export function filterGroup(group: Group, filter: GroupFilter): boolean {
  switch (filter) {
    case "protected":
      return protectionSummary(group.settings, explicitSettings(group)).active > 0;
    case "open":
      return protectionSummary(group.settings, explicitSettings(group)).active === 0;
    case "warns":
      return (group.counts?.warns ?? 0) > 0;
    case "unavailable":
      return !group.available;
    case "attention":
      return group.health?.attention === true;
    default:
      return true;
  }
}

export function sortGroups(groups: Group[], sort: GroupSort): Group[] {
  const copy = [...groups];
  copy.sort((a, b) => {
    switch (sort) {
      case "members":
        return (b.members ?? -1) - (a.members ?? -1) || a.title.localeCompare(b.title);
      case "warns":
        return (b.counts?.warns ?? 0) - (a.counts?.warns ?? 0) || a.title.localeCompare(b.title);
      case "type":
        return a.type.localeCompare(b.type) || a.title.localeCompare(b.title);
      case "health":
        return (a.health?.score ?? 100) - (b.health?.score ?? 100) || a.title.localeCompare(b.title);
      default:
        return a.title.localeCompare(b.title);
    }
  });
  return copy;
}

export function visibleGroups(
  groups: Group[],
  { query, filter, sort }: { query: string; filter: GroupFilter; sort: GroupSort },
): Group[] {
  return sortGroups(
    groups.filter((group) => matchesQuery(group, query) && filterGroup(group, filter)),
    sort,
  );
}

export function toggleSelected(selected: number[], id: number): number[] {
  return selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id];
}

/** The backend refuses bulk writes above this size; the UI mirrors it. */
export const BULK_LIMIT = 15;

export function bulkSelection(selected: number[]): { ids: number[]; overflow: number } {
  return { ids: selected.slice(0, BULK_LIMIT), overflow: Math.max(0, selected.length - BULK_LIMIT) };
}

/** Merge a settings patch returned by the backend into a list row. */
export function applySettings(group: Group, patch: GroupSettings): Group {
  return { ...group, settings: { ...group.settings, ...patch } };
}

export function applySettingsToChats(groups: Group[], ids: number[], patch: GroupSettings): Group[] {
  const target = new Set(ids);
  return groups.map((group) => (target.has(group.id) ? applySettings(group, patch) : group));
}

/** Bot API rates a group title at 128 chars; keep list rows honest. */
export function displayTitle(group: Pick<Group, "title" | "id">): string {
  const title = group.title?.trim();
  return title ? title.slice(0, 128) : `Telegram chat ${group.id}`;
}

export function memberLabel(members: number | null | undefined): string {
  if (typeof members !== "number" || members < 0) return "members unknown";
  return `${members.toLocaleString("en-US")} member${members === 1 ? "" : "s"}`;
}

export function errorHint(message: string, status?: number): string {
  if (status === 501) return "The bot backend needs its Render redeploy before this panel can save.";
  if (/supported boolean|protection settings are accepted/i.test(message))
    return "This switch is newer than the running bot backend. Redeploy the Render service, then retry.";
  if (message.includes("served")) return "Add the bot to this group and send /start there, then refresh.";
  if (message.includes("administrator")) return "Your Telegram account must be an admin in this group to change it.";
  if (message.includes("permission")) return "The bot is missing a group permission this action needs.";
  return message;
}

export const ESCALATION_CHOICES: { id: EscalationAction; label: string; description: string }[] = [
  { id: "none", label: "Nothing", description: "Warnings are recorded but no member is restricted." },
  { id: "mute", label: "Mute temporarily", description: "Restrict the member for the chosen number of hours." },
  { id: "kick", label: "Remove", description: "Kick the member; they may rejoin unless banned." },
  { id: "ban", label: "Ban", description: "Ban the member from the group." },
];

/** Local mm:ss helpers shared by the editor and its preview. */
export function hhmmToMinutes(value: string): number | null {
  const match = /^([01]?\d|2[0-3]):([0-5]\d)$/.exec(value.trim());
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

export function zoneLabel(offsetMinutes: number): string {
  const sign = offsetMinutes < 0 ? "-" : "+";
  const absolute = Math.abs(offsetMinutes);
  return `UTC${sign}${String(Math.floor(absolute / 60)).padStart(2, "0")}:${String(absolute % 60).padStart(2, "0")}`;
}

/** Is "now" inside the window, evaluated in the panel's own clock? */
export function quietNow(quiet: QuietHours, now = new Date()): boolean {
  if (!quiet.enabled) return false;
  const start = hhmmToMinutes(quiet.start);
  const end = hhmmToMinutes(quiet.end);
  if (start === null || end === null || start === end) return false;
  const shifted = new Date(now.getTime() + quiet.tz_offset * 60_000);
  const current = shifted.getUTCHours() * 60 + shifted.getUTCMinutes();
  return start < end ? current >= start && current < end : current >= start || current < end;
}

export function quietSummary(quiet: QuietHours): string {
  if (!quiet.enabled) return "Quiet hours are off.";
  return `Silent ${quiet.start}–${quiet.end} (${zoneLabel(quiet.tz_offset)})`;
}

export function escalationSummary(escalation: Escalation): string {
  if (!escalation.enabled || escalation.action === "none") return "No automatic restriction.";
  if (escalation.action === "mute") return `Mute for ${escalation.mute_hours}h at the warning limit.`;
  return `${escalation.action === "kick" ? "Remove" : "Ban"} at the warning limit.`;
}

export function healthTone(score: number): "good" | "watch" | "poor" {
  if (score >= 85) return "good";
  if (score >= 70) return "watch";
  return "poor";
}

/** Human wording for an audit row; the fallback keeps unknown kinds readable. */
export function auditLabel(event: AuditEvent): string {
  const labels: Record<string, string> = {
    settings: "Protection changed",
    protect: "Protection changed",
    preset: "Preset applied",
    warn_limit: "Warning limit changed",
    welcome: "Welcome updated",
    goodbye: "Goodbye updated",
    rules: "Rules updated",
    blacklist: "Blacklist changed",
    blacklist_mode: "Blacklist mode changed",
    note: "Note removed",
    filter: "Filter removed",
    approval: "Approval removed",
    warn_reset: "Warnings cleared",
    automation: "Automation updated",
    commands: "Command switch changed",
    recording: "Recording changed",
    purge: "History purged",
    join_request: "Join request reviewed",
    report: "Report reviewed",
  };
  return labels[event.kind] ?? event.kind.replace(/_/g, " ");
}

export function whenLabel(iso: string | null): string {
  if (!iso) return "time unknown";
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "time unknown";
  return date.toLocaleString();
}
