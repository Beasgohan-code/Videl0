import test from "node:test";
import assert from "node:assert/strict";
import {
  BACKUP_FORMAT,
  BACKUP_MAX_BYTES,
  backupChanges,
  backupFileName,
  backupIsEmpty,
  backupSummary,
  parseBackupFile,
} from "../src/lib/group-backup";

const valid = () => ({
  format: BACKUP_FORMAT,
  version: 1,
  exported_at: "2026-10-20T10:00:00Z",
  group: { id: -1001, title: "Alpha" },
  settings: { lock_links: true, warn_threshold: 3 },
  automation: { quiet_hours: {}, escalation: {}, protection: {} },
  blacklist: [{ trigger: "spam", mode: "del" }],
  commands_disabled: ["music"],
});

test("a backup written by the bot parses, wrapped or bare", () => {
  const bare = parseBackupFile(JSON.stringify(valid()));
  assert.equal(bare.ok, true);
  const wrapped = parseBackupFile(JSON.stringify({ ok: true, backup: valid() }));
  assert.equal(wrapped.ok, true);
});

test("foreign, future or malformed files are refused with a reason", () => {
  for (const [text, pattern] of [
    ["not json", /valid JSON/],
    ["[]", /JSON object/],
    [JSON.stringify({ format: "other" }), /not a Videl group backup/],
    [JSON.stringify({ format: BACKUP_FORMAT, version: 9, settings: {} }), /cannot be imported/],
    [JSON.stringify({ format: BACKUP_FORMAT, version: 1 }), /no settings block/],
  ] as [string, RegExp][]) {
    const result = parseBackupFile(text);
    assert.equal(result.ok, false);
    if (!result.ok) assert.match(result.error, pattern);
  }
});

test("an oversized file is refused before it is parsed", () => {
  const huge = "x".repeat(BACKUP_MAX_BYTES + 1);
  const result = parseBackupFile(huge);
  assert.equal(result.ok, false);
  if (!result.ok) assert.match(result.error, /larger than 256 KB/);
});

test("the preview counts changes and never invents any", () => {
  const changes = backupChanges({
    settings: { before: { lock_links: true }, after: { lock_links: false, lock_photos: true } },
    automation: ["protection"],
    blacklist: { add: ["new"], remove: [] },
    commands: { disable: [], enable: ["music"] },
  });
  assert.equal(backupIsEmpty(changes), false);
  const rows = backupSummary(changes);
  assert.deepEqual(rows.map((row) => row.label), ["2 settings change", "Automation", "Blacklist", "Commands"]);
  assert.match(rows[0].detail, /links off/);
  assert.match(rows[0].detail, /photos on/);
  assert.match(rows[2].detail, /\+1 word/);
  assert.match(rows[3].detail, /1 switched back on/);
});

test("an identical file reports nothing to apply", () => {
  assert.equal(backupIsEmpty(backupChanges({})), true);
  assert.equal(backupIsEmpty(backupChanges({ settings: { before: {}, after: {} } })), true);
  assert.deepEqual(backupSummary(backupChanges(undefined)), []);
});

test("changes tolerate a backend that sends partial blocks", () => {
  const changes = backupChanges({ settings: { after: { lock_links: "weird" } }, blacklist: { add: "not-a-list" } });
  assert.deepEqual(changes.settings.after, { lock_links: "weird" });
  assert.deepEqual(changes.blacklist.add, []);
  assert.deepEqual(changes.automation, []);
});

test("the download name carries the group and the day", () => {
  assert.equal(backupFileName(-1001234567, new Date("2026-10-20T22:00:00Z")), "videl-group--1001234567-2026-10-20.json");
});
