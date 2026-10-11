import type {
  CatalogComparison,
  CatalogFound,
  CatalogPosition,
  Extra,
  Outcome,
  Search,
  Session,
  Suggestions,
  Verdict,
} from "./types";

export const RAG_BASE = "/rag";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | null,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal) {
  let response: Response;
  try {
    response = await fetch(`${RAG_BASE}${path}`, {
      method,
      signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network", String(error));
  }
  const text = await response.text();
  const data: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data as { detail?: unknown; code?: unknown } | null;
    const message = typeof detail?.detail === "string" ? detail.detail : response.statusText;
    const code = typeof detail?.code === "string" ? detail.code : null;
    throw new ApiError(response.status, code, message);
  }
  return data as T;
}

const s = (id: string) => `/sessions/${encodeURIComponent(id)}`;
const q = (id: string) => `/searches/${encodeURIComponent(id)}`;

export const ragApi = {
  startSearch: (description: string) => request<Search>("POST", "/searches", { description }),
  candidates: (id: string) => request<Search>("POST", `${q(id)}/candidates`),
  rerank: (id: string) => request<Search>("POST", `${q(id)}/rerank`),
  select: (id: string, code: string, automatic: boolean) =>
    request<Session>("POST", `${q(id)}/select`, { code, automatic }),
  session: (id: string) => request<Session>("GET", s(id)),
  answer: (id: string, body: { option: number } | { text: string }) =>
    request<Session>("POST", `${s(id)}/answer`, body),
  pick: (id: string, code: string) => request<Session>("POST", `${s(id)}/pick`, { code }),
  group: (id: string, code: string) => request<Session>("POST", `${s(id)}/group`, { code }),
  values: (id: string, name: string, values: readonly string[]) =>
    request<Session>("PATCH", `${s(id)}/characteristics`, { values: { [name]: values } }),
  number: (id: string, name: string, value: number | null) =>
    request<Session>("PUT", `${s(id)}/characteristics/number`, { name, value }),
  describe: (id: string, text: string, name: string | null) =>
    request<Session>("POST", `${s(id)}/characteristics/text`, { text, name }),
  message: (id: string, text: string) => request<Session>("POST", `${s(id)}/messages`, { text }),
  addExtra: (id: string, extra: Extra) => request<Verdict>("POST", `${s(id)}/extras`, extra),
  removeExtra: (id: string, n: number) => request<Session>("DELETE", `${s(id)}/extras/${n}`),
  suggest: (id: string) => request<Suggestions>("POST", `${s(id)}/suggestions`),
  finish: (id: string) => request<Outcome>("POST", `${s(id)}/finish`),
  find: (text: string, mode: "text" | "semantic" = "text", signal?: AbortSignal) =>
    request<CatalogFound[]>(
      "GET",
      `/catalog?q=${encodeURIComponent(text)}&mode=${mode}`,
      undefined,
      signal,
    ),
  position: (code: string, signal?: AbortSignal) =>
    request<CatalogPosition>("GET", `/catalog/${encodeURIComponent(code)}`, undefined, signal),
  compare: (codes: readonly string[], signal?: AbortSignal) =>
    request<CatalogComparison>(
      "GET",
      `/catalog/compare?${codes.map((c) => `codes=${encodeURIComponent(c)}`).join("&")}`,
      undefined,
      signal,
    ),
};
