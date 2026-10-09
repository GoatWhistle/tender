// Логика мок-сервиса витрины: выдача, фасеты, сортировка — как ожидаем от бэкенда.
// Данные — `fixtures.json` (собирает `scripts/build_mock.py`).
import type {
  Category,
  Facet,
  Position,
  PositionSummary,
  Product,
  ProductPage,
  ProductQuery,
  ProductSummary,
} from "../src/api/types.ts";
import { CATEGORIES } from "../src/lib/categories.ts";

export class Missing extends Error {}

export type RawPosition = Omit<Position, "products" | "min_price">;
export type RawProduct = Omit<Product, "position" | "position_name" | "required_filled" | "required_total">;

export type Fixtures = { positions: RawPosition[]; products: RawProduct[] };

export function createCatalog(data: Fixtures) {
  const positionByCode = new Map(data.positions.map((p) => [p.code, p]));

  const summaryOf = (p: RawPosition): PositionSummary => {
    const own = data.products.filter((x) => x.position_code === p.code);
    return {
      code: p.code,
      name: p.name,
      category: p.category,
      okpd2: p.okpd2,
      okpd2_name: p.okpd2_name,
      products: own.length,
      min_price: own.length ? Math.min(...own.map((x) => x.price)) : null,
    };
  };
  const positionOf = (p: RawPosition): Position => ({ ...p, ...summaryOf(p) });

  const productSummary = (x: RawProduct): ProductSummary => {
    const pos = positionByCode.get(x.position_code)!;
    const required = pos.characteristics.filter((c) => c.required);
    return {
      id: x.id,
      title: x.title,
      position_code: x.position_code,
      position_name: pos.name,
      category: x.category,
      price: x.price,
      offers: x.offers,
      supplier: x.supplier,
      required_filled: required.filter((c) => c.code in x.values).length,
      required_total: required.length,
    };
  };

  const matchesText = (x: RawProduct, q: string) => {
    const hay = `${x.title} ${positionByCode.get(x.position_code)!.name} ${x.position_code}`;
    return q
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .every((t) => hay.toLowerCase().includes(t));
  };

  const matchesFilters = (x: RawProduct, filters: Record<string, string[]>, skip?: string) =>
    Object.entries(filters).every(
      ([ch, values]) => ch === skip || !values.length || values.includes(x.values[ch]?.value_code),
    );

  const products = (query: ProductQuery): ProductPage => {
    const filters = query.position ? (query.filters ?? {}) : {};
    const base = data.products.filter(
      (x) =>
        (!query.category || x.category === query.category) &&
        (!query.q || matchesText(x, query.q)),
    );

    const counts = new Map<string, number>();
    for (const x of base) counts.set(x.position_code, (counts.get(x.position_code) ?? 0) + 1);
    const positions = [...counts].map(([code, count]) => ({
      ...summaryOf(positionByCode.get(code)!),
      count,
    }));

    const inPosition = base.filter((x) => !query.position || x.position_code === query.position);
    const hits = inPosition.filter((x) => matchesFilters(x, filters));

    const facets: Facet[] = [];
    const pos = query.position ? positionByCode.get(query.position) : undefined;
    for (const ch of pos?.characteristics ?? []) {
      // счётчики фасета — без его собственного фильтра, чтобы можно было расширить выбор
      const pool = inPosition.filter((x) => matchesFilters(x, filters, ch.code));
      const values = ch.values
        .map((v) => ({
          code: v.code,
          label: v.label,
          unit: v.unit,
          count: pool.filter((x) => x.values[ch.code]?.value_code === v.code).length,
        }))
        .filter((v) => v.count > 0 || filters[ch.code]?.includes(v.code));
      if (values.length)
        facets.push({ code: ch.code, name: ch.name, quantitative: ch.quantitative, values });
    }

    const items = hits.map(productSummary);
    if (query.sort === "price_asc") items.sort((a, b) => a.price - b.price);
    if (query.sort === "price_desc") items.sort((a, b) => b.price - a.price);
    if (query.sort === "filled")
      items.sort(
        (a, b) =>
          b.required_filled / (b.required_total || 1) - a.required_filled / (a.required_total || 1),
      );

    const pageSize = query.pageSize ?? 24;
    const pages = Math.max(1, Math.ceil(items.length / pageSize));
    const page = Math.min(Math.max(1, query.page ?? 1), pages);
    return {
      items: items.slice((page - 1) * pageSize, page * pageSize),
      total: items.length,
      page,
      pages,
      positions,
      facets,
    };
  };

  return {
    categories: (): Category[] =>
      CATEGORIES.map(({ name, slug }) => ({
        name,
        slug,
        positions: data.positions.filter((p) => p.category === name).length,
        products: data.products.filter((x) => x.category === name).length,
      })),

    positions: (category?: string): PositionSummary[] =>
      data.positions.filter((p) => !category || p.category === category).map(summaryOf),

    position: (code: string): Position => {
      const p = positionByCode.get(code);
      if (!p) throw new Missing(code);
      return positionOf(p);
    },

    product: (id: string): Product => {
      const x = data.products.find((p) => p.id === id);
      if (!x) throw new Missing(id);
      return {
        ...productSummary(x),
        values: x.values,
        position: positionOf(positionByCode.get(x.position_code)!),
      };
    },

    products,
  };
}
