import { describe, expect, it } from "vitest";
import type { Characteristic, Session } from "../rag";
import { summarize } from "./summary";

const characteristic = (patch: Partial<Characteristic>): Characteristic => ({
  name: "Цвет",
  required: false,
  multiple: false,
  options: [],
  values: [],
  ...patch,
});

const group = (code: string) => ({ code, name: code, okpd2: "o", relevance: 90, reason: "" });

const session: Session = {
  id: "s",
  stage: "spec",
  description: "шкаф металический",
  corrected: "шкаф металлический",
  fixes: [{ before: "металический", after: "металлический", kind: "typo" }],
  issues: [],
  groups: [group("a"), group("b"), group("c")],
  group: "a",
  answers: { "Вид товара": "Шкаф" },
  candidates: [],
  question: null,
  position: { code: "c", name: "n", okpd2: "o", okpd2_name: "on", fixed: { "Вид товара": "Шкаф" } },
  characteristics: [
    characteristic({ name: "Тип", required: true, values: ["Секционный"], origin: "description" }),
    characteristic({ name: "Цвет", values: ["Белый"], origin: "manual" }),
    characteristic({ name: "Ширина", required: true }),
    characteristic({ name: "Материал" }),
  ],
  extras: [],
  extras_allowed: true,
  missing: ["Ширина"],
  message: null,
  selection_reason: null,
  messages: [],
};

describe("итог подбора", () => {
  it("считает автоматически заполненное без ручного, пустого и незаполненного", () => {
    expect(summarize(session)).toEqual({
      groups: 3,
      questions: 1,
      automatic: 2,
      total: 4,
      fixes: 1,
    });
  });
});
