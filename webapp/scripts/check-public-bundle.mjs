import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(".next/static");
const files = [];
async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) await walk(full);
    else if (/\.(?:js|css|json|map)$/.test(entry.name)) files.push(full);
  }
}
await walk(root);
if (!files.length) throw new Error("No public build assets found; run `next build` first.");

const secrets = [
  "BOT_TOKEN",
  "WEBAPP_SECRET",
  "MONGO_DB_URL",
  "INTERNAL_SECRET",
  "STRING_SESSION",
  "API_HASH",
  "ELDIAN_API_KEY",
]
  .map((key) => [key, process.env[key] || ""])
  .filter(([, value]) => value.length >= 8);
const credentialPatterns = [
  /mongodb(?:\+srv)?:\/\/[^\s"'<>/:]+:[^@\s"'<>/]+@/i,
  /\bbot\d{5,}:[A-Za-z0-9_-]{20,}\b/,
];
const leaks = [];
for (const file of files) {
  const contents = await readFile(file, "utf8");
  for (const [name, value] of secrets) {
    if (contents.includes(value)) leaks.push(`${path.relative(root, file)} contains ${name}`);
  }
  for (const pattern of credentialPatterns) {
    if (pattern.test(contents)) leaks.push(`${path.relative(root, file)} contains a credential-shaped value`);
  }
}
if (leaks.length) {
  console.error(leaks.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Scanned ${files.length} public assets: no configured secret values or credential-shaped strings found.`);
}
