import test from "node:test";
import assert from "node:assert/strict";
import { csvDocument } from "../src/lib/csv";
import { designLibrary } from "../src/lib/design-library";
import {
  designDocument,
  initialDesign,
  parseDesign,
  paintDesign,
} from "../src/lib/image-design";
import { parseBrandKits } from "../src/lib/studio-drafts";
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
test("all 20 layout recipes remain valid editable design documents", () => {
  assert.equal(designLibrary.length, 20);
  assert.equal(new Set(designLibrary.map((r) => r.id)).size, 20);
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

const LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

test("a design keeps a bounded logo and a printable footer", () => {
  const parsed = parseDesign({ ...initialDesign, logoData: LOGO, logoCorner: "br", footer: "  @videl  " });
  assert.equal(parsed.logoData, LOGO);
  assert.equal(parsed.logoCorner, "br");
  assert.equal(parsed.footer, "  @videl  ");
});

test("a design ignores remote logos, oversized data and control characters", () => {
  assert.equal(parseDesign({ ...initialDesign, logoData: "https://example.com/logo.png" }).logoData, "");
  assert.equal(parseDesign({ ...initialDesign, logoData: `data:image/png;base64,${"A".repeat(300001)}` }).logoData, "");
  assert.equal(parseDesign({ ...initialDesign, footer: "safe\u0007text" }).footer, "");
  assert.equal(parseDesign({ ...initialDesign, logoCorner: "middle" }).logoCorner, "tl");
});

test("brand kits keep the logo, corner and footer they were saved with", () => {
  const [kit] = parseBrandKits([
    { id: "k1", name: "Team", background: "#101010", accent: "#202020", color: "#ffffff",
      font: "Arial", logoData: LOGO, logoCorner: "bl", footer: "videl.studio" },
  ]);
  assert.equal(kit.logoData, LOGO);
  assert.equal(kit.logoCorner, "bl");
  assert.equal(kit.footer, "videl.studio");
  const [clean] = parseBrandKits([
    { id: "k2", name: "No logo", background: "#101010", accent: "#202020", color: "#ffffff",
      font: "Arial", logoData: "javascript:alert(1)", logoCorner: "x" },
  ]);
  assert.equal(clean.logoData, undefined);
  assert.equal(clean.logoCorner, undefined);
});

test("the footer and logo are painted onto the export canvas", () => {
  const words: string[] = [];
  let drawn = 0;
  const ctx: any = {
    clearRect() {}, fillRect() {}, save() {}, restore() {}, beginPath() {}, arc() {},
    stroke() {}, fill() {}, moveTo() {}, lineTo() {},
    measureText: (s: string) => ({ width: s.length * 8 }),
    fillText: (s: string) => words.push(s),
    drawImage: () => { drawn += 1; },
  };
  const logo = { naturalWidth: 64, naturalHeight: 64 } as unknown as HTMLImageElement;
  paintDesign(ctx, { ...initialDesign, logoData: LOGO, footer: "videl.studio" }, null, logo);
  assert.equal(drawn, 1);
  assert.ok(words.includes("videl.studio"));
});
