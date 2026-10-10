import { expect, test } from "@playwright/test"
import portal from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

for (const mobile of [false, true]) {
  test(`Точные размеры и проверка ограничений ${mobile ? "на телефоне" : "на компьютере"}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 390 : 1440, height: 1000 })
    const candidate = { id: "cabinet", code: "31.01", name: "Шкаф", differences: {} }
    const fields = [
      {
        name: "Высота",
        required: true,
        multiple: false,
        options: ["≥ 1000 < 1200 Миллиметр"],
        values: ["≥ 1000 < 1200 Миллиметр"],
        numeric: {
          unit: "мм",
          exact: "1000",
          ranges: [
            { min: 1000, min_op: "greaterOrEqual", max: 1200, max_op: "less", concrete: [] },
          ],
        },
      },
      {
        name: "Глубина",
        required: false,
        multiple: false,
        options: ["≥ 500 < 600 Миллиметр"],
        values: ["≥ 500 < 600 Миллиметр"],
        numeric: {
          unit: "мм",
          exact: "550",
          ranges: [{ min: 500, min_op: "greaterOrEqual", max: 600, max_op: "less", concrete: [] }],
        },
      },
    ]
    const session = {
      id: "session",
      stage: "spec",
      position: { code: "31.01", name: "Шкаф", fixed: {} },
      characteristics: fields,
      extras: [],
      extras_allowed: true,
      missing: [],
      messages: [],
      message: null,
      selection_reason: null,
      candidates: [],
      question: null,
      message_review: null,
    }
    let updates = 0
    await page.route("http://127.0.0.1:5175/api/**", async (route) => {
      const url = route.request().url()
      if (route.request().method() === "PATCH") {
        const body = route.request().postDataJSON()
        expect(body).toEqual({ values: {}, exact: { Высота: "1100" } })
        updates += 1
        const field = fields[0]
        if (field) field.numeric.exact = "1100"
        return route.fulfill({ json: session })
      }
      if (url.endsWith("/select")) return route.fulfill({ json: session })
      return route.fulfill({
        json: {
          id: "search",
          stage: url.endsWith("/searches") ? "review" : "ranked",
          description: "Шкаф",
          corrected: "Шкаф",
          fixes: [],
          issues: [],
          candidates: [candidate],
          auto_select_code: null,
        },
      })
    })
    await page.goto("/")
    const prompt = page.getByRole("textbox", { name: portal.inputLabel })
    await prompt.fill("Шкаф")
    await prompt.press("Enter")
    await page.locator("li[data-id] button").first().click()
    const height = page.getByRole("textbox", { name: "Высота", exact: true })
    await expect(height).toHaveValue("1000")
    await expect(page.getByRole("textbox", { name: "Глубина", exact: true })).toHaveValue("550")
    await height.fill("1200")
    await page.getByRole("button", { name: rag.saveNumber, exact: true }).click()
    await expect(page.getByRole("alert")).toHaveText(rag.numberOutside)
    expect(updates).toBe(0)
    await expect(page.getByRole("button", { name: rag.preview, exact: true })).toBeDisabled()
    await height.fill("1100")
    await page.getByRole("button", { name: rag.saveNumber, exact: true }).click()
    await expect(height).toHaveValue("1100")
    await expect(page.getByRole("button", { name: rag.saveNumber, exact: true })).toHaveCount(0)
    expect(updates).toBe(1)
    await page.screenshot({
      path: test.info().outputPath(`quantities-${mobile ? "mobile" : "desktop"}.png`),
      fullPage: true,
    })
    await page.getByRole("button", { name: rag.preview, exact: true }).click()
    await expect(page.getByText("1100 мм", { exact: true })).toBeVisible()
    await expect(page.getByText("550 мм", { exact: true })).toBeVisible()
  })
}
