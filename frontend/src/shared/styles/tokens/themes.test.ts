import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (name: string) => readFileSync(new URL(name, import.meta.url), "utf8");

const LIGHT = ":root:has([data-portal])";
const DARK = ':root:has([data-portal])[data-theme="dark"]';

function block(css: string, selector: string): string {
  const start = css.indexOf(`${selector} {`);
  return start < 0 ? "" : css.slice(start, css.indexOf("\n}", start));
}

function declared(...blocks: string[]): string[] {
  return blocks.flatMap((b) => [...b.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1] ?? "")).sort();
}

describe("семантические токены", () => {
  it("переопределены в тёмной теме", () => {
    const semantic = read("./semantic.css");
    const light = declared(block(semantic, LIGHT), block(read("./elevation.css"), LIGHT));
    const dark = declared(block(semantic, DARK));
    expect(light.length).toBeGreaterThan(0);
    expect(dark).toEqual(light);
  });
});
