import { expect, test } from "@playwright/test"
import ru from "../src/shared/i18n/locales/ru/portal.json" with { type: "json" }
import rag from "../src/shared/i18n/locales/ru/rag.json" with { type: "json" }

test("Живой КТРУ: автовыбор группы, различия и выбор единицы поставки", async ({ page }) => {
  test.skip(process.env.RAG_LIVE_TEST !== "1", "Нужны настоящий индекс и доступ к моделям")
  test.setTimeout(180000)
  await page.goto("/")
  await page
    .getByRole("textbox", { name: ru.inputLabel })
    .fill("Подгузник детский немедицинский многоразового использования")
  const initial = page.waitForResponse(
    (response) => response.url().endsWith("/searches") && response.request().method() === "POST",
  )
  const ranked = page.waitForResponse((response) => response.url().endsWith("/rerank"), {
    timeout: 120000,
  })
  const selected = page.waitForResponse((response) => response.url().endsWith("/select"), {
    timeout: 150000,
  })
  await page.getByRole("textbox", { name: ru.inputLabel }).press("Enter")
  const search = await (await initial).json()
  if (search.fixes.length || search.issues.length)
    await page
      .getByRole("button", { name: search.fixes.length ? rag.acceptChanges : rag.searchAsIs })
      .click()
  const ranking = await (await ranked).json()
  expect(ranking.candidates.length).toBeGreaterThan(0)
  expect(ranking.candidates[0].differences).toBeDefined()
  if (!ranking.auto_select_code)
    await page
      .getByRole("list", { name: ru.catalogLabel })
      .getByRole("button")
      .filter({ hasText: ranking.candidates[0].name })
      .first()
      .click()
  const session = await (await selected).json()
  expect(session.stage).toBe("clarify")
  expect(session.question.name).toBe("Единица поставки")
  await expect(page.getByRole("heading", { name: "Единица поставки", exact: true })).toBeVisible()
  await expect(page.getByRole("term").filter({ hasText: "Единица поставки" })).toHaveCount(2)
  await expect(page.getByRole("definition").filter({ hasText: "Упаковка" })).toBeVisible()
  await expect(page.getByRole("definition").filter({ hasText: "Штука" })).toBeVisible()
  await test.info().attach("selection-decision", {
    body: JSON.stringify({
      automatic: Boolean(ranking.auto_select_code),
      reason: ranking.auto_select_reason,
    }),
    contentType: "application/json",
  })
  await page.screenshot({ path: "test-results/ktru-differences.png", fullPage: true })
  const answered = page.waitForResponse((response) => response.url().endsWith("/answer"), {
    timeout: 60000,
  })
  await page.getByRole("button", { name: "Упаковка", exact: true }).click()
  const resolved = await (await answered).json()
  expect(resolved.stage).toBe("spec")
  expect(resolved.position.code).toBe("17.22.12.120-00000005")
  await expect(page.getByRole("heading", { name: rag.specTitle })).toBeVisible()
  const input = page.getByRole("textbox", { name: ru.inputLabel })
  await expect(input).toBeVisible()
  const message = page.waitForResponse((response) => response.url().endsWith("/messages"), {
    timeout: 90000,
  })
  await input.fill("Какие характеристики уже заполнены? Ничего не меняй.")
  await input.press("Enter")
  const updated = await (await message).json()
  expect(updated.messages).toHaveLength(2)
  expect(updated.characteristics).toEqual(resolved.characteristics)
  await expect(input).toHaveValue("")
  await expect(page.getByRole("region", { name: rag.conversation })).toBeVisible()
  await page.screenshot({ path: "test-results/persistent-conversation.png", fullPage: true })
  const instructions = resolved.characteristics
    .map((field: { name: string; options: string[] }) => `${field.name}: ${field.options[0]}`)
    .join("; ")
  const filled = page.waitForResponse((response) => response.url().endsWith("/messages"), {
    timeout: 90000,
  })
  await input.fill(`Заполни карточку следующими значениями: ${instructions}`)
  await input.press("Enter")
  const card = await (await filled).json()
  expect(card.missing).toEqual([])
  await page.getByRole("button", { name: rag.preview, exact: true }).click()
  await expect(input).toBeVisible()
  await page.getByRole("button", { name: rag.finish, exact: true }).click()
  await expect(page.getByRole("heading", { name: rag.done, exact: true })).toBeVisible()
  await expect(input).toBeVisible()
  const cleared = page.waitForResponse((response) => response.url().endsWith("/messages"), {
    timeout: 90000,
  })
  await input.fill(
    `Очисти значение характеристики «${resolved.characteristics[0].name}», остальные не меняй.`,
  )
  await input.press("Enter")
  const edited = await (await cleared).json()
  expect(edited.stage).toBe("spec")
  expect(edited.characteristics[0].values).toEqual([])
  await expect(page.getByRole("button", { name: rag.download, exact: true })).toHaveCount(0)
})
