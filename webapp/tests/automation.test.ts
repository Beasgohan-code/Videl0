import test from "node:test";
import assert from "node:assert/strict";
import {
  WINDOW_LOCKS,
  attentionQueue,
  auditLabel,
  escalationSummary,
  explicitSettings,
  filterGroup,
  healthTone,
  protectionNow,
  protectionSummary,
  quietNow,
  quietSummary,
  sortGroups,
  visibleGroups,
  windowSummary,
  zoneLabel,
  type Group,
  type ProtectionWindow,
} from "../src/lib/group-admin";
import {
  backendRevision,
  buildReleaseCheck,
  compareRevisions,
  driftLabel,
  webRevision,
} from "../src/lib/release";
import { GET as auditGET } from "../src/app/api/groups/[id]/audit/route";
import { GET as federationGET } from "../src/app/api/federation/route";
import { POST as federationPOST } from "../src/app/api/federation/[id]/route";
import { GET as versionGET } from "../src/app/api/version/route";
import { POST as retryPOST } from "../src/app/api/schedules/retry/route";

const group = (overrides: Partial<Group> = {}): Group => ({
  id: -1001,
  title: "Alpha",
  type: "supergroup",
  members: 10,
  available: true,
  settings: {},
  ...overrides,
});

// ── quiet hours ─────────────────────────────────────────────────────────────

const quiet = (start: string, end: string, extra: Partial<{ enabled: boolean; tz_offset: number }> = {}) => ({
  enabled: true,
  start,
  end,
  tz_offset: 0,
  ...extra,
});

test("quiet hours match inside a same-day window and not outside it", () => {
  const window = quiet("09:00", "17:00");
  assert.equal(quietNow(window, new Date("2026-05-01T12:00:00Z")), true);
  assert.equal(quietNow(window, new Date("2026-05-01T08:59:00Z")), false);
  assert.equal(quietNow(window, new Date("2026-05-01T17:00:00Z")), false, "the end is exclusive");
});

test("quiet hours wrap past midnight", () => {
  const window = quiet("22:00", "07:00");
  assert.equal(quietNow(window, new Date("2026-05-01T23:30:00Z")), true);
  assert.equal(quietNow(window, new Date("2026-05-01T03:00:00Z")), true);
  assert.equal(quietNow(window, new Date("2026-05-01T12:00:00Z")), false);
});

test("quiet hours honour the stored offset instead of the browser clock", () => {
  const window = quiet("22:00", "07:00", { tz_offset: 330 }); // IST
  assert.equal(quietNow(window, new Date("2026-05-01T17:00:00Z")), true, "17:00 UTC is 22:30 IST");
  assert.equal(quietNow(window, new Date("2026-05-01T14:00:00Z")), false, "14:00 UTC is 19:30 IST");
});

test("a disabled or equal-bounds window never matches", () => {
  assert.equal(quietNow({ ...quiet("22:00", "07:00"), enabled: false }, new Date("2026-05-01T23:00:00Z")), false);
  assert.equal(quietNow(quiet("22:00", "22:00"), new Date("2026-05-01T23:00:00Z")), false);
});

test("quiet summaries name the window and zone", () => {
  assert.equal(quietSummary({ enabled: false, start: "22:00", end: "07:00", tz_offset: 0 }), "Quiet hours are off.");
  const text = quietSummary(quiet("22:00", "07:00", { tz_offset: 330 }));
  assert.match(text, /22:00–07:00/);
  assert.match(text, /UTC\+05:30/);
  assert.equal(zoneLabel(-300), "UTC-05:00");
  assert.equal(zoneLabel(0), "UTC+00:00");
});

test("escalation summaries describe the action that will run", () => {
  assert.equal(escalationSummary({ enabled: false, action: "ban", mute_hours: 6 }), "No automatic restriction.");
  assert.equal(escalationSummary({ enabled: true, action: "none", mute_hours: 6 }), "No automatic restriction.");
  assert.match(escalationSummary({ enabled: true, action: "mute", mute_hours: 12 }), /12h/);
  assert.match(escalationSummary({ enabled: true, action: "kick", mute_hours: 6 }), /Remove/);
  assert.match(escalationSummary({ enabled: true, action: "ban", mute_hours: 6 }), /Ban/);
});

// ── protection counting ────────────────────────────────────────────────────

test("stored values win over defaults when counting protection", () => {
  const filled = { welcome_enabled: true, lock_links: false };
  assert.equal(protectionSummary(filled, {}).active, 0, "a group that saved nothing is not protected");
  assert.equal(protectionSummary(filled, { lock_links: true }).active, 1);
  assert.equal(protectionSummary(filled).active, 1, "without a stored view, fall back to the payload");
});

test("explicitSettings prefers the stored map", () => {
  assert.deepEqual(explicitSettings(group({ settings: { a: true }, explicit: { b: true } })), { b: true });
  assert.deepEqual(explicitSettings(group({ settings: { a: true } })), { a: true });
});

// ── health, filters and sorting ────────────────────────────────────────────

test("attention filter and health sort put the worst groups first", () => {
  const rows = [
    group({ id: -1, title: "Good", health: { score: 95, issues: [], attention: false } }),
    group({ id: -2, title: "Bad", health: { score: 40, issues: [{ code: "x", message: "y" }], attention: true } }),
    group({ id: -3, title: "Okay", health: { score: 72, issues: [], attention: false } }),
  ];
  assert.deepEqual(
    visibleGroups(rows, { query: "", filter: "attention", sort: "health" }).map((row) => row.title),
    ["Bad"],
  );
  assert.deepEqual(
    sortGroups(rows, "health").map((row) => row.title),
    ["Bad", "Okay", "Good"],
  );
  assert.equal(filterGroup(group({ health: { score: 60, issues: [], attention: false } }), "attention"), false);
});

test("health tone thresholds are stable", () => {
  assert.equal(healthTone(100), "good");
  assert.equal(healthTone(85), "good");
  assert.equal(healthTone(84), "watch");
  assert.equal(healthTone(70), "watch");
  assert.equal(healthTone(69), "poor");
});

test("audit labels are readable and never empty", () => {
  const base = { action: "x", detail: "", actor: null, source: "web", at: null };
  assert.equal(auditLabel({ ...base, kind: "preset" }), "Preset applied");
  assert.equal(auditLabel({ ...base, kind: "join_request" }), "Join request reviewed");
  assert.equal(auditLabel({ ...base, kind: "some_new_kind" }), "some new kind");
});

// ── release drift ──────────────────────────────────────────────────────────

test("revisions are normalised without inventing a commit", () => {
  assert.equal(webRevision("A1B2C3D4E5"), "a1b2c3d");
  assert.equal(webRevision(undefined), "local");
  assert.equal(webRevision("not-a-sha"), "local");
  assert.equal(backendRevision("deadbeef1234"), "deadbee");
  assert.equal(backendRevision("nope"), null);
  assert.equal(backendRevision(42), null);
});

test("drift is only claimed when both revisions are known", () => {
  assert.equal(compareRevisions("abc1234", "abc1234"), "same");
  assert.equal(compareRevisions("abc1234", "def5678"), "different");
  assert.equal(compareRevisions("abc1234", null), "unknown");
  assert.equal(compareRevisions("local", "abc1234"), "unknown");
});

test("release hints say which deployment is behind", () => {
  const drifted = buildReleaseCheck({ web: "abc1234", backend: "def5678", status: "ok", latencyMs: 90, checkedAt: "2026-05-01T00:00:00Z" });
  assert.equal(driftLabel(drifted), "Drifted");
  assert.match(drifted.hint, /different commits/);
  const same = buildReleaseCheck({ web: "abc1234", backend: "abc1234", status: "ok", latencyMs: 90, checkedAt: "2026-05-01T00:00:00Z" });
  assert.equal(driftLabel(same), "In sync");
  assert.equal(same.p95Ms, null, "no measurement is not zero");
  assert.equal(buildReleaseCheck({ web: "abc1234", backend: "abc1234", status: "ok", latencyMs: 90, p95Ms: 42.5, checkedAt: "2026-05-01T00:00:00Z" }).p95Ms, 42.5);
  const unknown = buildReleaseCheck({ web: "abc1234", backend: null, status: "ok", latencyMs: 50, checkedAt: "2026-05-01T00:00:00Z" });
  assert.equal(driftLabel(unknown), "Revision unknown");
  const missing = buildReleaseCheck({ web: "local", backend: null, status: "not_configured", latencyMs: null, checkedAt: "2026-05-01T00:00:00Z" });
  assert.equal(driftLabel(missing), "Backend not configured");
});

// ── route guards ───────────────────────────────────────────────────────────

test("new owner routes reject unauthenticated requests before touching the backend", async () => {
  const audit = await auditGET(new Request("https://studio.example/api/groups/-1001/audit"), {
    params: Promise.resolve({ id: "-1001" }),
  });
  assert.equal(audit.status, 401);
  assert.equal((await federationGET(new Request("https://studio.example/api/federation"))).status, 401);
  assert.equal(
    (await federationPOST(new Request("https://studio.example/api/federation/fed1", { method: "POST" }), {
      params: Promise.resolve({ id: "fed1" }),
    })).status,
    401,
  );
  assert.equal((await versionGET(new Request("https://studio.example/api/version"))).status, 401);
  assert.equal(
    (await retryPOST(new Request("https://studio.example/api/schedules/retry", { method: "POST" }))).status,
    401,
  );
});

// ── CSV export ─────────────────────────────────────────────────────────────

test("audit export quotes cells and neutralises spreadsheet formulas", async () => {
  const { csvDocument } = await import("../src/lib/csv");
  const output = csvDocument([
    ["When", "Change"],
    ["2026-05-01T00:00:00Z", "=SUM(A1)"],
    ["2026-05-01T00:01:00Z", 'say "hi"'],
  ]);
  assert.match(output, /^\uFEFF"When","Change"/);
  assert.match(output, /"'=SUM\(A1\)"/);
  assert.match(output, /"say ""hi"""/);
});

// ── scheduled protection windows ───────────────────────────────────────────

const protection = (overrides: Partial<ProtectionWindow> = {}): ProtectionWindow => ({
  enabled: true,
  start: "22:00",
  end: "07:00",
  locks: ["lock_links", "lock_media"],
  state: { active: false, applied: [], since: null },
  ...overrides,
});

test("a protection window uses the same wrapping and offset rules as quiet hours", () => {
  assert.equal(protectionNow(protection(), 0, new Date("2026-05-01T23:30:00Z")), true);
  assert.equal(protectionNow(protection(), 0, new Date("2026-05-01T12:00:00Z")), false);
  assert.equal(protectionNow(protection({ enabled: false }), 0, new Date("2026-05-01T23:30:00Z")), false);
  assert.equal(protectionNow(protection({ start: "22:00", end: "22:00" }), 0, new Date("2026-05-01T23:30:00Z")), false);
  // 17:00 UTC is 22:30 in IST.
  assert.equal(protectionNow(protection(), 330, new Date("2026-05-01T17:00:00Z")), true);
});

test("protection summaries never imply locks that were not picked", () => {
  assert.equal(windowSummary(protection({ locks: [] }), 0), "No locks picked yet.");
  assert.match(windowSummary(protection({ enabled: false }), 0), /2 locks ready/);
  const on = windowSummary(protection(), 330);
  assert.match(on, /22:00–07:00/);
  assert.match(on, /UTC\+05:30/);
});

test("only real lock keys are offered to a window", () => {
  assert.ok(WINDOW_LOCKS.length >= 15);
  assert.ok(WINDOW_LOCKS.every((lock) => lock.key.startsWith("lock_")));
  assert.ok(WINDOW_LOCKS.some((lock) => lock.key === "lock_links"));
  assert.ok(!WINDOW_LOCKS.some((lock) => lock.key === "antispam"));
});

test("the attention queue ranks the worst groups and stays short", () => {
  const rows = [
    group({ id: -1, title: "Fine", health: { score: 100, issues: [], attention: false } }),
    group({ id: -2, title: "Worse", health: { score: 40, issues: [{ code: "a", message: "Bot removed" }], attention: true } }),
    group({ id: -3, title: "Bad", health: { score: 60, issues: [{ code: "b", message: "No locks" }], attention: true } }),
  ];
  assert.deepEqual(attentionQueue(rows).map((row) => row.title), ["Worse", "Bad"]);
  assert.deepEqual(attentionQueue(rows, 1).map((row) => row.title), ["Worse"]);
  assert.deepEqual(attentionQueue([]), []);
});

test("the waiting-on-you filter matches both inbox queues", () => {
  const base = { warns: 0, notes: 0, blacklist: 0, approved: 0 };
  const rows = [
    group({ id: -1, counts: { ...base, pending_joins: 2 } }),
    group({ id: -2, counts: { ...base, reports: 1 } }),
    group({ id: -3, counts: { ...base, reports: 0, pending_joins: 0 } }),
    group({ id: -4, counts: base }),
  ];
  assert.deepEqual(rows.filter((row) => filterGroup(row, "inbox")).map((row) => row.id), [-1, -2]);
  assert.equal(filterGroup(group({ counts: { ...base, reports: undefined } }), "inbox"), false);
});
