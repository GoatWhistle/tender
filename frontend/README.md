# Витрина покупателя

React + Vite + TypeScript. Страницы: главная, каталог (`/catalog`, `/catalog/:slug`) с фильтрами
по характеристикам позиции КТРУ, карточка товара (`/product/:id`).

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, мок API в браузере
npm test           # логика мока: фильтры, фасеты, сортировка
npm run build
VITE_API=http npm run dev   # настоящий бэкенд через прокси /api → API_URL (http://localhost:8000)
```

## API

Контракт — `src/api/types.ts` (`StorefrontApi`). Две реализации:

- `src/api/mock/` — мок по умолчанию: данные `fixtures.json`, задержка 120–400 мс;
- `src/api/http.ts` — `GET /api/v1/storefront/{categories, positions, positions/{code},
  products, products/{id}}`; фильтры — повторяющийся `f=<код характеристики>:<код значения>`.
  На бэкенде этих эндпоинтов пока нет.

Фасеты — только внутри выбранной позиции КТРУ: у каждой позиции свои характеристики. Счётчик
значения считается без фильтра своей характеристики.

Фикстуры собираются из `var/` (`backend/build_var.py`): позиции КТРУ — настоящие, названия
товаров — из выгрузок СТЕ, значения характеристик выбираются из допустимых значений позиции,
цены и поставщики выдуманы.

```bash
uvx python -I frontend/scripts/build_mock.py var frontend/src/api/mock/fixtures.json
```

## Стиль

Референс — AVNIER (refero.design): белый холст, чёрные полосы, моно-текст капсом, крупные
заголовки, линейки 1px, углы 0. Шрифты без кириллицы заменены: Space Mono → IBM Plex Mono,
avnier-font → Unbounded (`@fontsource`, работают офлайн). Фото нет — вместо них «таблички»
с рисунком категории и кодом КТРУ (`SpecPlate`).
