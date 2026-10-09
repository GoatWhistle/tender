// Мок-сервис API витрины: те же эндпоинты, что ждёт `src/api/http.ts`, на данных fixtures.json.
// Запуск: `npm run mock-api` (порт MOCK_PORT, по умолчанию 8001).
import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { ProductQuery, Sort } from "../src/api/types.ts";
import { Missing, createCatalog, type Fixtures } from "./catalog.ts";
import { Conflict, createSeller, type SPosition } from "./seller.ts";

const fixtures = JSON.parse(
  readFileSync(new URL("./fixtures.json", import.meta.url), "utf8"),
) as Fixtures;
const catalog = createCatalog(fixtures);
const seller = createSeller(fixtures.positions as unknown as SPosition[]);
const PORT = Number(process.env.MOCK_PORT ?? 8001);
const PREFIX = "/api/v1/storefront";
const SESSIONS = "/api/v1/sessions";

function productQuery(p: URLSearchParams): ProductQuery {
  const filters: Record<string, string[]> = {};
  for (const f of p.getAll("f")) {
    const [ch, v] = f.split(":");
    if (ch && v) (filters[ch] ??= []).push(v);
  }
  return {
    category: p.get("category") ?? undefined,
    position: p.get("position") ?? undefined,
    q: p.get("q") ?? undefined,
    sort: (p.get("sort") as Sort | null) ?? undefined,
    page: p.has("page") ? Number(p.get("page")) : undefined,
    pageSize: p.has("page_size") ? Number(p.get("page_size")) : undefined,
    filters,
  };
}

function route(path: string, params: URLSearchParams): unknown {
  const [, resource, id] = path.split("/").map(decodeURIComponent);
  if (resource === "categories" && id === undefined) return catalog.categories();
  if (resource === "positions")
    return id === undefined
      ? catalog.positions(params.get("category") ?? undefined)
      : catalog.position(id);
  if (resource === "products")
    return id === undefined ? catalog.products(productQuery(params)) : catalog.product(id);
  throw new Missing(path);
}

type Body = { text?: string; question_id?: string; option?: string | null; value_code?: string | null };

/** Сессии карточки поставщика: раздел 12.1 плана. */
function sessionRoute(method: string, path: string, body: Body): unknown {
  const [, id, action, key] = path.split("/").map(decodeURIComponent);
  if (method === "POST" && id === undefined) return seller.create(body.text ?? "");
  if (method === "GET" && id && !action) return seller.get(id);
  if (method === "POST" && action === "messages") return seller.message(id, body.text ?? "");
  if (method === "POST" && action === "answers")
    return seller.answer(id, body.question_id ?? "", body.option ?? null);
  if (method === "PATCH" && action === "facts" && key)
    return seller.editFact(id, key, body.value_code ?? null);
  throw new Missing(path);
}

async function readBody(req: IncomingMessage): Promise<Body> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw ? (JSON.parse(raw) as Body) : {};
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  const method = req.method ?? "GET";
  let handle: () => unknown;
  if (method === "GET" && url.pathname.startsWith(PREFIX))
    handle = () => route(url.pathname.slice(PREFIX.length), url.searchParams);
  else if (url.pathname.startsWith(SESSIONS)) {
    let body: Body;
    try {
      body = await readBody(req);
    } catch {
      return send(res, 400, { detail: "Тело запроса — не JSON" });
    }
    handle = () => sessionRoute(method, url.pathname.slice(SESSIONS.length), body);
  } else return send(res, 404, { detail: "Не найдено" });
  // задержка как у настоящего сервиса, чтобы были видны состояния загрузки
  setTimeout(() => {
    try {
      send(res, 200, handle());
    } catch (e) {
      if (e instanceof Missing) send(res, 404, { detail: `Не найдено: ${e.message}` });
      else if (e instanceof Conflict) send(res, 409, { detail: e.message });
      else send(res, 500, { detail: String(e) });
    }
  }, 120 + Math.random() * 280);
}).listen(PORT, () => console.log(`мок API: http://localhost:${PORT}${PREFIX}, ${SESSIONS}`));
