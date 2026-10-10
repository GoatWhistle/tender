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
  | "resolved"
  | "technical_error"
  /** зарезервированы бэкендом, пока не выставляются */
  | "out_of_scope"
  | "ambiguous_in_catalog"
  | "conflict";

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

export type Candidate = { code: string; name: string; excluded: boolean };

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
  /** пока всегда пуст */
  facts: unknown[];
  errors: AnalysisError[];
  warnings: string[];
  /** пока всегда null */
  next_question: unknown;
};

export interface SellerApi {
  /** POST /api/v1/sessions без тела */
  create(): Promise<SessionState>;
  get(id: string): Promise<SessionState>;
  /** idempotencyKey — заголовок `Idempotency-Key`, свой на каждую попытку */
  message(id: string, text: string, idempotencyKey: string): Promise<SessionState>;
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
