import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const addedGameArt = ["chess", "chinese", "dots", "gomoku", "yacht"];

test("new multiplayer game artwork is shipped as readable local JPEG assets", () => {
  for (const game of addedGameArt) {
    const path = join(process.cwd(), "public", "arcade", `${game}.jpg`);
    const bytes = readFileSync(path);
    assert.deepEqual([...bytes.subarray(0, 3)], [0xff, 0xd8, 0xff], `${game} is a JPEG`);
    assert.ok(statSync(path).size > 8_000, `${game} asset is not an empty placeholder`);
  }
});
