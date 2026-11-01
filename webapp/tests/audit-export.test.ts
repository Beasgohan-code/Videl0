import test from "node:test";
import assert from "node:assert/strict";
import { auditCsv } from "../src/lib/audit-export";

test("audit CSV is bounded, quotes values and removes actor identifiers", () => {
  const csv = auditCsv([
    { at: "2026-10-31T12:00:00Z", kind: "moderation", action: "member action", detail: 'Banned user 123456789 for "spam"', source: "web", actor: 987654321 },
  ]);
  assert.match(csv, /"timestamp","category","action","summary","source"/);
  assert.match(csv, /\[id\]/);
  assert.match(csv, /""spam""/);
  assert.doesNotMatch(csv, /987654321|123456789/);
});

test("audit CSV neutralizes spreadsheet formulas and caps the export at 40 events", () => {
  const csv = auditCsv(Array.from({ length: 45 }, (_, index) => ({
    at: "2026-10-31T12:00:00Z",
    kind: "settings",
    action: index === 0 ? "=HYPERLINK(\"https://example.invalid\")" : `change-${index}`,
    detail: "summary",
    source: "web",
  })));
  assert.match(csv, /'=HYPERLINK/);
  assert.equal(csv.split("\r\n").length, 41);
});
