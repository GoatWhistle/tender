import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"
import portal from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

const candidates = Array.from({ length: 20 }, (_, index) => ({
  id: `position-${index}`,
  code: `31.01.11.121-${index}`,
  name: `Шкаф ${index + 1}`,
  okpd2: "31.01.11.121",
  reason: "",
  differences: { Материал: "Металл", Высота: "120 см", Отделения: "2", Ширина: "60 см" },
}))
const ranked = candidates.slice(0, 5).reverse()
const search = {
  id: "rank-preview",
  description: "Шкаф для одежды",
  corrected: "Шкаф для одежды",
  fixes: [],
  issues: [],
  auto_select_code: null,
  auto_select_reason: null,
}

for (const mobile of [false, true]) {
  test(`Ранжирование и просмотр кода ${mobile ? "на телефоне" : "на компьютере"}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 375 : 1440, height: 1000 })
    await page.emulateMedia({ reducedMotion: mobile ? "reduce" : "no-preference" })
    let release = () => {}
    const ranking = new Promise<void>((resolve) => {
      release = resolve
    })
    let selected = 0
    let previews = 0
    await page.context().route("http://127.0.0.1:5175/api/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/catalog/")) {
        previews += 1
        return route.fulfill({
          json: {
            code: ranked[0]?.code,
            name: ranked[0]?.name,
            okpd2: "31.01.11.121",
            okpd2_name: "Мебель",
            units: ["Штука"],
            rubrics: [],
            characteristics: Array.from({ length: 50 }, (_, index) => ({
              code: String(index),
              name: `Характеристика ${index + 1}`,
              kind: "2",
              required: index === 0,
              values: ["Допустимое значение", "Другое значение"],
            })),
          },
        })
      }
      if (url.endsWith("/select")) {
        selected += 1
        return route.abort()
      }
      if (url.endsWith("/rerank")) {
        await ranking
        return route.fulfill({ json: { ...search, stage: "ranked", candidates: ranked } })
      }
      return route.fulfill({
        json: { ...search, stage: url.endsWith("/searches") ? "review" : "candidates", candidates },
      })
    })
    await page.goto("/")
    await page.getByRole("textbox", { name: portal.inputLabel }).fill(search.description)
    await page.getByRole("textbox", { name: portal.inputLabel }).press("Enter")
    await expect(page.locator("li[data-id]")).toHaveCount(20)
    await expect(page.locator("[data-rank-arrow]")).toHaveCount(0)
    await expect(page.locator("[data-rank-differences]")).toHaveCount(0)
    const before = await page
      .locator("li[data-id]")
      .first()
      .evaluate((row) => ({
        row: row.getBoundingClientRect().right,
        title: row.querySelector("[data-rank-code]")?.getBoundingClientRect().right ?? 0,
      }))
    expect(before.row - before.title).toBeLessThan(50)
    await page.evaluate(() => {
      let minimum = Number.POSITIVE_INFINITY
      let maximum = 0
      let hidden = false
      function sample() {
        const arrow = document.querySelector("[data-rank-arrow]")
        const differences = document.querySelector("[data-rank-differences]")
        if (arrow && differences) {
          const left = arrow.getBoundingClientRect().left
          minimum = Math.min(minimum, left)
          maximum = Math.max(maximum, left)
          hidden ||= Number(getComputedStyle(differences).opacity) < 0.5
          document.documentElement.dataset.rankEvidence = JSON.stringify({
            distance: maximum - minimum,
            hidden,
          })
          if (!arrow.getAnimations().length && !differences.getAnimations().length) return
        }
        requestAnimationFrame(sample)
      }
      requestAnimationFrame(sample)
    })
    release()
    await expect(page.locator("li[data-id]")).toHaveCount(5)
    await expect(page.locator("[data-rank-arrow]")).toHaveCount(5)
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((animation) => animation.finished.catch(() => undefined)),
      )
    })
    expect(
      await page
        .locator("li[data-id]")
        .evaluateAll((rows) => rows.map((row) => row.getAttribute("data-id"))),
    ).toEqual(ranked.map((candidate) => candidate.id))
    await expect(page.getByText(/Ещё различий/)).toHaveCount(0)
    if (!mobile) {
      const evidence = await page.evaluate(() =>
        JSON.parse(document.documentElement.dataset.rankEvidence ?? "{}"),
      )
      expect(evidence.distance).toBeGreaterThan(100)
      expect(evidence.hidden).toBe(true)
    }
    const code = ranked[0]?.code ?? ""
    const trigger = page.getByRole("link", { name: code, exact: true })
    await expect(trigger).toHaveAttribute("target", "_blank")
    expect(await trigger.evaluate((link) => getComputedStyle(link).fontWeight)).toBe("400")
    const popupPromise = page.waitForEvent("popup")
    await trigger.click()
    const popup = await popupPromise
    await expect(popup.getByRole("heading", { name: rag.catalogContents })).toBeVisible()
    await expect(popup.getByText("Характеристика 50", { exact: true })).toBeAttached()
    await expect(page.getByRole("heading", { name: rag.catalogContents })).toHaveCount(0)
    expect(selected).toBe(0)
    expect(previews).toBeGreaterThan(0)
    const axe = await new AxeBuilder({ page: popup }).withTags(["wcag2a", "wcag2aa"]).analyze()
    expect(axe.violations).toEqual([])
    expect(await popup.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    )
    await popup.screenshot({
      path: test.info().outputPath(`preview-${mobile ? "mobile" : "desktop"}.png`),
    })
    await popup.close()
    await page.screenshot({
      path: test.info().outputPath(`ranked-${mobile ? "mobile" : "desktop"}.png`),
    })
  })
}
