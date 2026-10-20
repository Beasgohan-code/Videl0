const { chromium: playwright } = require("playwright-core");
const os = require("node:os");
const path = require("node:path");
const artifacts = path.join(os.tmpdir(), "videl-studio-smoke");
const base = process.env.QA_BASE_URL || "http://localhost:3001";
const fs = require("node:fs/promises");
const assert = require("node:assert/strict");
(async () => {
  await fs.mkdir(artifacts, { recursive: true });
  const browser = await playwright.launch({
    args: ["--no-sandbox"],
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
  });
  const errors = [];
  page.on("pageerror", (e) => {
    errors.push(e.message);
    console.log("RUNTIME", e.message);
  });
  let sent = 0;
  let summaryError = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body =
      path === "/api/summary" && summaryError
        ? { ok: false, error: "Summary temporarily offline" }
        : path === "/api/summary"
          ? {
              ok: true,
              stats: { chats: 14, users: 15, plays: 72, uptime: 600 },
              measured_at: new Date().toISOString(),
            }
          : path === "/api/health"
            ? { status: "ok", bot_status: "online" }
            : path === "/api/channel"
              ? { ok: true, message_id: ++sent, chat_id: "@offline_test" }
              : { ok: false, error: "Offline browser test; not authenticated" };
    await route.fulfill({
      status: body.ok === false ? (path === "/api/summary" ? 503 : 401) : 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  await page.goto(base);
  await page.getByText("Bot online", { exact: true }).waitFor();
  await page.getByText("72", { exact: true }).waitFor();
  summaryError = true;
  await page.getByRole("button", { name: "Refresh now", exact: true }).click();
  await page
    .getByText(/Showing the last successful snapshot, not current totals/)
    .waitFor();
  assert.equal(await page.getByText("72", { exact: true }).count(), 1);
  summaryError = false;
  await page.goto(`${base}/?tab=post`);
  await page.getByRole("button", { name: "Design Image", exact: true }).click();
  await page
    .getByLabel("Heading", { exact: true })
    .fill("A design you can edit");
  await page.getByLabel("Small label", { exact: true }).fill("BROWSER CHECK");
  await page.getByLabel("Supporting text size", { exact: true }).fill("42");
  await page.getByRole("button", { name: "Label", exact: true }).click();
  const canvas = page.locator("canvas");
  await canvas.focus();
  await canvas.press("ArrowRight");
  await page.waitForFunction(
    () =>
      JSON.parse(localStorage.getItem("videl_image_design_v1") || "{}").design
        ?.labelX === 9,
  );
  let downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PNG", exact: true }).click();
  let download = await downloadPromise;
  await download.saveAs(path.join(artifacts, "export.png"));
  const png = await fs.readFile(path.join(artifacts, "export.png"));
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 675);
  downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Save editable design", exact: true })
    .click();
  download = await downloadPromise;
  await download.saveAs(path.join(artifacts, "design.json"));
  const doc = JSON.parse(
    await fs.readFile(path.join(artifacts, "design.json"), "utf8"),
  );
  assert.equal(doc.design.title, "A design you can edit");
  assert.equal(doc.design.subtitleSize, 42);
  assert.equal(doc.design.labelX, 9);
  await page.getByLabel("Heading", { exact: true }).fill("Temporary change");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .locator('input[accept=".json,application/json"]')
    .setInputFiles(path.join(artifacts, "design.json"));
  await page.waitForFunction(
    () =>
      document.querySelector('textarea[aria-label="Heading"]')?.value ===
      "A design you can edit",
  );
  await page
    .getByRole("button", { name: "Use image in post", exact: true })
    .click();
  await page.getByLabel("Channel or chat ID").fill("@offline_test");
  await page.locator(".visual-post-editor").fill("A safe offline test post");
  await page.getByRole("checkbox", { name: /I reviewed/ }).check();
  await page.getByRole("button", { name: "Publish post", exact: true }).click();
  await page.getByText(/Telegram accepted the post/).waitFor();
  assert.equal(sent, 1);
  await page.getByRole("checkbox", { name: /I reviewed/ }).check();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Publish post", exact: true }).click();
  assert.equal(sent, 1, "Duplicate confirmation cancellation must not send");
  await page.locator(".visual-post-editor").fill("x".repeat(1025));
  assert.equal(
    await page
      .getByRole("button", { name: "Publish post", exact: true })
      .isDisabled(),
    true,
  );
  await page.locator(".visual-post-editor").fill("A safe offline test post");
  await page.getByRole("button", { name: "Remove image", exact: true }).click();
  await page.waitForFunction(() =>
    JSON.parse(
      localStorage.getItem("videl_post_recovery_v1") || "{}",
    ).text?.includes("offline test"),
  );
  await page.reload();
  await page
    .getByRole("button", { name: "Create Post", exact: true })
    .first()
    .waitFor();
  // Reload resets to Home; reopen Post through the persistent navigation.
  await page.goto(`${base}/?tab=post`);
  await page.getByText("Unfinished post found", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  assert.ok(
    (await page.locator(".visual-post-editor").innerText()).includes(
      "A safe offline test post",
    ),
  );
  await page.getByRole("button", { name: "Design Image", exact: true }).click();
  assert.equal(
    await page.getByLabel("Heading", { exact: true }).inputValue(),
    "A design you can edit",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
    "Mobile viewport must not overflow",
  );
  await page.screenshot({
    path: path.join(artifacts, "mobile.png"),
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  console.log(
    "PASS: real Chromium PNG export, editable JSON export, keyboard movement, JSON import, mocked image publish, duplicate guard, caption limit, post recovery, design restore, 390px mobile layout; no runtime errors.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
