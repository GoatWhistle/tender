import { describe, expect, it } from "vitest";
import { Missing, createCatalog } from "./catalog.ts";

const char = (code: string, required: boolean, values: string[]) => ({
  code,
  name: code,
  quantitative: false,
  required,
  multi: false,
  values: values.map((v) => ({ code: v, label: v, unit: null })),
});

const position = {
  code: "P1",
  name: "Стол письменный",
  category: "Мебель",
  okpd2: "31.01",
  okpd2_name: "Мебель офисная",
  units: ["Штука"],
  characteristics: [char("color", true, ["white", "black"]), char("legs", false, ["4", "2"])],
};

const product = (id: string, price: number, values: Record<string, string>) => ({
  id,
  title: `Стол ${id}`,
  position_code: "P1",
  category: "Мебель",
  price,
  offers: 1,
  supplier: "ООО",
  values: Object.fromEntries(
    Object.entries(values).map(([ch, v]) => [ch, { value_code: v, label: v, unit: null, number: null }]),
  ),
});

const api = createCatalog(
  {
    positions: [position],
    products: [
      product("a", 300, { color: "white", legs: "4" }),
      product("b", 100, { color: "black", legs: "4" }),
      product("c", 200, { legs: "2" }),
    ],
  },
);

describe("мок витрины", () => {
  it("фильтр: И между характеристиками, ИЛИ внутри", () => {
    const page = api.products({
      position: "P1",
      filters: { color: ["white", "black"], legs: ["4"] },
    });
    expect(page.items.map((x) => x.id).sort()).toEqual(["a", "b"]);
  });

  it("счётчики фасета не учитывают его собственный фильтр", () => {
    const page = api.products({ position: "P1", filters: { color: ["white"] } });
    const color = page.facets.find((f) => f.code === "color")!;
    expect(color.values.map((v) => [v.code, v.count])).toEqual([
      ["white", 1],
      ["black", 1],
    ]);
    const legs = page.facets.find((f) => f.code === "legs")!;
    expect(legs.values.map((v) => [v.code, v.count])).toEqual([["4", 1]]);
  });

  it("без позиции фильтры характеристик не применяются и фасетов нет", () => {
    const page = api.products({ filters: { color: ["white"] } });
    expect(page.total).toBe(3);
    expect(page.facets).toEqual([]);
  });

  it("сортировка по цене и полнота обязательных полей", () => {
    const page = api.products({ sort: "price_asc" });
    expect(page.items.map((x) => x.id)).toEqual(["b", "c", "a"]);
    expect(page.items.find((x) => x.id === "c")).toMatchObject({
      required_filled: 0,
      required_total: 1,
    });
  });

  it("поиск по названию и коду позиции", () => {
    expect((api.products({ q: "стол b" })).total).toBe(1);
    expect((api.products({ q: "P1" })).total).toBe(3);
  });

  it("неизвестный товар — Missing", () => {
    expect(() => api.product("zzz")).toThrow(Missing);
  });
});
