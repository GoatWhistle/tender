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
  group: { code: string; name: string };
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
  code: string;
  name: string;
  excluded: boolean;
  reason: ExclusionReason | null;
};

export type FactStatus =
  "accepted_from_text" | "ambiguous" | "confirmed_by_user" | "derived_from_catalog" | "superseded";

export type Fact = {
  id: string;
  characteristic_name: string | null;
  raw_value: string;
  raw_unit: string | null;
  /** decimal-строка, диапазон из двух строк или текст */
  value: string | [string, string];
  unit_code: string | null;
  kind: "number" | "range" | "text" | "interval";
  origin: "parser" | "user" | "catalog";
  status: FactStatus;
  source: { message_id: string; quote: string; start: number; end: number } | null;
};

export type QuestionOption = { id: string; label: string };

export type Question = {
  question_id: string;
  kind: "conflict" | "discriminate" | "required";
  characteristic: string;
  text: string;
  options: QuestionOption[];
  allow_unknown: boolean;
};

export type DialogTurn = {
  question_id: string;
  kind: Question["kind"];
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

export type SessionState = {
  session_id: string;
  revision: number;
  /** незнакомое значение возможно: бэкенд может добавить статус раньше фронта */
  status: SessionStatus | (string & {});
  messages: SessionMessage[];
  path: NarrowingPath | null;
  alternatives: Alternative[];
  candidates: Candidate[];
  candidate_counts: { in_group: number; compatible: number; excluded_by_rules: number };
  facts: Fact[];
  errors: AnalysisError[];
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
};

export interface SellerApi {
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
