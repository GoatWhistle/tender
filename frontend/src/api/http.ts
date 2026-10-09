import { NotFound } from "./types";
import type { ProductQuery, SellerApi, StorefrontApi } from "./types";

// Эндпоинты витрины на бэкенде — `/api/v1/storefront/...`; фильтры — повторяющийся
// параметр `f=<код характеристики>:<код значения>`.
const BASE = "/api/v1/storefront";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (res.status === 404) throw new NotFound(url);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

function get<T>(path: string, params?: URLSearchParams): Promise<T> {
  const qs = params?.toString();
  return request(`${BASE}${path}${qs ? `?${qs}` : ""}`);
}

function send<T>(method: "POST" | "PATCH", url: string, body?: unknown): Promise<T> {
  return request(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
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

// Сессии карточки поставщика — `/api/v1/sessions/...` (раздел 12.1 плана).
const SESSIONS = "/api/v1/sessions";

export const sellerApi: SellerApi = {
  create: (text) => send("POST", SESSIONS, { text }),
  get: (id) => request(`${SESSIONS}/${encodeURIComponent(id)}`),
  message: (id, text) => send("POST", `${SESSIONS}/${encodeURIComponent(id)}/messages`, { text }),
  answer: (id, questionId, option) =>
    send("POST", `${SESSIONS}/${encodeURIComponent(id)}/answers`, {
      question_id: questionId,
      option,
    }),
  editFact: (id, key, valueCode) =>
    send("PATCH", `${SESSIONS}/${encodeURIComponent(id)}/facts/${encodeURIComponent(key)}`, {
      value_code: valueCode,
    }),
  export: (id) => send("POST", `${SESSIONS}/${encodeURIComponent(id)}/export`),
};
