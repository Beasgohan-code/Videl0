/**
 * Minimal component test harness: React 19 server rendering into a string.
 *
 * There is no browser in CI, and screens are client components, so hooks are
 * not exercised here. What it does prove is that a screen renders every prop
 * path without throwing, which is exactly what a prop rename breaks.
 */
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

export function render(element: ReactElement): string {
  return renderToStaticMarkup(element);
}

export { createElement };
