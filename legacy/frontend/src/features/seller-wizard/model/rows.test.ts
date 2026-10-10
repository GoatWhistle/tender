import { describe, expect, it } from "vitest";
import type { Diagnostic, Fact, SessionState } from "../../../api/types";
import type { PositionDetail } from "../../../entities/position";
import { buildRows, completeness, unboundDiagnostics } from "./rows";
import { chosenPositionCode, reachableStep, stepIndex } from "./steps";

const fact = (patch: Partial<Fact>): Fact => ({
  id: "f1",
  characteristic_name: "Глубина",
  raw_value: "0,55",
  raw_unit: "м",
  value: "0.55",
  unit_code: null,
  kind: "number",
  origin: "parser",
  status: "accepted_from_text",
  source: null,
  ...patch,
});

const state = (patch: Partial<SessionState>): SessionState => ({
  session_id: "s",
  revision: 1,
  status: "needs_clarification",
  messages: [],
  path: { category: "Мебель", group: { code: "G", name: "Шкаф" }, positions: 2 },
  alternatives: [],
  candidates: [
    { code: "A", name: "Шкаф", excluded: false, reason: null },
    { code: "B", name: "Шкаф", excluded: true, reason: null },
  ],
  candidate_counts: { in_group: 2, compatible: 1, excluded_by_rules: 1 },
  facts: [],
  errors: [],
  warnings: [],
  next_question: null,
  dialog: [],
  card_complete: false,
  missing_required: [],
  common_fields: [],
  unanswered: [],
  unsupported_rules: [],
  enum_proposals: [],
  ...patch,
});

const position: PositionDetail = {
  code: "A",
  name: "Шкаф",
  category: "Мебель",
  okpd2: "31",
  okpd2_name: "Шкафы",
  characteristics: [
    {
      code: "c1",
      name: "Тип шкафа",
      quantitative: false,
      required: true,
      kind: "single",
      multi: false,
      values: [],
    },
    {
      code: "c2",
      name: "Глубина",
      quantitative: true,
      required: false,
      kind: "range",
      multi: false,
      values: [{ code: "v", label: "", text: null, unit: "мм", min: 500, max: 700 }],
    },
    {
      code: "c3",
      name: "Цвет",
      quantitative: false,
      required: false,
      kind: "single",
      multi: false,
      values: [],
    },
  ],
};

const diagnostic = (patch: Partial<Diagnostic>): Diagnostic => ({
  kind: "out_of_range",
  fact_id: "f1",
  source_quote: "глубина 0,55 м",
  source: { message_id: "m", quote: "", start: 0, end: 0 },
  expected: [],
  suggestion: "550 мм",
  candidates: [],
  rule_ref: [],
  scope: { group_code: null, position_codes: [], complete: true },
  requires_confirmation: true,
  explanation: "вне диапазона",
  alias_source: null,
  ...patch,
});

describe("buildRows", () => {
  it("ставит ошибку первой и связывает диагностику с фактом", () => {
    const rows = buildRows(state({ facts: [fact({})], errors: [diagnostic({})] }), position);
    expect(rows[0]?.name).toBe("Глубина");
    expect(rows[0]?.status).toBe("error");
    expect(rows[0]?.diagnostics).toHaveLength(1);
    expect(
      unboundDiagnostics(state({ facts: [fact({})], errors: [diagnostic({})] }), rows),
    ).toEqual([]);
  });

  it("отмечает пустую обязательную как незаполненную, необязательную как пустую", () => {
    const rows = buildRows(state({}), position);
    expect(rows.find((r) => r.name === "Тип шкафа")?.status).toBe("missing");
    expect(rows.find((r) => r.name === "Цвет")?.status).toBe("empty");
    expect(completeness(rows)).toEqual({ done: 0, total: 1 });
  });

  it("показывает вопрос по характеристике и факт без привязки", () => {
    const rows = buildRows(
      state({
        facts: [fact({ id: "f9", characteristic_name: null, raw_value: "80" })],
        next_question: {
          question_id: "q",
          kind: "required",
          characteristic: "Тип шкафа",
          text: "?",
          options: [],
          allow_unknown: true,
        },
      }),
      position,
    );
    expect(rows.find((r) => r.name === "Тип шкафа")?.status).toBe("question");
    expect(rows.find((r) => r.unbound)?.facts[0]?.id).toBe("f9");
  });

  it("не показывает удалённые и заменённые факты", () => {
    const rows = buildRows(state({ facts: [fact({ status: "deleted" })] }), position);
    expect(rows.find((r) => r.name === "Глубина")?.facts).toEqual([]);
  });
});

describe("steps", () => {
  it("открывает карточку только после определения позиции", () => {
    expect(reachableStep(null)).toBe(0);
    expect(reachableStep(state({}))).toBe(2);
    expect(reachableStep(state({ status: "resolved" }))).toBe(3);
    expect(reachableStep(state({ status: "technical_error" }))).toBe(0);
  });

  it("берёт единственную совместимую позицию, иначе группу", () => {
    expect(chosenPositionCode(state({}))).toBe("A");
    expect(
      chosenPositionCode(
        state({
          candidates: [
            { code: "A", name: "", excluded: false, reason: null },
            { code: "B", name: "", excluded: false, reason: null },
          ],
        }),
      ),
    ).toBe("G");
  });

  it("разбирает шаг из адреса", () => {
    expect(stepIndex("characteristics")).toBe(2);
    expect(stepIndex("unknown")).toBe(0);
    expect(stepIndex(null)).toBe(0);
  });
});
