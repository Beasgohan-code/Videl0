import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import ts from "typescript";

async function routes(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const found = await Promise.all(entries.map(async (entry) => {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) return routes(full);
    return entry.name === "route.ts" ? [full] : [];
  }));
  return found.flat();
}

test("every API route declares its owner/player guard or explicit public auth boundary", async () => {
  const root = path.join(process.cwd(), "src", "app", "api");
  const files = await routes(root);
  assert.ok(files.length >= 40, "route inventory should notice a missing API tree");
  const unguarded: string[] = [];
  for (const file of files) {
    const source = await readFile(file, "utf8");
    const relative = path.relative(root, file).replaceAll(path.sep, "/");
    const parsed = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
    const handlers = parsed.statements.filter((statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement) &&
      statement.name !== undefined &&
      ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"].includes(statement.name.text) &&
      Boolean(statement.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword)), 
    );
    if (relative === "auth/route.ts") {
      const byMethod = new Map(handlers.map((handler) => [handler.name!.text, handler.body?.getText(parsed) || ""]));
      assert.match(byMethod.get("POST") || "", /crossSiteRequest\(req\)/, "auth writes must reject cross-site requests");
      assert.match(byMethod.get("DELETE") || "", /crossSiteRequest\(req\)/, "logout must reject cross-site requests");
      assert.match(byMethod.get("GET") || "", /validOwnerCookie\(req\)/, "auth status must validate the signed owner cookie");
      continue;
    }
    if (relative === "session/route.ts") {
      const byMethod = new Map(handlers.map((handler) => [handler.name!.text, handler.body?.getText(parsed) || ""]));
      assert.match(byMethod.get("GET") || "", /playerRequired\(req\)/, "session status must verify its signed player cookie");
      assert.match(byMethod.get("POST") || "", /crossSite\(req\)/, "session creation must reject cross-site requests");
      assert.match(byMethod.get("DELETE") || "", /crossSite\(req\)/, "session logout must reject cross-site requests");
      continue;
    }
    for (const handler of handlers) {
      const body = handler.body?.getText(parsed) || "";
      if (!/ownerRequired\(req\)|playerRequired\(req\)/.test(body))
        unguarded.push(`${relative}#${handler.name?.text || "unknown"}`);
    }
    // Aliased exports share one helper (for example schedules); require the helper
    // itself to enforce a session rather than trusting that the route imports it.
    if (!handlers.length && !/ownerRequired\(req\)|playerRequired\(req\)/.test(source))
      unguarded.push(relative);
  }
  assert.deepEqual(unguarded, [], `API routes without a declared access guard: ${unguarded.join(", ")}`);
});
