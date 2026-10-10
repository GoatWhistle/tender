import { expect, test } from "@playwright/test";
import { dictionaries, t } from "../src/shared/i18n";
import { expectAccessible, expectNoHorizontalScroll } from "./fixtures/a11y";

test("тёмная тема сохраняется и проходит проверку доступности", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: t("common:theme.dark") }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expectAccessible(page);

  await page.goto("/catalog/mebel");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("table").getByRole("row").nth(1)).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page.goto("/sell");
  await expectAccessible(page);
});

test("переключатель языка переводит интерфейс и запоминает выбор", async ({ page }) => {
  const en = dictionaries.en;
  await page.goto("/");
  await page.getByRole("radio", { name: t("common:language.en") }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1, name: en.store.title })).toBeVisible();
  await expect(page.getByRole("link", { name: en.common.nav.catalog })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: en.store.title })).toBeVisible();

  await page.getByRole("radio", { name: en.common.language.ru }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { level: 1, name: t("store:title") })).toBeVisible();
});
