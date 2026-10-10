// Мок-сервис API витрины: те же эндпоинты, что ждёт `src/api/http.ts`, на данных fixtures.json.
// Сессий поставщика здесь нет — экран `/sell` работает только с бэкендом. Запуск: `npm run mock-api` (порт MOCK_PORT, по умолчанию 8001).
import { readFileSync } from "node:fs";
import { createServer, type ServerResponse } from "node:http";
import type { ProductQuery, Sort } from "../src/api/types.ts";
import { Missing, createCatalog, type Fixtures } from "./catalog.ts";

const fixtures = JSON.parse(
  readFileSync(new URL("./fixtures.json", import.meta.url), "utf8"),
) as Fixtures;
const catalog = createCatalog(fixtures);
const PORT = Number(process.env.MOCK_PORT ?? 8001);
const PREFIX = "/api/v1/storefront";

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

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  if (req.method !== "GET" || !url.pathname.startsWith(PREFIX))
    return send(res, 404, { detail: "Не найдено" });
  const handle = () => route(url.pathname.slice(PREFIX.length), url.searchParams);
  // задержка как у настоящего сервиса, чтобы были видны состояния загрузки
  setTimeout(
    () => {
      try {
        send(res, 200, handle());
      } catch (e) {
        if (e instanceof Missing) send(res, 404, { detail: `Не найдено: ${e.message}` });
        else send(res, 500, { detail: String(e) });
      }
    },
    120 + Math.random() * 280,
  );
}).listen(PORT, () => console.log(`мок API: http://localhost:${PORT}${PREFIX}`));
