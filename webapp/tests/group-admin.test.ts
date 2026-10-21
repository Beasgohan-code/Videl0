import test from "node:test";
import assert from "node:assert/strict";
import {
  BULK_LIMIT,
  SETTING_KEYS,
  PROTECTION_GROUPS,
  applySettings,
  applySettingsToChats,
  bulkSelection,
  conflictMessage,
  displayTitle,
  effectiveGuards,
  errorHint,
  filterGroup,
  flag,
  matchesQuery,
  memberLabel,
  protectionSummary,
  nextRevision,
  toggleSelected,
  visibleGroups,
  type Group,
} from "../src/lib/group-admin";
import { isSettingPatch, parseChatId, validBulk } from "../src/lib/group-backend";

const group = (overrides: Partial<Group> = {}): Group => ({
  id: -1001,
  title: "Alpha",
  type: "supergroup",
  members: 10,
  available: true,
  settings: {},
  counts: { warns: 0, notes: 0, blacklist: 0, approved: 0 },
  ...overrides,
});

test("only settings the bot enforces are offered", () => {
  assert.equal(SETTING_KEYS.length, 21);
  assert.ok(SETTING_KEYS.includes("lock_links"));
  assert.ok(SETTING_KEYS.includes("captcha_enabled"));
  assert.ok(SETTING_KEYS.includes("welcome_enabled"));
  assert.equal(new Set(SETTING_KEYS).size, SETTING_KEYS.length);
  // No duplicate control wired to two switches.
  const declared = PROTECTION_GROUPS.flatMap((entry) => entry.controls.map((control) => control.key));
  assert.deepEqual([...declared].sort(), [...SETTING_KEYS].sort());
});

test("missing settings fall back to the bot's own defaults", () => {
  assert.equal(flag({}, "welcome_enabled"), true, "the bot greets unless told otherwise");
  assert.equal(flag({}, "lock_links"), false);
  assert.equal(flag({ welcome_enabled: "false" }, "welcome_enabled"), false);
  assert.equal(flag({ antispam: 1 }, "antispam"), true);
});

test("protection summary counts what the owner saved, not the defaults", () => {
  assert.deepEqual(protectionSummary({}), { active: 0, total: 21 });
  assert.equal(protectionSummary({ lock_links: true, antispam: true }).active, 2);
  assert.equal(protectionSummary({ lock_links: "true", antispam: 1 }).active, 2);
  assert.equal(protectionSummary({ lock_links: false }).active, 0);
  assert.equal(effectiveGuards({}), 1, "welcomes are on by default");
});

test("search, filter and sort only present real groups", () => {
  const items = [
    group({ id: -1, title: "Bravo", members: 50, settings: { lock_links: true }, counts: { warns: 2, notes: 0, blacklist: 0, approved: 0 } }),
    group({ id: -2, title: "Alpha", members: 5, settings: {}, counts: { warns: 0, notes: 0, blacklist: 0, approved: 0 } }),
    group({ id: -3, title: "Charlie", members: null, available: false }),
  ];
  assert.equal(visibleGroups(items, { query: "", filter: "all", sort: "name" })[0].title, "Alpha");
  assert.equal(visibleGroups(items, { query: "-3", filter: "all", sort: "name" })[0].title, "Charlie");
  assert.deepEqual(visibleGroups(items, { query: "", filter: "protected", sort: "name" }).map((item) => item.title), ["Bravo"]);
  assert.deepEqual(visibleGroups(items, { query: "", filter: "warns", sort: "name" }).map((item) => item.title), ["Bravo"]);
  assert.deepEqual(visibleGroups(items, { query: "", filter: "unavailable", sort: "name" }).map((item) => item.title), ["Charlie"]);
  assert.equal(visibleGroups(items, { query: "", filter: "all", sort: "members" })[0].title, "Bravo");
  assert.equal(filterGroup(items[2], "open"), true);
  assert.equal(filterGroup(items[0], "open"), false);
  assert.equal(matchesQuery(group({ username: "alpha_chat" }), "ALPHA_CHAT"), true);
});

test("selections are capped at the backend limit without silent truncation", () => {
  const ids = Array.from({ length: BULK_LIMIT + 3 }, (_, index) => -1000 - index);
  assert.deepEqual(bulkSelection(ids).ids.length, BULK_LIMIT);
  assert.equal(bulkSelection(ids).overflow, 3);
  assert.deepEqual(toggleSelected([-1], -2), [-1, -2]);
  assert.deepEqual(toggleSelected([-1, -2], -1), [-2]);
});

test("settings patches merge without mutating the previous rows", () => {
  const rows = [group({ id: -1 }), group({ id: -2 })];
  const patched = applySettingsToChats(rows, [-2], { lock_links: true });
  assert.equal(patched[0].settings.lock_links, undefined);
  assert.equal(patched[1].settings.lock_links, true);
  assert.equal(rows[1].settings.lock_links, undefined);
  assert.equal(applySettings(rows[0], { antispam: true }).settings.antispam, true);
});

test("titles and member labels stay honest", () => {
  assert.equal(displayTitle({ title: "  ", id: -9 }), "Telegram chat -9");
  assert.equal(memberLabel(null), "members unknown");
  assert.equal(memberLabel(1), "1 member");
  assert.equal(memberLabel(1200), "1,200 members");
});

test("chat IDs must be negative Telegram group IDs", () => {
  assert.equal(parseChatId("-100123"), -100123);
  assert.equal(parseChatId(-100123), -100123);
  for (const bad of [0, 42, "-0", "abc", null, undefined, NaN, 1.5, "-99999999999999999999"])
    assert.equal(parseChatId(bad), null);
});

test("setting patches reject unknown keys and non-booleans", () => {
  assert.equal(isSettingPatch({ lock_links: true }), true);
  assert.equal(isSettingPatch({ lock_links: "true" }), false);
  assert.equal(isSettingPatch({ made_up: true }), false);
  assert.equal(isSettingPatch({}), false);
  assert.equal(isSettingPatch([]), false);
});

test("bulk requests validate size, action and preset", () => {
  assert.deepEqual(validBulk({ chat_ids: ["-1", -2], action: "preset", preset: "strict" }), {
    chatIds: [-1, -2],
    action: "preset",
    preset: "strict",
  });
  assert.equal(validBulk({ chat_ids: [], action: "preset", preset: "strict" }), null);
  assert.equal(validBulk({ chat_ids: Array.from({ length: BULK_LIMIT + 1 }, (_, i) => -i - 1), action: "preset", preset: "strict" }), null);
  assert.equal(validBulk({ chat_ids: [-1], action: "preset", preset: "nuke" }), null);
  assert.equal(validBulk({ chat_ids: [-1], action: "delete" }), null);
  assert.equal(validBulk({ chat_ids: [1], action: "preset", preset: "strict" }), null);
});

test("errors explain what the owner can actually do", () => {
  assert.match(errorHint("nope", 501), /Render/);
  assert.match(errorHint("Choose a group already served by this bot."), /Add the bot/);
  assert.match(errorHint("Your account lacks the required group permission: can_delete_messages."), /permission/);
  assert.equal(errorHint("plain failure"), "plain failure");
});

test("a panel writes with the revision it read and adopts the next one", () => {
  assert.equal(nextRevision({ revision: 4 }, null), 4);
  assert.equal(nextRevision({ revision: 0 }, 7), 0);
  assert.equal(nextRevision({ revision: "4" }, 3), 3);
  assert.equal(nextRevision({ revision: -1 }, null), null);
  assert.equal(nextRevision({ revision: 1.5 }, null), null);
  assert.equal(nextRevision({}, 2), 2);
  assert.equal(nextRevision(null, null), null);
});

test("a conflict names the race and says the screen reloaded", () => {
  assert.match(conflictMessage(5), /changed this group \(revision 5\)/);
  assert.match(conflictMessage(5), /latest values are now shown/);
  assert.match(conflictMessage(undefined), /changed this group/);
  assert.doesNotMatch(conflictMessage("not a number"), /revision/);
});
