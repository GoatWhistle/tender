import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { createSeller, type SPosition } from "./seller.ts";

const fixtures = JSON.parse(readFileSync(new URL("./fixtures.json", import.meta.url), "utf8")) as {
  positions: SPosition[];
};
const seller = () => createSeller(fixtures.positions);
const fact = (st: ReturnType<ReturnType<typeof seller>["get"]>, name: string) =>
  st.facts.find((f) => f.name === name);

describe("мок карточки поставщика", () => {
  it("исправляет опечатку и извлекает значения по позиции", () => {
    const st = seller().create("Стол письменный угловой, деревяный каркас, столешница ЛДСП");
    expect(st.position?.name).toBe("Стол письменный");
    expect(st.issues.map((i) => i.kind)).toContain("typo");
    expect(fact(st, "Тип каркаса")?.value).toBe("Деревянный");
    expect(fact(st, "Вид материала столешницы")?.value).toBe("ЛДСП");
    // одно слово «ЛДСП» не засчитывается двум характеристикам
    expect(fact(st, "Вид материала каркаса")).toBeUndefined();
  });

  it("сужает кандидатов и спрашивает позицию, затем обязательные поля", () => {
    const api = seller();
    let st = api.create("Шкаф для одежды");
    expect(st.candidate_counts.compatible).toBeGreaterThan(1);
    expect(st.next_question?.kind).toBe("position");
    const metal = st.next_question!.options.find((o) => o.label === "Шкаф для одежды металлический")!;
    st = api.answer(st.session_id, st.next_question!.id, metal.code);
    expect(st.position?.code).toBe(metal.code);
    expect(st.candidates.filter((c) => c.compatible)).toHaveLength(1);
    expect(st.next_question?.kind).toBe("characteristic");
  });

  it("исключает позиции с противоположным материалом и объясняет почему", () => {
    const st = seller().create("Шкаф для одежды металлический");
    const wooden = st.candidates.find((c) => c.name === "Шкаф для одежды деревянный")!;
    expect(wooden.compatible).toBe(false);
    expect(wooden.reason).toMatch(/металлический/);
  });

  it("переводит единицы и ловит чужую размерность и неправдоподобные числа", () => {
    const st = seller().create(
      "Электролобзик, мощность 5 кг, толщина дерева 8 см, толщина металла 400 мм",
    );
    expect(fact(st, "Максимальная толщина обрабатываемого дерева")).toMatchObject({
      value: "80 мм",
      raw: "8 см",
      state: "accepted",
    });
    expect(fact(st, "Мощность")?.state).toBe("error");
    expect(st.issues.map((i) => i.kind)).toEqual(expect.arrayContaining(["unit", "range"]));
  });

  it("сообщает о значении, которого нет в справочнике", () => {
    const st = seller().create("Электролобзик, тип питания: солнечная батарея");
    expect(st.issues.find((i) => i.kind === "unknown_value")?.detail).toMatch(/От сети/);
  });

  it("без распознанного товара — конкретные шаги", () => {
    const st = seller().create("Хорошая вещь недорого");
    expect(st.status).toBe("no_match");
    expect(st.issues[0].detail).toMatch(/стол письменный/);
  });

  it("«не знаю» оставляет черновик с незаполненными обязательными полями", () => {
    const api = seller();
    let st = api.create("Шуруповерт с ударом");
    while (st.next_question) st = api.answer(st.session_id, st.next_question.id, null);
    expect(st.status).toBe("draft");
    expect(st.card_complete).toBe(false);
    expect(st.missing_required.length).toBeGreaterThan(0);
  });

  it("правка факта значением из справочника", () => {
    const api = seller();
    let st = api.create("Стол письменный угловой");
    const opts = st.editable["Конфигурация стола"];
    const straight = opts.find((o) => o.label === "Прямой")!;
    st = api.editFact(st.session_id, "Конфигурация стола", straight.code);
    expect(fact(st, "Конфигурация стола")).toMatchObject({ value: "Прямой", source: "edit" });
  });

  it("устаревший вопрос отклоняется", () => {
    const api = seller();
    const st = api.create("Шкаф для одежды");
    api.message(st.session_id, "металлический");
    expect(() => api.answer(st.session_id, st.next_question!.id, null)).toThrow(/устарел/);
  });
});
