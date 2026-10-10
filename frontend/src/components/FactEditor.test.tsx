import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import type { Fact, SessionState } from "../api/types";
import { createSellerSession } from "../lib/sellerSession";
import { FactForm } from "./FactEditor";

it("редактор модельного факта показывает принятое значение, а не цитату целиком", () => {
  const fact: Fact = {
    id: "model-fact",
    characteristic_name: "Материал",
    raw_value: "стул со стальным каркасом",
    raw_unit: null,
    value: "сталь",
    unit_code: null,
    kind: "text",
    origin: "decision",
    status: "confirmed_by_user",
    source: null,
  };
  const state: SessionState = {
    session_id: "s",
    revision: 1,
    status: "resolved",
    messages: [],
    path: null,
    alternatives: [],
    candidates: [],
    candidate_counts: { in_group: 0, compatible: 0, excluded_by_rules: 0 },
    facts: [fact],
    errors: [],
    warnings: [],
    next_question: null,
    dialog: [],
    card_complete: true,
    missing_required: [],
    common_fields: [],
    unanswered: [],
    unsupported_rules: [],
    enum_proposals: [],
  };
  const reply = async () => state;
  const store = createSellerSession({
    create: reply,
    get: reply,
    message: reply,
    answer: reply,
    mutate: reply,
    recalculate: reply,
    resolveEnum: reply,
  });
  const html = renderToStaticMarkup(
    <FactForm state={state} store={store} fact={fact} onClose={() => {}} />,
  );
  expect(html).toContain('value="сталь"');
  expect(html).not.toContain('value="стул со стальным каркасом"');
  expect(html).toContain("Часть товара");
  expect(html).toContain("Сохранить");
});
