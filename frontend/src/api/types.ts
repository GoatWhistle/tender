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
