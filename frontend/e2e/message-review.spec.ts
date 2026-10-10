import { expect, test } from "@playwright/test"
import portal from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

const candidate = { id: "cabinet", code: "31.01", name: "Шкаф", differences: {} }
const search = {
  id: "search",
  description: "Шкаф",
  corrected: "Шкаф",
  fixes: [],
  issues: [],
  candidates: [candidate],
  auto_select_code: null,
}
const session = {
  id: "session",
  stage: "spec",
  position: { code: "31.01", name: "Шкаф", fixed: {} },
  characteristics: [
    {
      name: "Высота",
      required: false,
      multiple: false,
      options: ["1000 мм", "1100 мм"],
      values: ["1000 мм"],
    },
  ],
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

for (const mobile of [false, true]) {
  test(`Дополнение проверяется до применения ${mobile ? "на телефоне" : "на компьютере"}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 390 : 1440, height: 1000 })
    let confirmations = 0
    let release = () => {}
    const waiting = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route("http://127.0.0.1:5175/api/**", async (route) => {
      const url = route.request().url()
      if (url.endsWith("/confirm")) {
        confirmations += 1
        await waiting
        return route.fulfill({
          json: {
            ...session,
            characteristics: [{ ...session.characteristics[0], values: ["1100 мм"] }],
          },
        })
      }
      if (url.endsWith("/messages"))
        return route.fulfill({
          json: {
            ...session,
            message_review: {
              id: "review",
              original: "высота 1100 м",
              corrected: "высота 1100 мм",
              fixes: [{ before: "1100 м", after: "1100 мм", kind: "unit" }],
              issues: [],
            },
          },
        })
      if (url.endsWith("/select")) return route.fulfill({ json: session })
      return route.fulfill({
        json: { ...search, stage: url.endsWith("/searches") ? "review" : "ranked" },
      })
    })
    await page.goto("/")
    const input = page.getByRole("textbox", { name: portal.inputLabel })
    await expect(page.getByText(portal.introText, { exact: true })).toBeVisible()
    await input.fill("Шкаф")
    await input.press("Enter")
    await page.locator("li[data-id] button").first().click()
    await expect(page.getByText(rag.conversationHint, { exact: true })).toBeVisible()
    await input.fill("высота 1100 м")
    await input.press("Enter")
    await expect(page.getByRole("heading", { name: rag.messageReviewTitle })).toBeVisible()
    await expect(input).toHaveValue("высота 1100 м")
    expect(confirmations).toBe(0)
    await expect(page.getByRole("button", { name: /1000 мм/ })).toBeVisible()
    await page.screenshot({
      path: test.info().outputPath(`review-${mobile ? "mobile" : "desktop"}.png`),
    })
    await page.getByRole("button", { name: rag.applyMessage, exact: true }).click()
    await expect(input).toBeEnabled()
    await input.fill("Добавьте две полки")
    release()
    await expect(page.getByRole("heading", { name: rag.messageReviewTitle })).toHaveCount(0)
    await expect(input).toHaveValue("Добавьте две полки")
    await expect(page.getByRole("button", { name: /1100 мм/ })).toBeVisible()
  })
}
