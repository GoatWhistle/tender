import { expect, test } from "@playwright/test"
import portal from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

for (const mobile of [false, true]) {
  test(`Загрузка поверх списка без сдвига ${mobile ? "на телефоне" : "на компьютере"}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 390 : 1440, height: 1000 })
    await page.emulateMedia({ reducedMotion: mobile ? "reduce" : "no-preference" })
    let finishRanking = () => {}
    let finishSelection = () => {}
    const ranking = new Promise<void>((resolve) => {
      finishRanking = resolve
    })
    const selection = new Promise<void>((resolve) => {
      finishSelection = resolve
    })
    const candidate = {
      id: "one",
      code: "31.01.11.121-1",
      name: "Шкаф",
      okpd2: "31.01.11.121",
      reason: "",
      differences: {},
    }
    const search = {
      id: "loading",
      description: "Шкаф",
      corrected: "Шкаф",
      fixes: [],
      issues: [],
      candidates: [candidate],
      auto_select_code: candidate.code,
      auto_select_reason: null,
    }
    await page.route("**/api/searches**", async (route) => {
      const url = route.request().url()
      if (url.endsWith("/select")) {
        await selection
        return route.abort()
      }
      if (url.endsWith("/rerank")) await ranking
      await route.fulfill({
        json: {
          ...search,
          stage: url.endsWith("/searches")
            ? "review"
            : url.endsWith("/rerank")
              ? "ranked"
              : "candidates",
        },
      })
    })
    await page.goto("/")
    await page.getByRole("textbox", { name: portal.inputLabel }).fill(search.description)
    await page.getByRole("button", { name: portal.send, exact: true }).click()
    const row = page.locator("li[data-id]").first()
    await expect(row).toBeVisible()
    const before = await row.boundingBox()
    const status = page.getByRole("status")
    await expect(status).toHaveText(rag.ranking)
    await expect(status).toHaveAttribute("data-state", "open")
    await expect(status).toBeInViewport()
    expect(await row.boundingBox()).toEqual(before)
    expect(await status.evaluate((node) => getComputedStyle(node).pointerEvents)).toBe("none")
    await expect(status).toHaveCSS("opacity", "1")
    const bounds = await status.boundingBox()
    expect(
      Math.abs((bounds?.x ?? 0) + (bounds?.width ?? 0) / 2 - (mobile ? 390 : 1440) / 2),
    ).toBeLessThan(1)
    expect(bounds?.width).toBeLessThanOrEqual(mobile ? 342 : 480)
    expect(bounds?.height).toBeLessThan(80)
    await expect(status).toHaveCSS("border-top-width", "0px")
    await expect(status).toHaveCSS("box-shadow", "none")
    await expect(status).toHaveCSS("background-color", "rgba(0, 0, 0, 0)")
    await expect(status).toHaveCSS("font-weight", "400")
    await expect(status).toHaveCSS("font-size", "20px")
    await page.screenshot({ path: test.info().outputPath("ranking.png") })
    finishRanking()
    await expect(status).toHaveText(rag.selecting)
    await expect(status).toBeInViewport()
    await expect(row).toBeVisible()
    await page.screenshot({ path: test.info().outputPath("selecting.png") })
    finishSelection()
    await expect(page.getByRole("alert")).toBeVisible()
    await expect(page.locator('[role="status"]')).toHaveAttribute("data-state", "closed")
    await expect(page.locator('[role="status"]')).toBeHidden()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
