import { expect, test } from "@playwright/test"
import portal from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

const original = "Шкаф высотой 1000 м"
const corrected = "Шкаф высотой 1000 мм"
const search = {
  id: "review-test",
  stage: "review",
  description: original,
  corrected,
  fixes: [{ before: "1000 м", after: "1000 мм", kind: "unit" }],
  issues: [],
  candidates: [],
  auto_select_code: null,
  rejected: [],
  auto_select_reason: null,
}

for (const mobile of [false, true]) {
  test(`Исправления применяются только после подтверждения ${mobile ? "на телефоне" : "на компьютере"}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 390 : 1440, height: 1000 })
    let candidateRequests = 0
    let release = () => {}
    const waiting = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route("**/api/searches**", async (route) => {
      if (route.request().url().endsWith("/candidates")) {
        candidateRequests += 1
        await waiting
      }
      const initial = route.request().url().endsWith("/searches")
      await route.fulfill({ json: { ...search, stage: initial ? "review" : "ranked" } })
    })
    await page.goto("/")
    const input = page.getByRole("textbox", { name: portal.inputLabel })
    await input.fill(original)
    await page.getByRole("button", { name: portal.send, exact: true }).click()
    await expect(page.getByRole("heading", { name: rag.reviewChanges })).toBeVisible()
    await expect(input).toHaveValue(original)
    expect(candidateRequests).toBe(0)
    await page.screenshot({
      path: test.info().outputPath(`review-${mobile ? "mobile" : "desktop"}.png`),
    })
    await page.getByRole("button", { name: rag.acceptChanges }).click()
    await expect(input).toHaveValue(corrected)
    await expect(page.getByRole("status")).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    release()
    await expect(page.getByRole("heading", { name: portal.rankedTitle })).toBeVisible()
  })
}

test("Ручные исправления проверяются заново", async ({ page }) => {
  const descriptions: string[] = []
  await page.route("**/api/searches", async (route) => {
    descriptions.push(route.request().postDataJSON().description)
    await route.fulfill({ json: search })
  })
  await page.goto("/")
  const input = page.getByRole("textbox", { name: portal.inputLabel })
  await input.fill(original)
  await input.press("Enter")
  await page.getByRole("button", { name: rag.editDescription }).click()
  await expect(input).toBeFocused()
  await input.fill("Шкаф высотой 120 см")
  await page.getByRole("button", { name: rag.checkEdits }).click()
  await expect.poll(() => descriptions).toEqual([original, "Шкаф высотой 120 см"])
})
