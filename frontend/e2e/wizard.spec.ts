import { expect, test } from "@playwright/test";
import { t } from "../src/shared/i18n";
import { expectAccessible, expectNoHorizontalScroll } from "./fixtures/a11y";
import { mockRag } from "./fixtures/rag";

test("мастер проходит от описания до карточки", async ({ page }) => {
  await mockRag(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: t("store:home.title") })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page
    .getByRole("textbox", { name: t("seller:describe.label") })
    .fill("Шкаф для одежды металлический, глубина 0,55 м");
  await page.getByRole("button", { name: t("seller:describe.submit") }).click();

  await expect(page.getByText(t("seller:position.best"))).toBeVisible();
  await expect(
    page.getByText(t("seller:position.groupsLeft", { left: 2, total: 3 })),
  ).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);

  await page
    .getByRole("button", { name: t("seller:position.choose") })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: "Вид товара" })).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("button", { name: /^Шкаф/ }).click();

  await expect(
    page.getByRole("heading", { level: 2, name: t("seller:characteristics.heading") }),
  ).toBeVisible();
  await expect(page.getByText(t("seller:doubt.large"))).toBeVisible();
  await expect(
    page.getByText(t("seller:characteristics.progress", { done: 0, total: 1 })),
  ).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
  await page.getByText("Секционный", { exact: true }).click();
  await expect(
    page.getByText(t("seller:characteristics.progress", { done: 1, total: 1 })),
  ).toBeVisible();

  await page.getByRole("button", { name: t("seller:characteristics.toCard") }).click();
  await expect(page.getByText(t("seller:card.ready"))).toBeVisible();
  await page.getByRole("button", { name: t("seller:card.finish") }).click();
  const dialog = page.getByRole("dialog", { name: t("seller:card.dialogTitle") });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Секционный")).toBeVisible();
  await expectAccessible(page);
  await dialog.getByRole("button", { name: t("seller:card.confirm") }).click();

  await expect(page).toHaveURL(/\/cards\/session-1$/);
  const created = page.getByRole("dialog", { name: t("seller:final.createdTitle") });
  await expect(created).toBeVisible();
  await expectAccessible(page);
  await created.getByRole("button", { name: t("seller:final.toCard") }).click();
  await expect(created).toBeHidden();
  await expect(
    page.getByRole("heading", { level: 1, name: "Шкаф для одежды металлический" }),
  ).toBeVisible();
  await expect(page.getByText(t("seller:final.status"), { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: t("seller:card.download") })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});
