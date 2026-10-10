import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export async function expectAccessible(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every(
        (a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity,
      ),
  );
  const result = await new AxeBuilder({ page: page as never })
    .include("[data-portal]")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const serious = result.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
  ).toEqual([]);
}

export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

export async function watchExit(page: Page): Promise<() => Promise<boolean>> {
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { __states: string[] }).__states = seen;
    new MutationObserver((records) => {
      for (const r of records) {
        const el = r.target as Element;
        if (r.type === "attributes" && el.getAttribute("data-state") === "closing")
          seen.push("closing");
      }
    }).observe(document.body, { attributes: true, subtree: true, attributeFilter: ["data-state"] });
  });
  return () =>
    page.evaluate(() => (window as unknown as { __states: string[] }).__states.includes("closing"));
}
