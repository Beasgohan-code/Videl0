import test from "node:test";
import assert from "node:assert/strict";
import { canOpenSection, OWNER_ID } from "../src/lib/access";
import { campaignLink, textInsights } from "../src/lib/creator-tools";
test("public, loading and non-owner sessions never unlock private sections", () => {
  assert.equal(OWNER_ID, "6265999542");
  for (const owner of [false, null]) {
    for (const section of ["home", "post", "tools", "guide", "auth"])
      assert.equal(canOpenSection(section, owner), true);
    for (const section of [
      "chat",
      "groups",
      "federations",
      "automation",
      "analytics",
      "broadcast",
      "settings",
    ])
      assert.equal(canOpenSection(section, owner), false);
  }
  assert.equal(canOpenSection("settings", true), true);
});
test("creator tools count Telegram UTF16 units and unique Unicode hashtags", () => {
  assert.deepEqual(textInsights("Hi 😀 #Hello #HELLO #കേരളം"), {
    characters: 25,
    telegramLength: 26,
    words: 5,
    hashtags: ["#hello", "#കേരളം"],
  });
});
test("campaign links preserve existing parameters, replace labels, and reject active URLs", () => {
  const link = new URL(
    campaignLink(
      "https://example.com/news?id=7&utm_source=old#part",
      "telegram",
      "social",
      "Autumn sale",
    ),
  );
  assert.equal(link.searchParams.get("id"), "7");
  assert.equal(link.searchParams.get("utm_source"), "telegram");
  assert.equal(link.searchParams.get("utm_campaign"), "Autumn sale");
  assert.equal(link.hash, "#part");
  for (const raw of [
    "javascript:alert(1)",
    "file:///etc/passwd",
    "https://user:pass@example.com/",
  ])
    assert.throws(() => campaignLink(raw, "a", "b", "c"));
});
