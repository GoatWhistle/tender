import type { Page } from "@playwright/test";
import type { Diagnostic, Fact, SessionState } from "../../src/api/types";

const ID = "e2e-session";
const MESSAGE = "m1";
const TEXT = "Шкаф для одежды металлический, глубина -5 см";

const fact = (patch: Partial<Fact>): Fact => ({
  id: "f-kind",
  characteristic_name: "Вид товара",
  raw_value: "Шкаф",
  raw_unit: null,
  value: "Шкаф",
  unit_code: null,
  kind: "text",
  origin: "parser",
  status: "accepted_from_text",
  source: null,
  ...patch,
});

const depth = fact({
  id: "f-depth",
  characteristic_name: "Глубина",
  raw_value: "-5",
  raw_unit: "см",
  value: "-5",
  kind: "number",
});

const outOfRange: Diagnostic = {
  kind: "out_of_range",
  fact_id: "f-depth",
  source_quote: "глубина -5 см",
  source: { message_id: MESSAGE, quote: "глубина -5 см", start: 31, end: 44 },
  expected: ["500..700 мм"],
  suggestion: "550 мм",
  candidates: [],
  rule_ref: [],
  scope: { group_code: null, position_codes: [], complete: true },
  requires_confirmation: true,
  explanation: "Глубина не может быть отрицательной.",
  alias_source: null,
};

const base: SessionState = {
  session_id: ID,
  revision: 0,
  status: "draft",
  messages: [],
  path: null,
  alternatives: [],
  candidates: [],
  candidate_counts: { in_group: 0, compatible: 0, excluded_by_rules: 0 },
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
};

const analysed: SessionState = {
  ...base,
  revision: 1,
  status: "needs_clarification",
  messages: [{ id: MESSAGE, text: TEXT, created_at: "2026-10-10T10:00:00Z" }],
  path: {
    category: "Мебель",
    group: { code: "31.01.11.121-00000004", name: "Шкаф для одежды металлический" },
    positions: 2,
  },
  alternatives: [
    {
      code: "31.01.11.121-00000009",
      name: "Шкаф хозяйственный",
      category: "Мебель",
      score: 0.4,
      methods: {},
    },
  ],
  candidates: [
    {
      code: "31.01.11.121-00000003",
      name: "Шкаф для одежды металлический",
      excluded: false,
      reason: null,
    },
    {
      code: "31.01.11.121-00000001",
      name: "Шкаф для одежды металлический",
      excluded: true,
      reason: {
        fact_id: "f-kind",
        characteristic: "Вид товара",
        allowed: "Секция",
        given: "Шкаф",
        text: "вид товара: секция шкафа",
      },
    },
  ],
  candidate_counts: { in_group: 2, compatible: 1, excluded_by_rules: 1 },
  facts: [fact({}), depth],
  errors: [outOfRange],
  next_question: {
    question_id: "q1",
    kind: "required",
    characteristic: "Тип шкафа",
    text: "Какое значение «Тип шкафа» у товара?",
    options: [
      { id: "o1", label: "Секционный" },
      { id: "o2", label: "Отдельно стоящий" },
    ],
    allow_unknown: true,
  },
  missing_required: [{ characteristic: "c-type", name: "Тип шкафа" }],
};

const answered: SessionState = {
  ...analysed,
  revision: 2,
  status: "resolved",
  next_question: null,
  missing_required: [],
  card_complete: true,
  facts: [
    fact({}),
    depth,
    fact({
      id: "f-type",
      characteristic_name: "Тип шкафа",
      raw_value: "Секционный",
      value: "Секционный",
      origin: "user",
      status: "confirmed_by_user",
    }),
  ],
};

const position = {
  code: "31.01.11.121-00000003",
  name: "Шкаф для одежды металлический",
  category: "Мебель",
  okpd2: "31.01.11.121",
  okpd2_name: "Шкафы для одежды металлические",
  characteristics: [
    {
      code: "c-kind",
      name: "Вид товара",
      quantitative: false,
      required: true,
      kind: "fixed",
      multi: false,
      values: [{ code: "v1", label: "Шкаф", text: "Шкаф", unit: null, min: null, max: null }],
    },
    {
      code: "c-type",
      name: "Тип шкафа",
      quantitative: false,
      required: true,
      kind: "single",
      multi: false,
      values: [
        { code: "v2", label: "Секционный", text: "Секционный", unit: null, min: null, max: null },
      ],
    },
    {
      code: "c-depth",
      name: "Глубина",
      quantitative: true,
      required: false,
      kind: "range",
      multi: false,
      values: [{ code: "v3", label: "", text: null, unit: "Миллиметр", min: 500, max: 700 }],
    },
    {
      code: "c-color",
      name: "Цвет",
      quantitative: false,
      required: false,
      kind: "single",
      multi: false,
      values: [],
    },
  ],
};

export async function mockSellApi(page: Page): Promise<void> {
  let state: SessionState = base;
  await page.route("**/api/v1/positions/**", (route) => route.fulfill({ json: position }));
  await page.route("**/api/v1/sessions**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "POST" && url.endsWith("/sessions")) state = base;
    else if (url.endsWith("/messages")) state = analysed;
    else if (url.endsWith("/answers")) state = answered;
    await new Promise((r) => setTimeout(r, 150));
    await route.fulfill({ json: state });
  });
}

export const SELL_TEXT = TEXT;
