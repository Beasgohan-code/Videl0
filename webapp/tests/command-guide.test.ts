import test from "node:test";
import assert from "node:assert/strict";
import {
  BOT_COMMANDS,
  COMMAND_CATEGORIES,
  COMMAND_CONTEXTS,
  COMMAND_COUNT,
} from "../src/lib/commands";
import { canOpenSection } from "../src/lib/access";

test("the published guide covers every registered command exactly once", () => {
  assert.equal(COMMAND_COUNT, BOT_COMMANDS.length);
  assert.ok(COMMAND_COUNT >= 150, `expected the full catalogue, got ${COMMAND_COUNT}`);
  const names = BOT_COMMANDS.map((command) => command.name);
  assert.equal(new Set(names).size, names.length);
  for (const command of BOT_COMMANDS) {
    assert.match(command.name, /^[a-z0-9]+$/);
    assert.ok(command.summary.trim().length > 2, `${command.name} needs a summary`);
    assert.ok(command.usage.startsWith(`/${command.name}`));
    assert.ok(command.category in COMMAND_CATEGORIES);
    assert.ok(command.context in COMMAND_CONTEXTS);
  }
});

test("essential bot commands are documented", () => {
  const documented = new Set(BOT_COMMANDS.map((command) => command.name));
  for (const name of [
    "start",
    "help",
    "commands",
    "afk",
    "back",
    "remind",
    "warn",
    "ban",
    "kick",
    "lock",
    "notes",
    "save",
    "get",
    "welcome",
    "rules",
    "play",
    "pause",
    "skip",
    "queue",
    "stats",
    "kang",
    "font",
    "hug",
    "kiss",
  ])
    assert.ok(documented.has(name), `missing /${name}`);
});

test("legacy docstrings are replaced with readable copy", () => {
  const byName = new Map(BOT_COMMANDS.map((command) => [command.name, command.summary]));
  assert.equal(byName.get("addblacklist"), "Add a user to the anti-spam blocklist");
  assert.equal(byName.get("pause"), "Pause playback");
  for (const summary of byName.values()) assert.doesNotMatch(summary, /^(Addbl|Blmode|Fpromote|Bassoff)$/);
});

test("owner operations are marked and the guide is public to preview", () => {
  const owner = BOT_COMMANDS.filter((command) => command.owner);
  assert.ok(owner.length >= 5);
  assert.ok(owner.every((command) => command.category === "owner"));
  assert.equal(canOpenSection("guide", null), true);
  assert.equal(canOpenSection("guide", false), true);
});
