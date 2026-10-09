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

// ---------- Карточка поставщика: описание → характеристики → код КТРУ ----------

export type SessionStatus =
  /** нечего анализировать: тип товара не распознан */
  | "no_match"
  /** нужен ответ: несколько кандидатов или пустые обязательные поля */
  | "needs_clarification"
  /** код выбран, но обязательные поля остались неизвестными */
  | "draft"
  /** код выбран и все обязательные поля заполнены */
  | "complete";

export type FactSource = "description" | "answer" | "edit";

/** Характеристика, извлечённая из описания или ответа. Ключ — название характеристики. */
export type Fact = {
  key: string;
  name: string;
  /** цитата из описания, из которой взято значение */
  quote: string | null;
  /** исходная запись до нормализации, если отличается: «1,2 м» */
  raw: string | null;
  /** нормализованное значение в единице позиции: «120 см» */
  value: string;
  value_code: string | null;
  unit: string | null;
  source: FactSource;
  state: "accepted" | "error";
  note: string | null;
};

export type IssueKind = "typo" | "unit" | "range" | "unknown_value" | "no_match" | "not_in_position";

export type Issue = {
  id: string;
  kind: IssueKind;
  /** что не так — коротко */
  title: string;
  /** почему и что сделать */
  detail: string;
  quote: string | null;
  suggestion: string | null;
};

export type Candidate = {
  code: string;
  name: string;
  category: string;
  compatible: boolean;
  /** почему исключена */
  reason: string | null;
};

export type QuestionOption = { code: string; label: string };

export type Question = {
  id: string;
  kind: "position" | "characteristic";
  text: string;
  hint: string | null;
  options: QuestionOption[];
  allow_unknown: boolean;
};

export type Message = { role: "user" | "system"; text: string };

export type SessionState = {
  session_id: string;
  revision: number;
  status: SessionStatus;
  messages: Message[];
  facts: Fact[];
  issues: Issue[];
  candidates: Candidate[];
  candidate_counts: { retrieved: number; compatible: number; excluded: number };
  position: { code: string; name: string; category: string; okpd2: string } | null;
  card_complete: boolean;
  /** обязательные характеристики выбранной позиции */
  required: string[];
  missing_required: string[];
  /** допустимые значения для правки фактов — по ключу факта; только когда позиция выбрана */
  editable: Record<string, QuestionOption[]>;
  next_question: Question | null;
};

export type ExportedCard = {
  draft: boolean;
  position_code: string | null;
  position_name: string | null;
  characteristics: { code: string; name: string; value: string; value_code: string | null }[];
  missing_required: string[];
};

export interface SellerApi {
  create(text: string): Promise<SessionState>;
  get(id: string): Promise<SessionState>;
  message(id: string, text: string): Promise<SessionState>;
  /** option — код варианта или null («не знаю») */
  answer(id: string, questionId: string, option: string | null): Promise<SessionState>;
  /** valueCode — новое значение из допустимых или null — удалить факт */
  editFact(id: string, key: string, valueCode: string | null): Promise<SessionState>;
  export(id: string): Promise<ExportedCard>;
}
