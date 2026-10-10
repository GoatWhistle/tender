import { ApiError, NetworkError, NotFound } from "./types";
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

// Сессии поставщика — `/api/v1/sessions/...`, контракт в `docs/sessions.md`. Ошибки бэкенда —
// `{code, message}`; ответ без такого тела (422 FastAPI, 5xx прокси) — `ApiError` без кода.
const SESSIONS = "/api/v1/sessions";

async function sessionRequest<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    throw new NetworkError((e as Error).message);
  }
  const body = (await res.json().catch(() => undefined)) as unknown;
  if (res.ok) {
    if (body === undefined) throw new NetworkError("Ответ сервера не прочитан");
    return body as T;
  }
  const error = body as { code?: unknown; message?: unknown } | undefined;
  if (typeof error?.code === "string" && typeof error.message === "string")
    throw new ApiError(res.status, error.code, error.message);
  throw new ApiError(res.status, null, `${res.status} ${res.statusText}`.trim());
}

const session = (id: string) => `${SESSIONS}/${encodeURIComponent(id)}`;

export const sellerApi: SellerApi = {
  create: () => sessionRequest(SESSIONS, { method: "POST" }),
  get: (id) => sessionRequest(session(id)),
  message: (id, text, idempotencyKey) =>
    sessionRequest(`${session(id)}/messages`, {
      method: "POST",
      headers: { "content-type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ text }),
    }),
  answer: (id, questionId, optionId) =>
    sessionRequest(`${session(id)}/answers`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(
        optionId === null
          ? { question_id: questionId, unknown: true }
          : { question_id: questionId, option_id: optionId },
      ),
    }),
};
