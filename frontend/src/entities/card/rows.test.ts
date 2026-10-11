import { describe, expect, it } from "vitest";
import type { Characteristic, Session } from "../rag";
import { buildRows, completeness, needsAction } from "./rows";

const characteristic = (patch: Partial<Characteristic>): Characteristic => ({
  name: "Цвет",
  required: false,
  multiple: false,
  options: [],
  values: [],
  ...patch,
});

const session = (
  characteristics: Characteristic[],
  fixed: Record<string, string> = {},
): Session => ({
  id: "s",
  stage: "spec",
  description: "",
  corrected: "",
  fixes: [],
  issues: [],
  groups: [],
  group: "g",
  answers: {},
  candidates: [],
  question: null,
  position: { code: "c", name: "n", okpd2: "o", okpd2_name: "on", fixed },
  characteristics,
  extras: [],
  extras_allowed: true,
  missing: [],
  message: null,
  selection_reason: null,
  messages: [],
});

describe("строки характеристик", () => {
  it("ставят незаполненные обязательные и сомнительные первыми", () => {
    const rows = buildRows(
      session(
        [
          characteristic({ name: "Цвет", values: ["Белый"] }),
          characteristic({ name: "Высота", number: 9000, warning: "large" }),
          characteristic({ name: "Тип", required: true }),
          characteristic({ name: "Материал" }),
        ],
        { "Вид товара": "Шкаф" },
      ),
    );
    expect(rows.map((r) => r.name)).toEqual(["Тип", "Высота", "Цвет", "Вид товара", "Материал"]);
    expect(rows.filter(needsAction).map((r) => r.name)).toEqual(["Тип", "Высота"]);
  });

  it("принимают значение позиции строкой и списком", () => {
    const rows = buildRows(session([], { "Вид товара": "Шкаф" }));
    expect(rows[0]?.values).toEqual(["Шкаф"]);
    expect(rows[0]?.status).toBe("fixed");
  });

  it("считают заполненность только по редактируемым обязательным", () => {
    const rows = buildRows(
      session(
        [
          characteristic({ name: "Тип", required: true, values: ["Секционный"] }),
          characteristic({ name: "Ширина", required: true }),
        ],
        { "Вид товара": "Шкаф" },
      ),
    );
    expect(completeness(rows)).toEqual({ done: 1, total: 2 });
  });
});
