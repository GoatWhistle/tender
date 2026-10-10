import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"
import ru from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

test("Настоящий API, доступный ввод и мобильный экран", async ({ page, request }) => {
  const schema = await request.get("http://127.0.0.1:8100/openapi.json")
  expect(schema.ok()).toBe(true)
  expect((await schema.json()).paths["/searches"]).toBeDefined()
  await page.goto("/")
  await expect(page.getByRole("textbox", { name: ru.inputLabel })).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  const health = await request.get("http://127.0.0.1:8100/health")
  if (health.status() === 503) {
    await page.getByRole("textbox", { name: ru.inputLabel }).fill("Шкаф металлический")
    await page.getByRole("textbox", { name: ru.inputLabel }).press("Enter")
    await expect(page.getByRole("alert")).toContainText(rag.unavailable)
    await expect(page.getByRole("alert")).toBeInViewport()
    await expect(page.getByRole("textbox", { name: ru.inputLabel })).toHaveValue(
      "Шкаф металлический",
    )
  }
  await page.screenshot({ path: "test-results/real-api.png" })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole("button", { name: ru.theme }).click()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})
