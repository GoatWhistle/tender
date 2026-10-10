// Контракт витрины. Мок (`mock.ts`) и HTTP-клиент (`http.ts`) реализуют один `StorefrontApi`.

export type Category = {
  name: string;
  slug: string;
  positions: number;
  products: number;
};

export type PositionSummary = {
  code: string;
  name: string;
  category: string;
  okpd2: string;
  okpd2_name: string;
  products: number;
  min_price: number | null;
};

export type CharValue = { code: string; label: string; unit: string | null };

export type Characteristic = {
  code: string;
  name: string;
  quantitative: boolean;
  required: boolean;
  multi: boolean;
  values: CharValue[];
};

export type Position = PositionSummary & {
  units: string[];
  characteristics: Characteristic[];
};

/** Значение характеристики в карточке: код допустимого значения КТРУ и нормализованная запись. */
export type ProductValue = {
  value_code: string;
  label: string;
  unit: string | null;
  number: number | null;
};

export type ProductSummary = {
  id: string;
  title: string;
  position_code: string;
  position_name: string;
  category: string;
  price: number;
  offers: number;
  supplier: string;
  required_filled: number;
  required_total: number;
  /** код характеристики → значение; для колонок таблицы */
  values: Record<string, ProductValue>;
};

export type Product = ProductSummary & {
  position: Position;
};

export type FacetValue = { code: string; label: string; unit: string | null; count: number };

/** Фасет — характеристика позиции КТРУ; значения — её допустимые значения из справочника. */
export type Facet = {
  code: string;
  name: string;
  quantitative: boolean;
  values: FacetValue[];
};

export type Sort = "relevance" | "price_asc" | "price_desc" | "filled";

export type ProductQuery = {
  category?: string;
  position?: string;
  q?: string;
  /** код характеристики → коды допустимых значений; внутри — ИЛИ, между — И */
  filters?: Record<string, string[]>;
  sort?: Sort;
  page?: number;
  pageSize?: number;
};

export type ProductPage = {
  items: ProductSummary[];
  total: number;
  page: number;
  pages: number;
  /** позиции КТРУ в выдаче без учёта выбранной позиции */
  positions: (PositionSummary & { count: number })[];
  /** фасеты характеристик — только когда выбрана позиция */
  facets: Facet[];
};

export interface StorefrontApi {
  categories(): Promise<Category[]>;
  positions(category?: string): Promise<PositionSummary[]>;
  position(code: string): Promise<Position>;
  products(query: ProductQuery): Promise<ProductPage>;
  product(id: string): Promise<Product>;
}

export class NotFound extends Error {}

// ---------- Сессия поставщика: описание → группа КТРУ → позиции ----------
// Зеркало `SessionState` бэкенда (`/api/docs`, `docs/sessions.md`). UI ничего не пересчитывает.

export type SessionStatus =
  | "draft"
  | "needs_clarification"
  /** «Код определён»: осталась одна позиция; заполненность карточки — `card_complete` */
  | "resolved"
  /** позиции неразличимы по полям справочника — `common_fields` */
  | "ambiguous_in_catalog"
  /** нет совместимых позиций */
  | "conflict"
  | "technical_error"
  /** зарезервирован бэкендом, пока не выставляется */
  | "out_of_scope";

export type SessionMessage = { id: string; text: string; created_at: string };

export type NarrowingPath = {
  category: string;
  group: { code: string; name: string; role?: "group_template" };
  positions: number;
};

export type MethodContribution = { rank: number | null; contribution: number };

export type Alternative = {
  code: string;
  name: string;
  category: string;
  score: number;
  methods: Record<string, MethodContribution>;
};

export type ExclusionReason = {
  fact_id: string;
  characteristic: string;
  allowed: string;
  given: string;
  text: string;
};

export type Candidate = {
  role?: "ktru_position";
  code: string;
  name: string;
  excluded: boolean;
  reason: ExclusionReason | null;
  returned_reason?: string | null;
};

export type FactStatus =
  | "accepted_from_text"
  | "accepted_from_model"
  | "proposed"
  | "ambiguous"
  | "confirmed_by_user"
  | "derived_from_catalog"
  | "superseded"
  | "deleted";

export type Fact = {
  component?: string | null;
  superseded_by?: string | null;
  id: string;
  characteristic_name: string | null;
  raw_value: string;
  raw_unit: string | null;
  /** decimal-строка, диапазон из двух строк или текст */
  value: string | [string, string];
  unit_code: string | null;
  kind: "number" | "range" | "text" | "interval";
  origin: "parser" | "user" | "catalog" | "decision";
  status: FactStatus;
  source: { message_id: string; quote: string; start: number; end: number } | null;
};

export type EnumAction = "accept" | "choose" | "unknown";
export type EnumProposal = {
  id: string;
  characteristic: string;
  suggested: string[];
  options: string[];
  selections: { values: string[]; multiple: boolean }[];
  reason: string;
};

export type QuestionOption = { id: string; label: string };

export type Question = {
  question_id: string;
  kind: "conflict" | "discriminate" | "required" | "purpose";
  characteristic: string;
  text: string;
  options: QuestionOption[];
  allow_unknown: boolean;
};

export type DialogTurn = {
  question_id: string;
  kind: Question["kind"];
  clarification?: string | null;
  characteristic: string;
  revision: number;
  messages: number;
  /** null — «не знаю» */
  option_id: string | null;
  fact: Fact | null;
  /** группа вопроса: после смены группы ответ не применяется */
  group: string;
};

export type AnalysisError = { code: string; message: string };

export type Diagnostic = {
  kind: "typo" | "value_not_in_catalog" | "out_of_range" | "synonym";
  fact_id: string | null;
  source_quote: string;
  source: { message_id: string; quote: string; start: number; end: number };
  expected: string[];
  suggestion: string | null;
  candidates: string[];
  rule_ref: {
    position_code: string;
    characteristic_code: string;
    characteristic_name: string;
    value_codes: string[];
  }[];
  scope: { group_code: string | null; position_codes: string[]; complete: boolean };
  requires_confirmation: boolean;
  explanation: string;
  alias_source: string | null;
};

export const isDiagnostic = (error: AnalysisError | Diagnostic): error is Diagnostic =>
  "kind" in error;

export type SessionState = {
  session_id: string;
  revision: number;
  /** незнакомое значение возможно: бэкенд может добавить статус раньше фронта */
  status: SessionStatus | (string & {});
  messages: SessionMessage[];
  path: NarrowingPath | null;
  group_checks?: {
    code: string;
    name: string;
    verdict: "supported" | "contradicted" | "not_stated";
    scores: Record<string, number>;
    support_scores: Record<string, number> | null;
    criterion: string;
    model_revision: string;
    analysis_revision: number;
    role: "group_template";
  }[];
  alternatives: Alternative[];
  candidates: Candidate[];
  candidate_counts: { in_group: number; compatible: number; excluded_by_rules: number };
  facts: Fact[];
  fact_history?: {
    action: string;
    revision: number;
    created_at: string;
    before: Fact[];
    after: Fact[];
    group: string;
  }[];
  results_stale?: boolean;
  analysis_revision?: number | null;
  editable_fields?: string[];
  errors: (AnalysisError | Diagnostic)[];
  normalizations?: Diagnostic[];
  warnings: string[];
  next_question: Question | null;
  dialog: DialogTurn[];
  /** код определён и обязательные поля выбранной позиции заполнены */
  card_complete: boolean;
  missing_required: { characteristic: string; name: string }[];
  /** только при `ambiguous_in_catalog` */
  common_fields: { characteristic: string; values: string[] }[];
  /** различающие характеристики, на которые ответили «не знаю» */
  unanswered: string[];
  unsupported_rules: { position: string; characteristic: string }[];
  enum_proposals: EnumProposal[];
};

export type FactValue = {
  characteristic_name: string;
  raw_value: string;
  raw_unit?: string | null;
  kind: "text" | "number" | "range" | "interval";
  component?: string | null;
};
export type FactMutation = Partial<FactValue> & {
  expected_revision: number;
  action: "edit" | "delete" | "restore" | "confirm" | "split" | "accept_suggestion";
  related_ids?: string[];
  bindings?: FactValue[];
  diagnostic_index?: number;
};

export interface SellerApi {
  mutate(id: string, factId: string | null, body: FactMutation): Promise<SessionState>;
  recalculate(id: string, revision: number): Promise<SessionState>;
  /** Подтвердить предложение в ожидаемой ревизии сессии. */
  resolveEnum(
    id: string,
    revision: number,
    proposalId: string,
    action: EnumAction,
    values: string[],
  ): Promise<SessionState>;
  /** POST /api/v1/sessions без тела */
  create(): Promise<SessionState>;
  get(id: string): Promise<SessionState>;
  /** idempotencyKey — заголовок `Idempotency-Key`, свой на каждую попытку */
  message(id: string, text: string, idempotencyKey: string): Promise<SessionState>;
  /** optionId = null — «не знаю»; вопрос не из последней ревизии — 409 `stale_question` */
  answer(id: string, questionId: string, optionId: string | null): Promise<SessionState>;
}

/** Ответ API с телом ошибки `{code, message}` или без него (422 FastAPI, 5xx прокси). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | null,
    message: string,
  ) {
    super(message);
  }
}

/** Запрос не дошёл до сервера или ответ не прочитан. */
export class NetworkError extends Error {}
