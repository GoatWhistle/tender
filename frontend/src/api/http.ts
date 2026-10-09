import { NotFound } from "./types";
import type { StorefrontApi, ProductQuery } from "./types";

// Эндпоинты витрины на бэкенде — `/api/v1/storefront/...`; фильтры — повторяющийся
// параметр `f=<код характеристики>:<код значения>`.
const BASE = "/api/v1/storefront";

async function get<T>(path: string, params?: URLSearchParams): Promise<T> {
  const qs = params?.toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);
  if (res.status === 404) throw new NotFound(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function productParams(q: ProductQuery): URLSearchParams {
  const p = new URLSearchParams();
  if (q.category) p.set("category", q.category);
  if (q.position) p.set("position", q.position);
  if (q.q) p.set("q", q.q);
  if (q.sort) p.set("sort", q.sort);
  if (q.page) p.set("page", String(q.page));
  if (q.pageSize) p.set("page_size", String(q.pageSize));
  for (const [ch, values] of Object.entries(q.filters ?? {}))
    for (const v of values) p.append("f", `${ch}:${v}`);
  return p;
}

export const httpApi: StorefrontApi = {
  categories: () => get("/categories"),
  positions: (category) =>
    get("/positions", category ? new URLSearchParams({ category }) : undefined),
  position: (code) => get(`/positions/${encodeURIComponent(code)}`),
  products: (query) => get("/products", productParams(query)),
  product: (id) => get(`/products/${encodeURIComponent(id)}`),
};
