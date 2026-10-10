import { describe, expect, it } from "vitest";
import { resources } from "./resources";
import { hasKey, t } from "./t";

function leaves(node: unknown, prefix = ""): string[] {
  if (typeof node === "string") return [prefix];
  return Object.entries(node as Record<string, unknown>).flatMap(([k, v]) =>
    leaves(v, prefix ? `${prefix}.${k}` : k),
  );
}

describe("t", () => {
  it("подставляет переменные и форматирует числа", () => {
    expect(t("seller:characteristics.progress", { done: 1, total: 12 })).toBe(
      "Заполнено обязательных: 1 из 12",
    );
    expect(t("seller:describe.counter", { length: 3800, max: 4000 })).toMatch(/^3\s800 из 4\s000/);
  });

  it("выбирает форму множественного числа", () => {
    expect(t("seller:position.alternatives", { count: 1 })).toBe("Похожая группа: 1");
    expect(t("seller:position.alternatives", { count: 3 })).toBe("Похожие группы: 3");
  });

  it("узнаёт существующие ключи", () => {
    expect(hasKey("common:actions.next")).toBe(true);
    expect(hasKey("common:actions.missing")).toBe(false);
  });

  it("в текстах нет длинных тире и точек-разделителей", () => {
    const texts = Object.values(resources).flatMap((ns) =>
      leaves(ns).map((path) =>
        path.split(".").reduce<unknown>((n, k) => (n as Record<string, unknown>)[k], ns),
      ),
    );
    for (const text of texts) {
      expect(text).not.toMatch(/ — | · /);
    }
  });
});
