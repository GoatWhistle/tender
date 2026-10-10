# Запуск и проверки

> Интерфейс, витрина и справочник КТРУ запускаются на любой машине с Python 3.11+ и Node 22+.
> Анализ описаний требует трёх локальных моделей на GPU с 40 ГБ видеопамяти: без них поиск
> отвечает 503, а сессия получает статус технического сбоя. Проверки бэкенда и фронтенда, включая
> e2e, не требуют ни GPU, ни сети.

**Читайте, если** вы поднимаете стенд или прогоняете проверки · **Связано:**
[архитектура](architecture.md) · [зависимости](dependencies.md)

---

## Как поднять стенд?

Готовая база справочника с векторами групп лежит в репозитории, исходные XML для запуска не нужны.

```bash
mkdir -p var && cp artifacts/ktru-search.sqlite3 var/tender.db
cd backend && uv sync && uv run alembic upgrade head
EMBEDDINGS_URL=http://127.0.0.1:8081/v1 DECISION_URL=http://127.0.0.1:18080 \
  EXTRACTOR_URL=http://127.0.0.1:8082 \
  uv run uvicorn --factory main:create_app --host 127.0.0.1 --port 8000
```

```bash
cd frontend && npm ci --silent
npm run mock-api
STOREFRONT_URL=http://localhost:8001 API_URL=http://localhost:8000 npm run dev
```

| Адрес | Что это |
|---|---|
| <http://localhost:5173> | Интерфейс: главная, каталог, товар, мастер `/sell` |
| <http://localhost:8000/api/docs> | Swagger API бэкенда |
| <http://localhost:8001/api/v1/storefront> | Мок-сервис витрины |

## Как запустить модели?

Модели работают в отдельных контейнерах на NVIDIA GPU. Проверенный профиль — одна A100 40 ГБ.

| Сервис | Команда | Порт | Документация |
|---|---|---|---|
| OpenJev 4B v5 | `OPENJEV_PORT=18080 docker compose --profile gpu up --build -d openjev` | 18080 | [`services/openjev/README.md`](../services/openjev/README.md) |
| Эмбеддинги и экстрактор | `docker compose -f compose.yaml -f compose.qwen.yaml --profile gpu up -d` | 8081, 8082 | [`services/qwen/README.md`](../services/qwen/README.md) |

Веса скачиваются отдельным профилем `download`; команды и проверки весов — в README сервисов.

## Какие переменные окружения есть?

| Переменная | По умолчанию | Что задаёт |
|---|---|---|
| `DATABASE_URL` | `sqlite:///…/var/tender.db` | База справочника и сессий |
| `EMBEDDINGS_URL` | нет | Сервис эмбеддингов, базовый URL с `/v1`; без него поиск отвечает 503 |
| `EMBEDDINGS_MODEL` | `qwen-embedding` | Имя развёрнутой модели |
| `EMBEDDINGS_REVISION` | `97b0c614…` | Ревизия весов; должна совпадать с векторами базы |
| `DECISION_URL` | нет | Сервис OpenJev; без него проверка назначения невозможна |
| `DECISION_AUTO_ACCEPT_THRESHOLD` | `0.90` | Порог автопринятия перечислимых значений |
| `EXTRACTOR_URL` | нет | Корень строгого API экстрактора Qwen3.5, без `/v1`; без него работает только парсер |
| `VERIFIER_THRESHOLD` | `0.90` | Порог NLI-проверки извлечённых фактов |
| `SPELLING_URL` | нет | Проверка орфографии; без неё ответ несёт замечание `spelling_failed` |
| `GROUP_TOP_K` | `10` | Сколько групп проверяется на назначение |
| `SEARCH_MIN_SIMILARITY` | `0.45` | Косинус, ниже которого текст считается вне справочника |
| `STOREFRONT_URL`, `API_URL` | `http://localhost:8000` | Куда Vite отправляет `/api/v1/storefront` и остальной `/api` |

Полный список с типами — [`backend/settings.py`](../backend/settings.py).

## Как прогнать проверки?

| Что | Команда | Результат на этом коммите |
|---|---|---|
| Бэкенд | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` | 405 тестов проходят |
| Фронтенд | `cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` | 66 юнит-тестов проходят |
| e2e | `cd frontend && npm run e2e` | 16 сценариев на десктопе и телефоне, светлая и тёмная тема, axe без серьёзных нарушений |
| Сервис OpenJev без весов | `PYTHONPATH=services/openjev python -m unittest discover -s tests/decisions` | — |
| Сервисы Qwen без GPU | `PYTHONPATH=services/qwen python3 -m unittest discover -s tests/qwen` | — |

e2e поднимают мок витрины и Vite на своих портах, API сессий подменяют фикстурами
[`e2e/fixtures/sell.ts`](../frontend/e2e/fixtures/sell.ts). Браузер — Chromium из Playwright:
`npx playwright install chromium` один раз на машину.

Тесты бэкенда собирают схему через Alembic. На Windows Alembic читает `alembic.ini` в кодировке
системы и падает на кириллице; на Linux, где работает стенд, такой проблемы нет.

## Как пересчитать метрики?

Каждый отчёт в [`evals/reports/`](../evals/reports/) содержит команду, которой он собран.
Основные — в [доказательствах](evidence.md); определения метрик и пороги — в
[плане валидации](validation-plan.md).

---

<sub>[Оглавление документации](README.md) · [README проекта](../README.md)</sub>
