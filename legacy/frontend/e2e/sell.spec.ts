import { expect, test } from "@playwright/test";
import { t } from "../src/shared/i18n";
import { expectAccessible, expectNoHorizontalScroll, watchExit } from "./fixtures/a11y";
import { mockSellApi, SELL_TEXT } from "./fixtures/sell";

test.beforeEach(async ({ page }) => {
  await mockSellApi(page);
});

test("мастер проводит от описания до карточки", async ({ page }) => {
  await page.goto("/sell");
  await expect(page.getByRole("heading", { name: t("seller:describe.heading") })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page.getByLabel(t("seller:describe.label")).fill(SELL_TEXT);
  await page.getByRole("button", { name: t("seller:describe.submit") }).click();

  await expect(page).toHaveURL(/step=position/);
  await expect(page.getByRole("heading", { name: t("seller:position.heading") })).toBeVisible();
  await expect(page.getByRole("table", { name: t("seller:position.candidates") })).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: t("common:actions.next") }).click();
  await expect(page).toHaveURL(/step=characteristics/);
  const table = page.getByRole("table", { name: t("seller:characteristics.caption") });
  await expect(table).toBeVisible();
  await expect(
    table.getByRole("button", { name: t("seller:row.fix", { value: "550 мм" }) }),
  ).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  const closedEditor = await watchExit(page);
  await table.getByRole("button", { name: t("seller:row.collapse") }).click();
  await expect.poll(closedEditor).toBe(true);
  await expect(table.getByRole("button", { name: t("seller:row.collapse") })).toHaveCount(0);

  const questionRow = table.getByRole("rowgroup").filter({ hasText: "Тип шкафа" });
  await questionRow.getByRole("button", { name: t("seller:row.specify") }).click();
  await questionRow.getByText("Секционный").click();

  await expect(page.getByRole("button", { name: t("common:actions.next") })).toBeEnabled();
  await page.getByRole("button", { name: t("common:actions.next") }).click();
  await expect(page).toHaveURL(/step=card/);
  await expect(page.getByText(t("seller:card.complete"))).toBeVisible();
  await expectAccessible(page);
});

test("необязательные характеристики раскрываются и закрываются с анимацией", async ({ page }) => {
  await page.goto("/sell");
  await page.getByLabel(t("seller:describe.label")).fill(SELL_TEXT);
  await page.getByRole("button", { name: t("seller:describe.submit") }).click();
  await page.getByRole("button", { name: t("common:actions.next") }).click();
  const trigger = page.getByRole("button", {
    name: t("seller:characteristics.optional", { count: 1 }),
  });
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("table", { name: t("seller:characteristics.optionalCaption") }),
  ).toBeVisible();
  const closedPanel = await watchExit(page);
  await trigger.click();
  await expect.poll(closedPanel).toBe(true);
  await expect(
    page.getByRole("table", { name: t("seller:characteristics.optionalCaption") }),
  ).toHaveCount(0);
});

test("уменьшенное движение сжимает длительности", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/sell");
  const duration = await page.evaluate(() =>
    getComputedStyle(document.querySelector("[data-portal]") as Element)
      .getPropertyValue("--dur-base")
      .trim(),
  );
  expect(duration).toBe("1ms");
});
