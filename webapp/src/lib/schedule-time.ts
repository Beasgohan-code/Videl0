/**
 * Wall-clock ⇄ UTC for scheduled posts.
 *
 * A datetime-local input is a wall clock with no offset. When the owner picks
 * a zone, that wall clock belongs to the zone, not to the device: 09:00 in
 * Asia/Kolkata is 03:30Z, and 09:00 in America/New_York is 14:00Z in winter
 * and 13:00Z in summer.
 *
 * Two days a year a wall clock is not a function of UTC:
 * - a nonexistent time (spring-forward gap) moves forward to the first minute
 *   that exists, and says it was adjusted;
 * - an ambiguous time (fall-back) resolves to its first occurrence, so the
 *   backend sends once rather than twice.
 */

export const COMMON_TIMEZONES = [
  "UTC",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Moscow",
  "Africa/Johannesburg",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "Australia/Sydney",
  "Pacific/Auckland",
];

/** Every zone the browser knows, with a small fallback for old engines. */
export function timezoneOptions(preferred?: string): string[] {
  let zones: string[] = [];
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] })
      .supportedValuesOf;
    if (typeof supported === "function") zones = supported("timeZone");
  } catch {
    zones = [];
  }
  if (!zones.length) zones = [...COMMON_TIMEZONES];
  const list = new Set(zones.length ? zones : COMMON_TIMEZONES);
  // supportedValuesOf() omits UTC even though it is a valid zone.
  list.add("UTC");
  if (preferred) list.add(preferred);
  return [...list].sort((left, right) => left.localeCompare(right));
}

/** The device's zone, or UTC when the engine cannot say. */
export function deviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

type Wall = { year: number; month: number; day: number; hour: number; minute: number; second: number };

function parseWall(value: string): Wall | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value.trim());
  if (!match) return null;
  const wall: Wall = {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4]),
    minute: Number(match[5]),
    second: Number(match[6] ?? 0),
  };
  const probe = new Date(Date.UTC(wall.year, wall.month - 1, wall.day, wall.hour, wall.minute, wall.second));
  if (
    probe.getUTCFullYear() !== wall.year ||
    probe.getUTCMonth() !== wall.month - 1 ||
    probe.getUTCDate() !== wall.day ||
    probe.getUTCHours() !== wall.hour ||
    probe.getUTCMinutes() !== wall.minute
  )
    return null;
  return wall;
}

/** Offset of a zone, in milliseconds east of UTC, at a given instant. */
export function zoneOffsetMs(utcMs: number, timeZone: string): number {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const parts = formatter.formatToParts(new Date(utcMs));
  const pick = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  const asUtc = Date.UTC(pick("year"), pick("month") - 1, pick("day"), pick("hour"), pick("minute"), pick("second"));
  return asUtc - Math.floor(utcMs / 1000) * 1000;
}

function wallInZone(utcMs: number, timeZone: string): string {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  const parts = formatter.formatToParts(new Date(utcMs));
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${pick("year")}-${pick("month")}-${pick("day")}T${pick("hour")}:${pick("minute")}`;
}

/** The wall clock of a naive wall-clock timestamp, as the input spells it. */
function wallLabel(naiveMs: number): string {
  const date = new Date(naiveMs);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

/**
 * The instant whose wall clock in `timeZone` is `naiveMs`.
 *
 * Offsets change at transitions, so the first answer is only a guess: subtract
 * the offset observed at the guessed instant until it stops moving.
 */
function solveWall(naiveMs: number, timeZone: string): number {
  let instant = naiveMs;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const next = naiveMs - zoneOffsetMs(instant, timeZone);
    if (next === instant) break;
    instant = next;
  }
  return instant;
}

/**
 * Convert a wall clock in a zone to an instant.
 * Returns null for an unparseable value or an unknown zone.
 */
export function zonedWallToUtc(wall: string, timeZone: string): { iso: string; shifted: boolean } | null {
  const parsed = parseWall(wall);
  if (!parsed || !timeZone) return null;
  try {
    // Walk the wall clock forward, one minute at a time, until the zone can
    // represent it. The first candidate is the common case; the loop only runs
    // for the spring-forward gap, where an hour of labels does not exist.
    const naive = Date.UTC(parsed.year, parsed.month - 1, parsed.day, parsed.hour, parsed.minute, parsed.second);
    for (let minute = 0; minute <= 180; minute += 1) {
      const candidate = naive + minute * 60000;
      const instant = solveWall(candidate, timeZone);
      if (wallInZone(instant, timeZone) === wallLabel(candidate))
        return { iso: new Date(instant).toISOString(), shifted: minute > 0 };
    }
    return null;
  } catch {
    // An unknown zone throws a RangeError from Intl.
    return null;
  }
}

/** "09:00" for an ISO instant in a zone. */
export function wallTimeOf(iso: string, timeZone: string): string {
  try {
    return wallInZone(Date.parse(iso), timeZone).slice(11);
  } catch {
    return iso.slice(11, 16);
  }
}

/** "2026-10-25T09:00" for a datetime-local input, in the given zone. */
export function wallInputOf(iso: string, timeZone: string): string {
  try {
    return wallInZone(Date.parse(iso), timeZone);
  } catch {
    return new Date(iso).toISOString().slice(0, 16);
  }
}

/** A human-readable time in the series' zone, with its abbreviation. */
export function describeInZone(iso: string, timeZone?: string | null, locale?: string): string {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "Time unavailable";
  if (!timeZone) return date.toLocaleString(locale);
  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone,
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(date);
  } catch {
    return date.toLocaleString(locale);
  }
}

/**
 * The next occurrence of a daily or weekly wall clock, strictly after `now`.
 * Used for the "next run" line before the post is queued.
 */
export function nextSeriesRun(
  wall: string,
  timeZone: string,
  repeat: "daily" | "weekly",
  now: number = Date.now(),
): { iso: string; shifted: boolean } | null {
  const parsed = parseWall(wall);
  if (!parsed) return null;
  const step = repeat === "daily" ? 86400000 : 7 * 86400000;
  const base = Date.UTC(parsed.year, parsed.month - 1, parsed.day);
  for (let hop = 0; hop < 400; hop += 1) {
    const date = new Date(base + hop * step).toISOString().slice(0, 10);
    const candidate = zonedWallToUtc(`${date}T${String(parsed.hour).padStart(2, "0")}:${String(parsed.minute).padStart(2, "0")}`, timeZone);
    if (candidate && Date.parse(candidate.iso) > now) return candidate;
  }
  return null;
}
