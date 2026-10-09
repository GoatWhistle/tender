# Tender Hack: автозаполнение характеристик СТЕ и подбор КТРУ

План реализации — `docs/Предлагаемое решение.md`. Трекер и порядок работы — `AGENTS.md`.

## Команды

```bash
uv sync                                   # зависимости
uv run python -m backend.catalog.build    # индекс КТРУ и словарь → var/
```

## Структура

- `src/backend/catalog/` — загрузка XML КТРУ в структуры Python, сборка `var/`.
- `evals/datasets/` — размеченные наборы; `evals/smoke/` — скрипты замеров;
  `evals/reports/` — отчёты.
