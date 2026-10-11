import type { Page, Route } from "@playwright/test";
import type {
  CatalogComparison,
  CatalogFound,
  CatalogPosition,
  Characteristic,
  Outcome,
  Search,
  SearchCandidate,
  Session,
} from "../../src/entities/rag";

const candidate = (code: string, name: string, relevance: number | null): SearchCandidate => ({
  id: code,
  code,
  name,
  okpd2: code.slice(0, 12),
  relevance,
  reason: relevance === null ? null : "Совпадает назначение и материал",
  differences: { "Вид товара": "Секция шкафа; Шкаф" },
});

const all = [
  candidate("31.01.11.121-00000004", "Шкаф для одежды металлический", null),
  candidate("31.01.11.129-00000001", "Шкаф сушильный для одежды", null),
  candidate("31.01.12.131-00000003", "Шкаф для одежды деревянный", null),
];

const base: Omit<Search, "stage" | "candidates" | "rejected"> = {
  id: "search-1",
  description: "Шкаф для одежды металлический, глубина 0,55 м",
  corrected: "Шкаф для одежды металлический, глубина 0,55 м",
  fixes: [],
  issues: [],
  auto_select_code: null,
  auto_select_reason: null,
};

const ranked: Search = {
  ...base,
  stage: "ranked",
  candidates: [
    { ...all[0], relevance: 95 } as SearchCandidate,
    { ...all[2], relevance: 40 } as SearchCandidate,
  ],
  rejected: [all[1] as SearchCandidate],
};

const characteristic = (patch: Partial<Characteristic>): Characteristic => ({
  name: "Тип шкафа",
  required: true,
  multiple: false,
  options: ["Отдельно стоящий (Цельнокорпусный)", "Секционный"],
  values: [],
  origin: null,
  unit: null,
  bands: [],
  number: null,
  warning: null,
  ...patch,
});

const session = (patch: Partial<Session>): Session => ({
  id: "session-1",
  stage: "clarify",
  description: base.description,
  corrected: base.corrected,
  fixes: [],
  issues: [],
  groups: [
    {
      code: "31.01.11.121-00000004",
      name: "Шкаф для одежды металлический",
      okpd2: "31.01.11.121",
      relevance: 95,
      reason: "Совпадает назначение",
    },
  ],
  group: "31.01.11.121-00000004",
  answers: {},
  candidates: [
    {
      code: "31.01.11.121-00000001",
      name: "Шкаф для одежды металлический",
      differences: { "Вид товара": "Секция шкафа" },
    },
    {
      code: "31.01.11.121-00000003",
      name: "Шкаф для одежды металлический",
      differences: { "Вид товара": "Шкаф" },
    },
  ],
  question: {
    name: "Вид товара",
    required: true,
    multiple: false,
    options: ["Секция шкафа", "Шкаф"],
    counts: [1, 1],
  },
  position: null,
  characteristics: [],
  extras: [],
  extras_allowed: true,
  missing: [],
  message: null,
  selection_reason: null,
  messages: [],
  ...patch,
});

const position = {
  code: "31.01.11.121-00000003",
  name: "Шкаф для одежды металлический",
  okpd2: "31.01.11.121",
  okpd2_name: "Шкафы для одежды металлические",
  fixed: { "Вид товара": "Шкаф" },
};

const spec = session({
  stage: "spec",
  question: null,
  candidates: [{ code: position.code, name: position.name, differences: {} }],
  position,
  characteristics: [
    characteristic({}),
    characteristic({
      name: "Глубина",
      required: false,
      options: [],
      unit: "Миллиметр",
      number: 5500,
      warning: "large",
      origin: "description",
      bands: [
        { option: "≥ 500 < 600", min: 500, min_inclusive: true, max: 600, max_inclusive: false },
      ],
    }),
  ],
  missing: ["Тип шкафа"],
});

const filled = session({
  ...spec,
  characteristics: [
    characteristic({ values: ["Секционный"], origin: "manual" }),
    ...spec.characteristics.slice(1),
  ],
  missing: [],
});

const outcome: Outcome = {
  code: position.code,
  name: position.name,
  okpd2: position.okpd2,
  okpd2_name: position.okpd2_name,
  fixed: position.fixed,
  chosen: { "Тип шкафа": ["Секционный"] },
  entered: { Глубина: 5500 },
  doubts: { Глубина: "large" },
  extras: [],
};

const first: CatalogFound = {
  code: position.code,
  name: position.name,
  okpd2: position.okpd2,
  okpd2_name: position.okpd2_name,
};

const found: CatalogFound[] = [first];

const catalogPosition: CatalogPosition = {
  ...first,
  units: ["Штука"],
  rubrics: ["Мебель"],
  characteristics: [
    { code: "a", name: "Вид товара", kind: "1", required: true, values: ["Шкаф"] },
    { code: "b", name: "Тип шкафа", kind: "2", required: true, values: ["Секционный"] },
  ],
};

const comparison: CatalogComparison = {
  positions: [first, { ...first, code: "31.01.11.121-00000001" }],
  rows: [
    {
      field: "characteristic",
      name: "Вид товара",
      values: ["Шкаф", "Секция шкафа"],
      differs: true,
    },
    { field: "units", name: null, values: [["Штука"], ["Штука"]], differs: false },
  ],
};

export async function mockRag(page: Page): Promise<void> {
  let current: Session = session({});
  const json = (route: Route, body: unknown) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  await page.route(
    (url) => url.pathname.startsWith("/rag/"),
    async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/^\/rag/, "");
      const method = route.request().method();
      if (path === "/searches")
        return json(route, { ...base, stage: "candidates", candidates: all, rejected: [] });
      if (path.endsWith("/candidates"))
        return json(route, { ...base, stage: "candidates", candidates: all, rejected: [] });
      if (path.endsWith("/rerank")) return json(route, ranked);
      if (path.endsWith("/select")) return json(route, (current = session({})));
      if (path.endsWith("/answer")) return json(route, (current = spec));
      if (path.endsWith("/characteristics")) return json(route, (current = filled));
      if (path.endsWith("/finish")) {
        current = session({ ...filled, stage: "done" });
        return json(route, outcome);
      }
      if (path.startsWith("/sessions/") && method === "GET") return json(route, current);
      if (path === "/catalog/compare") return json(route, comparison);
      if (path === "/catalog") return json(route, found);
      if (path.startsWith("/catalog/")) return json(route, catalogPosition);
      return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    },
  );
}
