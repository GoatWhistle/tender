# Витрина покупателя

React + Vite + TypeScript. Страницы: главная, каталог (`/catalog`, `/catalog/:slug`) с фильтрами
по характеристикам позиции КТРУ, карточка товара (`/product/:id`).

```bash
cd frontend
npm ci
npm run mock-api                          # мок-сервис API на http://localhost:8001
API_URL=http://localhost:8001 npm run dev # http://localhost:5173, /api → мок-сервис
npm run dev                               # /api → бэкенд на http://localhost:8000
npm test                                  # логика мок-сервиса: фильтры, фасеты, сортировка
npm run build
```

## API

Контракт — `src/api/types.ts` (`StorefrontApi`), фронт ходит в API только через HTTP-клиент
`src/api/http.ts`: `GET /api/v1/storefront/{categories, positions, positions/{code}, products,
products/{id}}`; фильтры — повторяющийся `f=<код характеристики>:<код значения>`.

На бэкенде этих эндпоинтов пока нет, их отдаёт мок-сервис `mock-api/` (Node, без зависимостей):
`server.ts` — HTTP и задержка 120–400 мс, `catalog.ts` — выдача, фасеты, сортировка,
`fixtures.json` — данные. В сборку фронта мок не попадает.

Фасеты — только внутри выбранной позиции КТРУ: у каждой позиции свои характеристики. Счётчик
значения считается без фильтра своей характеристики.

Фикстуры собираются из `var/` (`backend/build_var.py`): позиции КТРУ — настоящие, названия
товаров — из выгрузок СТЕ, значения характеристик выбираются из допустимых значений позиции,
цены и поставщики выдуманы.

```bash
uvx python -I frontend/scripts/build_mock.py var frontend/mock-api/fixtures.json
```

## Стиль

Референс — AVNIER (refero.design): белый холст, чёрные полосы, моно-текст капсом, крупные
заголовки, линейки 1px, углы 0. Шрифты без кириллицы заменены: Space Mono → IBM Plex Mono,
avnier-font → Unbounded (`@fontsource`, работают офлайн). Фото нет — вместо них «таблички»
с рисунком категории и кодом КТРУ (`SpecPlate`).
