import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import Broadcast from "../src/components/studio/screens/Broadcast";

test("broadcast requires an explicit preview step before sending", () => {
  const markup = renderToStaticMarkup(createElement(Broadcast));
  assert.match(markup, /Preview message/);
  assert.doesNotMatch(markup, /aria-label="Broadcast preview"/);
  assert.match(markup, /disabled=""[^>]*>[\s\S]*Send broadcast/);
});
