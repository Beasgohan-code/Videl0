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
  let authMode = "guest",
    sessionActive = false,
    authPosts = 0;
  const signedFixture =
    "auth_date=123&user=%7B%22id%22%3A6265999542%7D&hash=offline-fixture";
  await page.route("https://telegram.org/**", (route) => route.abort());
  let sent = 0;
  const guestApiRequests = [];
  let summaryError = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (authMode === "guest" && path !== "/api/auth")
      guestApiRequests.push(path);
    if (path === "/api/auth" && authMode !== "guest") {
      if (route.request().method() === "POST") {
        assert.equal(route.request().postDataJSON().initData, signedFixture);
        authPosts++;
        if (authMode === "nonowner") {
          sessionActive = false;
          await route.fulfill({
            status: 403,
            contentType: "application/json",
            body: JSON.stringify({
              ok: false,
              owner: false,
              error: "Not the owner",
            }),
          });
          return;
        }
        if (authMode !== "blocked") sessionActive = true;
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            owner: true,
            user: { id: 6265999542, first_name: "Offline owner" },
          }),
        });
        return;
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ ok: sessionActive, owner: sessionActive }),
      });
      return;
    }
    if (
      authMode !== "guest" &&
      path !== "/api/summary" &&
      path !== "/api/health"
    ) {
      const data =
        path === "/api/channel"
          ? { ok: true, message_id: ++sent, chat_id: "@offline_test" }
          : path === "/api/stats"
            ? {
                ok: true,
                stats: {
                  users: 15,
                  chats: 14,
                  plays: 72,
                  database: "connected",
                  services: { user_session: true, mongo: true },
                },
              }
            : path === "/api/groups"
              ? {
                  ok: true,
                  chats: [
                    {
                      id: -100123,
                      title: "Offline community",
                      type: "supergroup",
                      members: 15,
                      available: true,
                      settings: { antispam: true },
                    },
                  ],
                }
              : path === "/api/analytics"
                ? {
                    ok: true,
                    window_hours: 24,
                    total_commands: 5,
                    series: [{ time: "10:00", commands: 5 }],
                    top_commands: [{ command: "play", count: 5 }],
                    top_chats: [{ id: "-100123", commands: 5 }],
                  }
                : path === "/api/bot-settings"
                  ? {
                      ok: true,
                      bot: {
                        first_name: "Offline bot",
                        username: "offline_bot",
                      },
                      commands: [],
                      webapp_url: base,
                      warnings: [],
                    }
                  : path === "/api/broadcast"
                    ? { ok: true, sent: 1, failed: 0, total: 1 }
                    : path === "/api/chat"
                      ? { ok: true, message_id: 31, via: "bot" }
                      : { ok: true };
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(data),
      });
      return;
    }
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
  await page
    .getByRole("heading", {
      name: "Make something worth sharing.",
      exact: true,
    })
    .waitFor();
  assert.equal(
    await page.getByRole("link", { name: "Bot Settings", exact: true }).count(),
    0,
  );
  assert.equal(await page.getByText("72", { exact: true }).count(), 0);
  await page.goto(`${base}/?tab=groups`);
  await page
    .getByRole("heading", {
      name: "Make something worth sharing.",
      exact: true,
    })
    .waitFor();
  await page.goto(`${base}/?tab=post`);
  await page
    .getByRole("heading", { name: "Post Studio", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Publish post", exact: true })
      .count(),
    0,
  );
  assert.equal(await page.getByLabel("Channel or chat ID").count(), 0);
  await page.goto(`${base}/?tab=tools`);
  await page
    .getByLabel("Your text", { exact: true })
    .fill("Hello #Creator #creator");
  await page.getByText("3 words", { exact: false }).waitFor();
  await page
    .getByLabel("Website URL", { exact: true })
    .fill("https://example.com/post");
  await page.getByLabel("Campaign", { exact: true }).fill("launch");
  assert.ok(
    (await page.getByLabel("Campaign URL").inputValue()).includes(
      "utm_campaign=launch",
    ),
  );
  assert.deepEqual(
    guestApiRequests,
    [],
    "Public tools must not request bot APIs",
  );
  authMode = "browser";
  sessionActive = true;
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
  authMode = "browser";
  sessionActive = true;
  await page.goto(`${base}/?tab=auth`);
  await page
    .getByRole("heading", { name: "Owner access verified", exact: true })
    .waitFor();
  authMode = "miniapp";
  sessionActive = false;
  await page.goto(
    `${base}/?tab=auth#tgWebAppData=${encodeURIComponent(signedFixture)}`,
  );
  await page
    .getByRole("heading", { name: "Owner access verified", exact: true })
    .waitFor();
  assert.equal(
    authPosts,
    1,
    "Signed launch data must authenticate even without the Telegram SDK",
  );
  authMode = "browser";
  sessionActive = true;
  for (const [tab, heading] of [
    ["chat", "Smart Chat"],
    ["groups", "Group Manager"],
    ["automation", "Automation"],
    ["analytics", "Analytics"],
    ["broadcast", "Broadcast"],
    ["settings", "Settings & services"],
  ]) {
    await page.goto(`${base}/?tab=${tab}`);
    await page.getByRole("heading", { name: heading, exact: true }).waitFor();
  }
  await page.goto(`${base}/?tab=groups`);
  await page.getByRole("button", { name: /Offline community/ }).waitFor();
  await page.getByLabel("Search served groups").fill("missing-group");
  assert.equal(
    await page.getByRole("button", { name: /Offline community/ }).count(),
    0,
  );
  await page.getByLabel("Search served groups").fill("Offline");
  await page
    .getByRole("button", { name: "Disable Anti-Spam", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enable Anti-Spam", exact: true })
    .waitFor();
  await page.goto(`${base}/?tab=chat`);
  await page.getByRole("button", { name: /Offline community/ }).click();
  await page.getByRole("button", { name: "Thank you", exact: true }).click();
  assert.ok(
    (await page.getByLabel("Message text").inputValue()).includes("Thanks"),
  );
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await page.getByText(/Telegram accepted · #31/).waitFor();
  await page.getByRole("button", { name: /Find a tool or jump/ }).click();
  await page.getByLabel("Search workspace tools").fill("analytics");
  await page.getByLabel("Search workspace tools").press("Enter");
  await page.getByRole("heading", { name: "Analytics", exact: true }).waitFor();
  await page
    .getByRole("dialog", { name: "Find a tool", exact: true })
    .waitFor({ state: "hidden" });
  downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", {
      name: "Download observed analytics · CSV",
      exact: true,
    })
    .click();
  download = await downloadPromise;
  await download.saveAs(path.join(artifacts, "analytics.csv"));
  assert.ok(
    (await fs.readFile(path.join(artifacts, "analytics.csv"), "utf8")).includes(
      '"command","play","5"',
    ),
  );
  await page.goto(`${base}/?tab=post`);
  await page.getByRole("button", { name: "Design Image", exact: true }).click();
  await page
    .getByRole("button", { name: "Browse 8 editable layouts", exact: true })
    .click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Apply layout A warm welcome", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Heading", { exact: true }).inputValue(),
    "You belong here.",
  );
  await page
    .getByLabel("Background pattern", { exact: true })
    .selectOption("dots");
  downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PNG", exact: true }).click();
  download = await downloadPromise;
  await download.saveAs(path.join(artifacts, "recipe.png"));
  assert.equal(
    (await fs.readFile(path.join(artifacts, "recipe.png"))).readUInt32BE(16),
    1080,
  );
  authMode = "nonowner";
  sessionActive = true;
  await page.goto(
    `${base}/?tab=settings#tgWebAppData=${encodeURIComponent(signedFixture)}`,
  );
  await page
    .getByRole("heading", {
      name: "Make something worth sharing.",
      exact: true,
    })
    .waitFor();
  await page.waitForFunction(
    () => !document.body.innerText.includes("Bot Settings"),
  );
  assert.equal(
    await page.getByRole("link", { name: "Bot Settings", exact: true }).count(),
    0,
  );
  authMode = "blocked";
  sessionActive = false;
  await page.goto(
    `${base}/?tab=auth#tgWebAppData=${encodeURIComponent(signedFixture)}`,
  );
  await page
    .getByRole("alert")
    .filter({ hasText: "browser blocked the owner session" })
    .waitFor();
  assert.equal(
    await page
      .getByRole("heading", { name: "Owner access verified", exact: true })
      .count(),
    0,
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: real Chromium PNG export, editable JSON export, keyboard movement, JSON import, mocked image publish, duplicate guard, caption limit, post recovery, design restore, 390px mobile layout, owner-session restoration, SDK-independent Mini App login, blocked-cookie diagnosis, private-tool gates, all private screens, group search/toggle, chat quick replies, CSV export, tool finder, editable recipe PNG export; no runtime errors.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
