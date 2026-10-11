import { expect, test } from "@playwright/test";
import { t } from "../src/shared/i18n";
import { expectAccessible, expectNoHorizontalScroll } from "./fixtures/a11y";
import { mockRag } from "./fixtures/rag";

test("каталог находит позицию и сравнивает её с другой", async ({ page }) => {
  await mockRag(page);
  await page.goto("/catalog?q=шкаф");
  await expect(page.getByText(t("store:catalog.found", { count: 1 }))).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page.getByRole("link", { name: "31.01.11.121-00000003" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Шкаф для одежды металлический" }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: t("store:compare.add") }).fill("31.01.11.121-00000001");
  await page.getByRole("button", { name: t("store:compare.addAction") }).click();
  await expect(page).toHaveURL(/compare=31\.01\.11\.121-00000001/);
  await expect(page.getByText(t("store:compare.summary", { differs: 1, total: 2 }))).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});
