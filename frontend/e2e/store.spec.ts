import { expect, test } from "@playwright/test";
import { t } from "../src/shared/i18n";
import { expectAccessible, expectNoHorizontalScroll } from "./fixtures/a11y";

test("главная показывает категории и ведёт в каталог", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: t("store:title") })).toBeVisible();
  const cards = page.locator("ul a[href^='/catalog/']");
  await expect(cards).toHaveCount(3);
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
  await cards.first().click();
  await expect(page).toHaveURL(/\/catalog\//);
});

test("каталог фильтрует по позиции и открывает товар", async ({ page }) => {
  await page.goto("/catalog/mebel");
  const table = page.getByRole("table");
  await expect(table.getByRole("row").nth(1)).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  const filtersToggle = page.getByRole("button", { name: t("store:catalog.filters") });
  if (await filtersToggle.isVisible()) await filtersToggle.click();
  const position = page
    .getByRole("group", { name: t("store:catalog.position") })
    .getByRole("radio")
    .nth(1);
  await position.check({ force: true });
  await expect(page).toHaveURL(/position=/);
  await expect(page.getByRole("button", { name: t("store:catalog.reset") })).toBeVisible();

  await page.getByRole("radio", { name: t("store:catalog.sortPriceAsc") }).click();
  await expect(page).toHaveURL(/sort=price_asc/);

  await table.getByRole("link").first().click();
  await expect(page).toHaveURL(/\/product\//);
  await expect(page.getByRole("progressbar").first()).toBeVisible();
  await expect(page.getByRole("table", { name: t("store:product.characteristics") })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});

test("несуществующий адрес показывает страницу портала", async ({ page }) => {
  await page.goto("/nope");
  await expect(page.getByText(t("common:notFound.title"))).toBeVisible();
  await expect(
    page.getByRole("link", { name: t("common:notFound.home"), exact: true }),
  ).toBeVisible();
  await expectAccessible(page);
});
