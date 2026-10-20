import test from "node:test";
import assert from "node:assert/strict";
import { csvDocument } from "../src/lib/csv";
import { designLibrary } from "../src/lib/design-library";
import {
  designDocument,
  parseDesign,
  paintDesign,
} from "../src/lib/image-design";
test("CSV export quotes values and prevents spreadsheet formulas", () => {
  const csv = csvDocument([
    ["type", "label", "count"],
    ["chat", "-100123", 7],
    ["command", '=HYPERLINK("bad")', 2],
    ["line", "a,b\nvalue", 0],
  ]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes('"\'-100123"'));
  assert.ok(csv.includes('"\'=HYPERLINK(""bad"")"'));
  assert.ok(csv.includes('"a,b\nvalue"'));
  assert.ok(csv.includes('"0"'));
});
test("all eight layout recipes remain valid editable design documents", () => {
  assert.equal(designLibrary.length, 8);
  assert.equal(new Set(designLibrary.map((r) => r.id)).size, 8);
  for (const recipe of designLibrary)
    assert.deepEqual(
      parseDesign(JSON.parse(designDocument(recipe.design))),
      recipe.design,
    );
});
test("every pattern renders customized text with a canvas context", () => {
  for (const recipe of designLibrary) {
    const words: string[] = [];
    const ctx: any = {
      clearRect() {},
      fillRect() {},
      save() {},
      restore() {},
      beginPath() {},
      arc() {},
      stroke() {},
      fill() {},
      moveTo() {},
      lineTo() {},
      measureText: (s: string) => ({ width: s.length * 8 }),
      fillText: (s: string) => words.push(s),
    };
    paintDesign(ctx, recipe.design, null);
    assert.ok(words.length > 2, recipe.name);
  }
});
